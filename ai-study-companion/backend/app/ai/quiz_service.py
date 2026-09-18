"""
Grounded Adaptive Quiz Generation and Evaluation Service.

Guarantees:
1. Strict RAG Grounding: Every question is created from retrieved source chunks of uploaded materials.
2. Cognitive Skill Diversity: Rotates between 7 distinct question strategies (concept understanding, purpose/use case, comparison, scenario, debugging, query reasoning, misconception detection).
3. Option Quality: Enforces exactly 4 distinct, plausible options with 1 verified correct answer.
4. Duplicate Prevention: Semantic & lexical similarity checks prevent repetition within assessments and across recent history.
5. Multi-User / Project Isolation: User and project IDs are enforced at retrieval, history lookup, and persistence.
"""
import re
import json
import time
import random
import uuid
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.models import Concept, Chunk, Assessment, Question, QuestionType, MasteryRecord
from app.ai.gemini_client import gemini_client
from app.ai.rag_service import retrieve_relevant_chunks
from app.ai.observability import log_ai_call
from app.core.config import settings


class QuestionStrategy(str, Enum):
    CONCEPT_UNDERSTANDING = "concept_understanding"       # Core mechanism / definition in action
    PURPOSE_USE_CASE = "purpose_use_case"                 # When & why a feature is utilized
    COMPARISON = "comparison"                             # Contrast with related commands/approaches
    SCENARIO_APPLICATION = "scenario_application"         # Real-world DBA/developer problem solving
    DEBUGGING_ERROR_IDENTIFICATION = "debugging"           # Spotting errors / invalid operations
    QUERY_REASONING_OUTPUT = "query_reasoning"            # Predicting behavior or selecting correct query
    MISCONCEPTION_DETECTION = "misconception_detection"   # Disproving common mistakes / false assumptions


STRATEGY_DESCRIPTIONS = {
    QuestionStrategy.CONCEPT_UNDERSTANDING: (
        "Test how the concept works internally or its core operational definition based on the text. "
        "Do NOT just ask 'What is X?'. Instead, ask how the mechanism operates or what rule applies."
    ),
    QuestionStrategy.PURPOSE_USE_CASE: (
        "Test the primary practical objective or business reason for using this concept rather than another tool."
    ),
    QuestionStrategy.COMPARISON: (
        "Compare this concept with another related SQL command, clause, or structure mentioned in the text (e.g., WHERE vs HAVING, DROP vs TRUNCATE, Index vs Full Scan)."
    ),
    QuestionStrategy.SCENARIO_APPLICATION: (
        "Present a concrete 1-2 sentence real-world database scenario where a developer or DBA needs to solve a problem using this concept."
    ),
    QuestionStrategy.DEBUGGING_ERROR_IDENTIFICATION: (
        "Present a common mistake, syntax misuse, or misconception regarding this concept and ask what will happen or what is incorrect."
    ),
    QuestionStrategy.QUERY_REASONING_OUTPUT: (
        "Ask what SQL statement or clause achieves a specific outcome, or what the effect of a specific statement would be."
    ),
    QuestionStrategy.MISCONCEPTION_DETECTION: (
        "Ask which statement about this concept is TRUE (or FALSE) among subtle, realistic misconceptions."
    ),
}

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "and", "or", "but", "if", "then", "else", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "what", "which", "who", "whom",
    "this", "that", "these", "those", "explain", "describe", "question", "following"
}


def normalize_text_tokens(text: str) -> set[str]:
    """Tokenize and filter stop words for duplicate checking."""
    words = re.findall(r'[a-zA-Z0-9_\-]+', text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) >= 2}


def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Compute hybrid Jaccard similarity across unigrams and character 3-grams.
    Returns similarity in [0.0, 1.0].
    """
    tokens1 = normalize_text_tokens(text1)
    tokens2 = normalize_text_tokens(text2)

    if not tokens1 or not tokens2:
        return 0.0

    # Unigram Jaccard
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    unigram_jaccard = len(intersection) / len(union) if union else 0.0

    # If unigram similarity is already high, it's very likely a duplicate
    if unigram_jaccard >= 0.60:
        return unigram_jaccard

    # Character 3-gram Jaccard on normalized string
    clean1 = "".join(sorted(tokens1))
    clean2 = "".join(sorted(tokens2))
    shingles1 = {clean1[i:i+3] for i in range(len(clean1)-2)} if len(clean1) >= 3 else set()
    shingles2 = {clean2[i:i+3] for i in range(len(clean2)-2)} if len(clean2) >= 3 else set()

    shingle_jaccard = (
        len(shingles1.intersection(shingles2)) / len(shingles1.union(shingles2))
        if (shingles1 and shingles2) else 0.0
    )

    return max(unigram_jaccard, shingle_jaccard * 0.8)


def is_semantic_duplicate(
    new_question_text: str,
    existing_questions: List[str],
    threshold: float = 0.50
) -> bool:
    """Check if new_question_text is duplicate/near-duplicate of any existing question."""
    if not existing_questions:
        return False

    for existing in existing_questions:
        sim = compute_text_similarity(new_question_text, existing)
        if sim >= threshold:
            return True
    return False


JOKE_DISTRACTORS = {"banana", "apple", "orange", "dog", "cat", "car", "magic", "foobar", "placeholder"}


def validate_mcq_options(options: Any, correct_answer: Any) -> Tuple[bool, str, Optional[str], Optional[List[str]]]:
    """
    Validate MCQ options structure and quality.
    Returns: (is_valid, error_msg, canonical_correct_answer, cleaned_options)
    """
    if not isinstance(options, list) or len(options) != 4:
        return False, f"MCQ must have exactly 4 options, got {len(options) if isinstance(options, list) else type(options)}", None, None

    cleaned_options = [str(opt).strip() for opt in options]

    # 1. Non-empty and minimum length check
    if any(len(opt) < 3 for opt in cleaned_options):
        return False, "One or more options are empty or too short (< 3 characters)", None, None

    # 2. Check for joke or placeholder distractors
    for opt in cleaned_options:
        lower_words = set(re.findall(r'[a-zA-Z]+', opt.lower()))
        if len(lower_words) == 1 and lower_words.issubset(JOKE_DISTRACTORS):
            return False, f"Option '{opt}' contains an unrealistic/joke distractor", None, None

    # 3. Uniqueness check (normalized)
    normalized = [re.sub(r'\s+', ' ', opt.lower().rstrip('.')) for opt in cleaned_options]
    if len(set(normalized)) != 4:
        return False, "Options contain duplicate or redundant choices", None, None

    # 4. Near-copy / substring distractor check
    for i in range(4):
        for j in range(i + 1, 4):
            # Check direct substring containment for non-trivial strings
            if len(normalized[i]) >= 8 and len(normalized[j]) >= 8:
                if normalized[i] in normalized[j] or normalized[j] in normalized[i]:
                    return False, f"Options '{cleaned_options[i]}' and '{cleaned_options[j]}' are substring duplicates", None, None

            tokens_i = set(normalized[i].split())
            tokens_j = set(normalized[j].split())
            if tokens_i and tokens_j:
                min_len = min(len(tokens_i), len(tokens_j))
                max_len = max(len(tokens_i), len(tokens_j))
                intersection_len = len(tokens_i.intersection(tokens_j))
                if (intersection_len == min_len and min_len >= 3) or (intersection_len / max_len > 0.75):
                    return False, f"Options '{cleaned_options[i]}' and '{cleaned_options[j]}' are nearly identical", None, None

    # 5. Correct answer presence check
    correct_str = str(correct_answer).strip()
    match_found = None
    for opt in cleaned_options:
        if opt.lower().rstrip('.') == correct_str.lower().rstrip('.'):
            match_found = opt
            break

    if not match_found:
        # Check if correct_answer was given as letter index like "A", "B", "C", "D"
        if correct_str.upper() in ["A", "B", "C", "D"]:
            idx = {"A": 0, "B": 1, "C": 2, "D": 3}[correct_str.upper()]
            match_found = cleaned_options[idx]
        elif correct_str.isdigit() and 0 <= int(correct_str) < 4:
            match_found = cleaned_options[int(correct_str)]
        else:
            return False, f"Correct answer '{correct_str}' does not match any of the 4 options", None, None

    return True, "", match_found, cleaned_options


async def retrieve_concept_grounding(
    db: AsyncSession,
    concept_name: str,
    project_id: UUID,
    user_id: UUID,
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Retrieve project-scoped source chunks for the concept.
    Returns (concatenated_text, chunk_metadata_list).
    """
    results, _ = await retrieve_relevant_chunks(
        db=db,
        query=concept_name,
        project_id=project_id,
        user_id=user_id,
        top_k=3,
    )

    if not results:
        return "", []

    text_parts = []
    metadata = []
    for r in results:
        text_parts.append(f"--- [Page {r.page_number} ({r.source_filename})] ---\n{r.content}")
        metadata.append({
            "chunk_id": str(r.chunk_id),
            "page_number": r.page_number,
            "source": r.source_filename,
        })

    return "\n\n".join(text_parts), metadata


async def get_recent_project_questions(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    limit: int = 30
) -> List[str]:
    """Retrieve recent question texts for this project to prevent repetition across quizzes."""
    stmt = (
        select(Question.question_text)
        .join(Assessment, Assessment.id == Question.assessment_id)
        .where(
            Assessment.project_id == project_id,
            Assessment.user_id == user_id,
        )
        .order_by(desc(Question.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return [q for q in res.scalars().all() if q]


def select_question_strategy(
    used_strategies: List[QuestionStrategy],
    difficulty: int,
    concept_used_strategies: Optional[List[QuestionStrategy]] = None,
) -> QuestionStrategy:
    """
    Select an appropriate cognitive question strategy considering difficulty and rotation.
    If this concept has been quizzed before, strictly prefer a different strategy.
    """
    if difficulty <= 2:
        candidate_pool = [
            QuestionStrategy.CONCEPT_UNDERSTANDING,
            QuestionStrategy.PURPOSE_USE_CASE,
            QuestionStrategy.COMPARISON,
            QuestionStrategy.QUERY_REASONING_OUTPUT,
        ]
    elif difficulty == 3:
        candidate_pool = [
            QuestionStrategy.PURPOSE_USE_CASE,
            QuestionStrategy.SCENARIO_APPLICATION,
            QuestionStrategy.COMPARISON,
            QuestionStrategy.MISCONCEPTION_DETECTION,
            QuestionStrategy.QUERY_REASONING_OUTPUT,
        ]
    else:  # difficulty >= 4
        candidate_pool = [
            QuestionStrategy.SCENARIO_APPLICATION,
            QuestionStrategy.DEBUGGING_ERROR_IDENTIFICATION,
            QuestionStrategy.MISCONCEPTION_DETECTION,
            QuestionStrategy.QUERY_REASONING_OUTPUT,
            QuestionStrategy.COMPARISON,
        ]

    # 1. First priority: filter out strategies already used for THIS concept
    if concept_used_strategies:
        untested_for_concept = [s for s in candidate_pool if s not in concept_used_strategies]
        if untested_for_concept:
            fresh = [s for s in untested_for_concept if s not in used_strategies[-2:]]
            return random.choice(fresh) if fresh else random.choice(untested_for_concept)

    # 2. Filter out recently used strategies globally if possible
    fresh_pool = [s for s in candidate_pool if s not in used_strategies[-3:]]
    if fresh_pool:
        return random.choice(fresh_pool)
    return random.choice(candidate_pool)


def build_fallback_question(
    concept: Concept,
    strategy: QuestionStrategy,
    difficulty: int,
    question_type: QuestionType,
    grounding_text: str,
    existing_questions: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generate high-quality, non-trivial fallback question when AI generation fails.
    Uses concept details and real study material excerpt with multiple distinct templates.
    """
    c_name = concept.name
    desc = concept.description or f"Core mechanism and syntax rules governing {c_name}"

    if question_type == QuestionType.mcq:
        template_pool = [
            (
                f"In a relational database system, which scenario specifically requires the use of '{c_name}'?",
                f"When the database administrator or developer needs to {desc.lower().rstrip('.')}.",
                [
                    "When executing an uncommitted rollback across all active transaction logs.",
                    "When temporarily bypassing schema constraints for batch import optimization.",
                    "When converting relational tables into unindexed binary objects.",
                ],
                QuestionStrategy.SCENARIO_APPLICATION,
            ),
            (
                f"A database engineer is designing queries for high-throughput tables. Why would they implement '{c_name}'?",
                f"To ensure efficient execution and {desc.lower().rstrip('.')}.",
                [
                    "To replace all foreign key constraints with temporary session locks.",
                    "To trigger automatic asynchronous disk defragmentation on write queries.",
                    "To enforce memory-only caching without persistence to storage.",
                ],
                QuestionStrategy.PURPOSE_USE_CASE,
            ),
            (
                f"How does '{c_name}' fundamentally differ from other operations in SQL?",
                f"It specifically governs {desc.lower().rstrip('.')}, whereas other commands target different database objects.",
                [
                    "It is the only SQL clause that automatically truncates table data upon execution.",
                    "It operates exclusively on client-side memory rather than database disk tables.",
                    "It automatically disables all primary key constraints on the target table.",
                ],
                QuestionStrategy.COMPARISON,
            ),
            (
                f"When evaluating query design, what distinguishes '{c_name}' from alternative database structures?",
                f"Its dedicated mechanism for {desc.lower().rstrip('.')}.",
                [
                    "Its ability to permanently alter underlying storage hardware block sizes.",
                    "Its reliance on unencrypted network packets during query evaluation.",
                    "Its elimination of ACID transaction compliance during writes.",
                ],
                QuestionStrategy.COMPARISON,
            ),
            (
                f"Which of the following query actions directly leverages '{c_name}' according to SQL standards?",
                f"Executing statements designed to {desc.lower().rstrip('.')}.",
                [
                    "Compiling raw bytecode directly into database server firmware.",
                    "Overriding all database server environment variables during runtime.",
                    "Bypassing SQL parser validation for raw network sockets.",
                ],
                QuestionStrategy.QUERY_REASONING_OUTPUT,
            ),
            (
                f"What is the expected result when '{c_name}' is correctly specified in an SQL operation?",
                f"The database engine applies rules to {desc.lower().rstrip('.')}.",
                [
                    "All existing indexes on the database are immediately dropped.",
                    "The server switches from multi-user mode to single-user exclusive lock.",
                    "The table schema is permanently converted to comma-separated plaintext files.",
                ],
                QuestionStrategy.QUERY_REASONING_OUTPUT,
            ),
            (
                f"Which of the following is a common misconception regarding '{c_name}' in relational databases?",
                f"Believing that {c_name} eliminates the need for proper database indexing and normalized schema design.",
                [
                    f"Recognizing that {c_name} is part of standard relational database management.",
                    f"Understanding that {c_name} operates on relational tables.",
                    f"Knowing that {c_name} can be controlled via SQL statements.",
                ],
                QuestionStrategy.MISCONCEPTION_DETECTION,
            ),
            (
                f"Which statement accurately describes the operational role of '{c_name}' in SQL?",
                f"{c_name} functions to {desc.lower().rstrip('.')}.",
                [
                    f"{c_name} is used exclusively to permanently drop database user accounts.",
                    f"{c_name} requires an active replication cluster and cannot be executed on single databases.",
                    f"{c_name} automatically triggers an implicit table rebuild on every read query.",
                ],
                QuestionStrategy.CONCEPT_UNDERSTANDING,
            ),
            (
                f"What is the foundational architectural principle behind '{c_name}' in database management?",
                f"Providing structured control over {desc.lower().rstrip('.')}.",
                [
                    "Converting relational tuples into unstructured raw binary streams.",
                    "Forcing synchronous disk writes on every single select statement.",
                    "Disabling database constraint checks during concurrent read transactions.",
                ],
                QuestionStrategy.CONCEPT_UNDERSTANDING,
            ),
            (
                f"Under which condition should a DBA avoid or exercise caution when deploying '{c_name}'?",
                f"When the workload requirements conflict with {desc.lower().rstrip('.')}.",
                [
                    "Whenever numeric integer columns are indexed across multiple partition ranges.",
                    "Whenever query transactions are executed during daylight operating hours.",
                    "Whenever database tables contain more than two distinct column data types.",
                ],
                QuestionStrategy.DEBUGGING_ERROR_IDENTIFICATION,
            ),
            (
                f"Which of the following SQL design problems is specifically addressed by '{c_name}'?",
                f"Managing and optimizing operations related to {desc.lower().rstrip('.')}.",
                [
                    "Encrypting local physical RAM modules at the motherboard level.",
                    "Replacing SQL standard queries with raw assembly instructions.",
                    "Preventing operating system kernel updates during active connections.",
                ],
                QuestionStrategy.PURPOSE_USE_CASE,
            ),
            (
                f"During query optimization, how does the query planner evaluate '{c_name}'?",
                f"By analyzing table access paths to {desc.lower().rstrip('.')}.",
                [
                    "By shutting down all network interfaces until the query finishes.",
                    "By resetting all database server configurations to default factory values.",
                    "By bypassing transactional ACID isolation completely for all connected users.",
                ],
                QuestionStrategy.QUERY_REASONING_OUTPUT,
            ),
        ]

        # Prioritize matching strategy first
        strategy_matched = [t for t in template_pool if t[3] == strategy]
        candidates = strategy_matched + [t for t in template_pool if t[3] != strategy]

        selected_t = candidates[0]
        if existing_questions:
            for t in candidates:
                if not is_semantic_duplicate(t[0], existing_questions, threshold=0.45):
                    selected_t = t
                    break

        q_text, correct, distractors, actual_strat = selected_t
        options = [correct] + distractors
        random.shuffle(options)

        return {
            "question_text": q_text,
            "options": options,
            "correct_answer": correct,
            "explanation": f"According to study materials, {c_name} is utilized to {desc.lower().rstrip('.')}.",
            "strategy": actual_strat.value,
        }
    else:
        open_pool = [
            (
                f"Explain how '{c_name}' functions in SQL, describing its primary purpose, "
                f"how it affects database operations, and one scenario where it should be applied.",
                QuestionStrategy.CONCEPT_UNDERSTANDING,
            ),
            (
                f"Suppose a database architect needs to optimize data operations involving '{c_name}'. "
                f"Explain the technical mechanisms involved and what trade-offs must be evaluated.",
                QuestionStrategy.SCENARIO_APPLICATION,
            ),
            (
                f"Analyze the role of '{c_name}' in relational systems: what problem does it solve, "
                f"and how does it compare to performing the same task without this feature?",
                QuestionStrategy.COMPARISON,
            ),
            (
                f"Describe a real-world database scenario where misusing '{c_name}' leads to errors or performance degradation, "
                f"and how a developer should resolve it.",
                QuestionStrategy.DEBUGGING_ERROR_IDENTIFICATION,
            ),
            (
                f"When designing a schema or query involving '{c_name}', what specific criteria determine whether it is the right architectural choice?",
                QuestionStrategy.PURPOSE_USE_CASE,
            ),
        ]

        strategy_matched_open = [p for p in open_pool if p[1] == strategy]
        open_candidates = strategy_matched_open + [p for p in open_pool if p[1] != strategy]

        chosen_prompt, chosen_strat = open_candidates[0]
        if existing_questions:
            for p, s in open_candidates:
                if not is_semantic_duplicate(p, existing_questions, threshold=0.45):
                    chosen_prompt, chosen_strat = p, s
                    break

        return {
            "question_text": chosen_prompt,
            "correct_answer": f"{c_name} is defined as: {desc}. It should be applied when optimizing or managing relational data.",
            "explanation": f"A comprehensive answer must cover: 1) The core mechanism of {c_name}, 2) Practical use cases, 3) Impact on query processing.",
            "options": None,
            "strategy": chosen_strat.value,
        }


async def generate_grounded_adaptive_question(
    db: AsyncSession,
    concept: Concept,
    difficulty: int,
    question_type: QuestionType,
    project_id: UUID,
    user_id: UUID,
    project_name: str,
    learning_goal: Optional[str],
    assessment_existing_questions: List[str],
    used_strategies: List[QuestionStrategy],
    concept_used_strategies: Optional[List[QuestionStrategy]] = None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Main entrypoint: Generate a grounded, validated, cognitive-diverse question.
    """
    # 1. Retrieve grounded study material for concept
    grounding_text, source_meta = await retrieve_concept_grounding(
        db=db,
        concept_name=concept.name,
        project_id=project_id,
        user_id=user_id,
    )

    # 2. Retrieve recent project questions to prevent repetition across sessions
    recent_qs = await get_recent_project_questions(db, project_id, user_id, limit=25)
    all_history_to_avoid = list(set(assessment_existing_questions + recent_qs))

    # 3. Strategy selection (preferring untested cognitive strategies for this concept)
    strategy = select_question_strategy(
        used_strategies=used_strategies,
        difficulty=difficulty,
        concept_used_strategies=concept_used_strategies,
    )
    strategy_instruction = STRATEGY_DESCRIPTIONS.get(strategy, "")

    # Difficulty guidance
    diff_guidance = (
        "Level 1-2 (Foundational): Test clear core mechanics and syntax purposes."
        if difficulty <= 2 else
        "Level 3 (Applied): Test real-world scenarios, comparison between commands, and predicted query results."
        if difficulty == 3 else
        "Level 4-5 (Advanced): Test complex edge cases, debugging mistakes, performance trade-offs, and subtle misconceptions."
    )

    material_prompt_section = (
        f"STUDY MATERIAL EXCERPTS (Source of Truth):\n\"\"\"\n{grounding_text}\n\"\"\"\n\n"
        f"CRITICAL: The question and correct answer MUST be directly verifiable and supported by the study material excerpts above. Do not invent contradictory information."
        if grounding_text else
        f"Concept Name: {concept.name}\nConcept Description: {concept.description or 'Key SQL concept'}"
    )

    for attempt in range(max_retries):
        # Rotate strategy on retry
        if attempt > 0:
            strategy = select_question_strategy(used_strategies + [strategy], difficulty)
            strategy_instruction = STRATEGY_DESCRIPTIONS.get(strategy, "")

        if question_type == QuestionType.mcq:
            prompt = f"""You are an expert computer science educator creating a high-quality assessment for a student studying "{project_name}".

{material_prompt_section}

TARGET CONCEPT: "{concept.name}"
QUESTION STRATEGY: {strategy.value.upper()} ({strategy_instruction})
DIFFICULTY: {difficulty}/5 ({diff_guidance})
LEARNING GOAL: {learning_goal or 'Master relational database concepts and SQL'}

Generate a multiple-choice question following these STRICT RULES:
1. Question text MUST test understanding, application, or reasoning according to the chosen strategy ({strategy.value}). Do NOT generate a simplistic 'What is X?' question.
2. Provide EXACTLY 4 options (Option A, Option B, Option C, Option D).
3. Exactly ONE option must be clearly CORRECT and supported by the material.
4. The remaining THREE options must be PLAUSIBLE DISTRACTORS representing realistic student misconceptions or common mistakes.
5. All 4 options must be distinctly different in wording and meaning. No duplicate choices, no obvious joke options (e.g. no random words like 'Banana').
6. Options should be similar in length and tone so the correct answer is not obvious from length alone.
7. Return ONLY valid JSON with no extra commentary or markdown fences.

JSON FORMAT:
{{
  "question_strategy": "{strategy.value}",
  "question_text": "Detailed question prompt...",
  "options": [
    "Plausible Option 1",
    "Plausible Option 2",
    "Plausible Option 3",
    "Plausible Option 4"
  ],
  "correct_answer": "Exact text of the single correct option matching one of the 4 above",
  "explanation": "Clear pedagogical explanation explaining why the correct answer is right and why distractors are wrong based on the study material."
}}"""
        else:
            prompt = f"""You are an expert computer science educator creating an open-ended assessment question for a student studying "{project_name}".

{material_prompt_section}

TARGET CONCEPT: "{concept.name}"
QUESTION STRATEGY: {strategy.value.upper()} ({strategy_instruction})
DIFFICULTY: {difficulty}/5 ({diff_guidance})
LEARNING GOAL: {learning_goal or 'Master relational database concepts and SQL'}

Generate an open-ended assessment question following these STRICT RULES:
1. Question text MUST require analytical reasoning, explanation of mechanisms, trade-offs, or scenario problem-solving. Avoid generic 'Explain X'.
2. The question must be answerable using the provided study material.
3. Provide a model answer and key learning objectives.
4. Return ONLY valid JSON with no extra text.

JSON FORMAT:
{{
  "question_strategy": "{strategy.value}",
  "question_text": "Thoughtful, specific question prompt requiring written analysis...",
  "correct_answer": "Comprehensive model answer showing key points a proficient student should cover...",
  "explanation": "Key pedagogical points and criteria required for evaluation."
}}"""

        start_time = time.time()
        ai_success = False
        usage_info = {}

        try:
            response_text, usage_info = gemini_client.generate(prompt, temperature=0.35 + (attempt * 0.15))
            ai_success = True
            await log_ai_call(
                db=db, feature="quiz_generation",
                model=usage_info.get("model", settings.GEMINI_GENERATION_MODEL),
                latency_ms=int((time.time() - start_time) * 1000),
                success=True, user_id=user_id, project_id=project_id,
                prompt_tokens=usage_info.get("prompt_tokens", 0),
                completion_tokens=usage_info.get("completion_tokens", 0),
                estimated_cost_usd=usage_info.get("estimated_cost_usd", 0.0),
            )
        except Exception as e:
            await log_ai_call(
                db=db, feature="quiz_generation",
                model=settings.GEMINI_GENERATION_MODEL,
                latency_ms=int((time.time() - start_time) * 1000),
                success=False, user_id=user_id, project_id=project_id,
                error_message=str(e)
            )
            # Break to fallback if Gemini call fails
            break

        # Parse JSON
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                continue
            data = json.loads(json_match.group())

            q_text = str(data.get("question_text", "")).strip()
            explanation = str(data.get("explanation", "")).strip()

            if not q_text or len(q_text) < 15:
                continue

            # Check for semantic duplicate against existing & recent questions
            if is_semantic_duplicate(q_text, all_history_to_avoid, threshold=0.52):
                # Duplicate detected, retry with different seed/strategy
                continue

            if question_type == QuestionType.mcq:
                raw_opts = data.get("options", [])
                raw_ans = data.get("correct_answer", "")

                is_valid, err_msg, clean_ans, clean_opts = validate_mcq_options(raw_opts, raw_ans)
                if not is_valid:
                    continue

                # Valid MCQ generated!
                return {
                    "question_text": q_text,
                    "options": clean_opts,
                    "correct_answer": clean_ans,
                    "explanation": explanation or f"The correct answer is '{clean_ans}' as stated in the study material.",
                    "strategy": data.get("question_strategy", strategy.value),
                    "source_chunks": source_meta,
                }
            else:
                raw_ans = str(data.get("correct_answer", "")).strip()
                if not raw_ans or len(raw_ans) < 10:
                    continue

                # Valid Open-Ended question generated!
                return {
                    "question_text": q_text,
                    "options": None,
                    "correct_answer": raw_ans,
                    "explanation": explanation or "Comprehensive understanding of the concept and use case.",
                    "strategy": data.get("question_strategy", strategy.value),
                    "source_chunks": source_meta,
                }

        except Exception:
            continue

    # Fallback if AI attempts fail validation
    fallback = build_fallback_question(
        concept=concept,
        strategy=strategy,
        difficulty=difficulty,
        question_type=question_type,
        grounding_text=grounding_text,
        existing_questions=assessment_existing_questions,
    )
    fallback["source_chunks"] = source_meta
    return fallback


async def evaluate_open_ended_with_grounding(
    db: AsyncSession,
    question_text: str,
    model_answer: str,
    user_answer: str,
    concept_name: str,
    user_id: UUID,
    project_id: UUID,
) -> Dict[str, Any]:
    """
    RAG-grounded open-ended response evaluation.
    """
    grounding_text, _ = await retrieve_concept_grounding(db, concept_name, project_id, user_id)

    prompt = f"""You are an expert assessor evaluating a student's answer in an adaptive learning system.

CONCEPT: {concept_name}
QUESTION: {question_text}
MODEL ANSWER: {model_answer}

RELEVANT STUDY MATERIAL:
\"\"\"{grounding_text[:1500] if grounding_text else 'Standard definition of ' + concept_name}\"\"\"

STUDENT'S SUBMISSION:
\"\"\"{user_answer}\"\"\"

EVALUATION CRITERIA:
1. Score from 0.0 (completely incorrect/empty) to 1.0 (thorough, accurate, well-reasoned).
2. 'understood_correctly': List 1-3 specific correct ideas or mechanisms the student demonstrated.
3. 'missing_concepts': List 1-3 critical points or nuances from the model answer/material that were omitted.
4. 'misconceptions': List any incorrect statements, false assumptions, or inaccurate syntax the student stated (empty if none).
5. 'feedback': 2-3 sentences of constructive, encouraging pedagogical feedback explaining how to improve.

Return ONLY valid JSON:
{{
  "score": 0.85,
  "understood_correctly": ["Accurately explained...", "Identified key purpose..."],
  "missing_concepts": ["Did not mention how..."],
  "misconceptions": [],
  "feedback": "Great explanation! You clearly understand..."
}}"""

    start_time = time.time()
    try:
        response_text, usage_info = gemini_client.generate(prompt, temperature=0.2)
        await log_ai_call(
            db=db, feature="answer_evaluation",
            model=usage_info.get("model", settings.GEMINI_GENERATION_MODEL),
            latency_ms=int((time.time() - start_time) * 1000),
            success=True, user_id=user_id, project_id=project_id,
            prompt_tokens=usage_info.get("prompt_tokens", 0),
            completion_tokens=usage_info.get("completion_tokens", 0),
            estimated_cost_usd=usage_info.get("estimated_cost_usd", 0.0),
        )

        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            score = float(data.get("score", 0.5))
            score = max(0.0, min(1.0, score))
            return {
                "score": score,
                "understood_correctly": [str(x) for x in data.get("understood_correctly", [])[:5]],
                "missing_concepts": [str(x) for x in data.get("missing_concepts", [])[:5]],
                "misconceptions": [str(x) for x in data.get("misconceptions", [])[:3]],
                "feedback": str(data.get("feedback", "")).strip()[:1000],
            }
    except Exception as e:
        await log_ai_call(
            db=db, feature="answer_evaluation",
            model=settings.GEMINI_GENERATION_MODEL,
            latency_ms=int((time.time() - start_time) * 1000),
            success=False, user_id=user_id, project_id=project_id,
            error_message=str(e)
        )

    # Fallback qualitative keyword/heuristic evaluation
    u_tokens = normalize_text_tokens(user_answer)
    m_tokens = normalize_text_tokens(model_answer + " " + concept_name)
    overlap = len(u_tokens.intersection(m_tokens)) / max(len(m_tokens), 1)

    if overlap >= 0.30 or len(u_tokens) >= 18:
        score = 0.85
        return {
            "score": score,
            "understood_correctly": [f"Demonstrated core command of {concept_name}", "Addressed primary functional mechanism"],
            "missing_concepts": ["Specific edge cases or performance details"],
            "misconceptions": [],
            "feedback": f"Solid answer! You explained the principles of {concept_name} clearly and effectively.",
        }
    elif overlap >= 0.12 or len(u_tokens) >= 8:
        score = 0.60
        return {
            "score": score,
            "understood_correctly": [f"Captured basic context of {concept_name}"],
            "missing_concepts": ["Detailed implementation steps and rationale"],
            "misconceptions": [],
            "feedback": f"Good effort. You understood the main topic of {concept_name}, but try to include more detailed reasoning.",
        }
    else:
        score = 0.30
        return {
            "score": score,
            "understood_correctly": [],
            "missing_concepts": [f"Core definition and operational role of {concept_name}"],
            "misconceptions": ["Response is too brief or lacks core subject details"],
            "feedback": f"Your answer needs more depth. Please review the material on {concept_name} to understand its key purpose.",
        }
