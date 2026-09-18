"""
Adaptive Quiz API.

Adaptive selection algorithm:
1. Get all concepts + mastery scores
2. Weight by: (1 - normalized_mastery) * importance * mistake_multiplier
3. Select concept probabilistically
4. Map mastery → difficulty
5. Generate question (MCQ or open-ended alternating)
6. For open-ended: AI evaluates with qualitative feedback
7. Post-completion: trigger learning workflow
"""
import uuid
import json
import re
import random
import time
from datetime import datetime, timezone
from typing import Optional, List, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.models import (
    Project, Assessment, AssessmentStatus, Question, QuestionType,
    Answer, Concept, MasteryRecord, Event
)
from app.schemas.schemas import (
    QuizStartRequest, QuestionOut, AnswerSubmitRequest, AnswerResultOut, AssessmentOut
)
from app.core.deps import get_current_user
from app.core.config import settings
from app.ai.gemini_client import gemini_client
from app.ai.observability import log_ai_call

router = APIRouter(tags=["quiz"])


async def _verify_project_access(project_id: UUID, user_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _map_mastery_to_difficulty(score: float) -> int:
    """Map mastery score (0-100) to question difficulty (1-5)."""
    if score < 30:
        return 1
    elif score < 50:
        return 2
    elif score < 65:
        return 3
    elif score < 80:
        return 4
    else:
        return 5


async def _select_adaptive_concept(
    db: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    used_concept_ids: list,
) -> tuple[Optional[Concept], float, int]:
    """
    Adaptive concept selection ensuring concept diversity across the assessment.
    1. First prefers concepts not yet tested in this quiz session.
    2. If repeating concepts, weights them inversely to their previous appearance count.
    3. Integrates mastery trend & importance scores.
    """
    concepts_result = await db.execute(
        select(Concept).where(
            Concept.project_id == project_id,
            Concept.user_id == user_id,
        )
    )
    concepts = concepts_result.scalars().all()

    if not concepts:
        return None, 50.0, 3

    used_ids_str = [str(u) for u in used_concept_ids]

    # Prioritize concepts not yet tested in this assessment
    unused_concepts = [c for c in concepts if str(c.id) not in used_ids_str]
    candidate_pool = unused_concepts if unused_concepts else concepts

    weights = []
    mastery_map = {}

    for concept in candidate_pool:
        mastery_result = await db.execute(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
        )
        mastery = mastery_result.scalar_one_or_none()
        score = mastery.score if mastery else 50.0  # Start at neutral if no data
        mastery_map[concept.id] = score

        # Higher weight for low mastery + high importance
        norm_mastery = score / 100.0
        mistake_multiplier = 1.5 if (mastery and mastery.trend and mastery.trend.value == "needs_attention") else 1.0
        weight = (1.0 - norm_mastery) * concept.importance_score * mistake_multiplier

        # If reusing concept, downweight heavily by number of prior appearances in this assessment
        appearance_count = used_ids_str.count(str(concept.id))
        if appearance_count > 0:
            weight = weight / (1.0 + (appearance_count * 2.0))

        weights.append(max(weight, 0.05))

    # Probabilistic selection
    total = sum(weights)
    probs = [w / total for w in weights]

    selected_concept = random.choices(candidate_pool, weights=probs, k=1)[0]
    mastery_score = mastery_map.get(selected_concept.id, 50.0)
    difficulty = _map_mastery_to_difficulty(mastery_score)

    return selected_concept, mastery_score, difficulty


from app.ai.quiz_service import (
    generate_grounded_adaptive_question,
    evaluate_open_ended_with_grounding,
    QuestionStrategy,
)


async def _generate_question(
    concept: Concept,
    difficulty: int,
    question_type: QuestionType,
    project: Project,
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    existing_questions: Optional[List[str]] = None,
    used_strategies: Optional[List[Any]] = None,
    concept_used_strategies: Optional[List[Any]] = None,
) -> dict:
    """
    Generate a grounded quiz question using the quality quiz service.
    """
    return await generate_grounded_adaptive_question(
        db=db,
        concept=concept,
        difficulty=difficulty,
        question_type=question_type,
        project_id=project_id,
        user_id=user_id,
        project_name=project.name,
        learning_goal=project.learning_goal,
        assessment_existing_questions=existing_questions or [],
        used_strategies=used_strategies or [],
        concept_used_strategies=concept_used_strategies,
    )


async def _evaluate_open_ended(
    question_text: str,
    correct_answer: str,
    user_answer: str,
    concept_name: str,
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
) -> dict:
    """
    AI evaluation of open-ended answers with RAG source grounding.
    """
    return await evaluate_open_ended_with_grounding(
        db=db,
        question_text=question_text,
        model_answer=correct_answer,
        user_answer=user_answer,
        concept_name=concept_name,
        user_id=user_id,
        project_id=project_id,
    )


@router.post("/spaces/{space_id}/projects/{project_id}/quiz/start",
             response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def start_quiz(
    space_id: UUID,
    project_id: UUID,
    body: QuizStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Start a new adaptive quiz session and return the first question."""
    project = await _verify_project_access(project_id, current_user.id, db)

    # Check if there are any concepts to quiz on
    concepts_count = await db.execute(
        select(func.count(Concept.id)).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        )
    )
    if (concepts_count.scalar() or 0) == 0:
        raise HTTPException(
            status_code=400,
            detail="No concepts available. Please upload and process learning materials first."
        )

    total_questions = body.length or settings.DEFAULT_QUIZ_LENGTH

    # Create assessment session
    assessment = Assessment(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=current_user.id,
        status=AssessmentStatus.in_progress,
        total_questions=total_questions,
        correct_count=0,
    )
    db.add(assessment)

    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        project_id=project_id,
        event_type="quiz_started",
        payload={"assessment_id": str(assessment.id), "total_questions": total_questions},
    )
    db.add(event)
    await db.flush()

    # Generate first question adaptively
    concept, mastery_score, difficulty = await _select_adaptive_concept(
        db, project_id, current_user.id, used_concept_ids=[]
    )

    if not concept:
        raise HTTPException(status_code=400, detail="Could not select a concept for the quiz")

    question_type = QuestionType.mcq  # First question always MCQ
    question_data = await _generate_question(concept, difficulty, question_type, project, db, current_user.id, project_id)

    question = Question(
        id=uuid.uuid4(),
        assessment_id=assessment.id,
        concept_id=concept.id,
        question_type=question_type,
        difficulty=difficulty,
        question_text=question_data["question_text"],
        options=question_data.get("options"),
        correct_answer=question_data["correct_answer"],
        explanation=question_data["explanation"],
    )
    db.add(question)
    project.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    return QuestionOut(
        id=question.id,
        assessment_id=assessment.id,
        question_type=question_type.value,
        difficulty=difficulty,
        question_text=question.question_text,
        options=question.options,
        question_number=1,
        total_questions=total_questions,
    )


@router.post("/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/answer/{question_id}",
             response_model=AnswerResultOut)
async def submit_answer(
    space_id: UUID,
    project_id: UUID,
    assessment_id: UUID,
    question_id: UUID,
    body: AnswerSubmitRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Submit answer and get next question (or completion if done)."""
    await _verify_project_access(project_id, current_user.id, db)

    # Verify assessment ownership
    assessment_result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if assessment.status == AssessmentStatus.completed:
        raise HTTPException(status_code=400, detail="Assessment already completed")

    # Get the question
    question_result = await db.execute(
        select(Question).where(
            Question.id == question_id,
            Question.assessment_id == assessment_id,
        )
    )
    question = question_result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Check if question is already answered via explicit query
    existing_ans_result = await db.execute(
        select(Answer).where(Answer.question_id == question_id)
    )
    if existing_ans_result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Question already answered")

    # Evaluate the answer
    is_correct = None
    ai_score = None
    feedback = None
    understood = []
    missing = []
    misconceptions_list = []

    if question.question_type == QuestionType.mcq:
        # Exact match for MCQ (case-insensitive)
        is_correct = body.answer.strip().lower() == (question.correct_answer or "").strip().lower()
        ai_score = 1.0 if is_correct else 0.0
        feedback = question.explanation or ("Correct!" if is_correct else f"The correct answer is: {question.correct_answer}")
    else:
        # AI evaluation for open-ended
        concept = None
        if question.concept_id:
            concept_result = await db.execute(select(Concept).where(Concept.id == question.concept_id))
            concept = concept_result.scalar_one_or_none()

        eval_result = await _evaluate_open_ended(
            question_text=question.question_text,
            correct_answer=question.correct_answer or "",
            user_answer=body.answer,
            concept_name=concept.name if concept else "this concept",
            db=db,
            user_id=current_user.id,
            project_id=project_id,
        )
        ai_score = eval_result["score"]
        is_correct = ai_score >= 0.6
        feedback = eval_result["feedback"]
        understood = eval_result["understood_correctly"]
        missing = eval_result["missing_concepts"]
        misconceptions_list = eval_result["misconceptions"]

    # Save answer
    answer = Answer(
        id=uuid.uuid4(),
        question_id=question.id,
        user_id=current_user.id,
        user_answer=body.answer,
        is_correct=is_correct,
        ai_score=ai_score,
        ai_feedback=feedback,
        understood_correctly=understood,
        missing_concepts=missing,
        misconceptions=misconceptions_list,
        evaluated_at=datetime.now(timezone.utc),
    )
    db.add(answer)

    if is_correct:
        assessment.correct_count += 1

    # Track event
    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        project_id=project_id,
        event_type="question_answered",
        payload={
            "assessment_id": str(assessment_id),
            "question_id": str(question_id),
            "question_type": question.question_type.value,
            "is_correct": is_correct,
            "ai_score": ai_score,
        },
    )
    db.add(event)
    await db.flush()

    # Count answered questions via async queries
    all_qs_result = await db.execute(
        select(Question).where(Question.assessment_id == assessment_id)
    )
    all_questions = all_qs_result.scalars().all()
    answered_qs_result = await db.execute(
        select(Answer.question_id).where(Answer.question_id.in_([q.id for q in all_questions]))
    )
    answered_ids = set(answered_qs_result.scalars().all())
    total_answered = len(answered_ids)

    next_available = total_answered < assessment.total_questions

    # If quiz not complete, generate next question
    if next_available:
        project_result = await db.execute(select(Project).where(Project.id == project_id))
        project = project_result.scalar_one_or_none()

        # Get used concept IDs
        used_concept_ids = [
            str(q.concept_id) for q in all_questions
            if q.concept_id
        ]

        concept, mastery_score, difficulty = await _select_adaptive_concept(
            db, project_id, current_user.id, used_concept_ids=used_concept_ids
        )

        if concept and project:
            # Alternate between MCQ and open-ended
            next_type = QuestionType.open_ended if total_answered % 3 == 2 else QuestionType.mcq
            existing_q_texts = [q.question_text for q in all_questions if q.question_text]
            question_data = await _generate_question(
                concept=concept,
                difficulty=difficulty,
                question_type=next_type,
                project=project,
                db=db,
                user_id=current_user.id,
                project_id=project_id,
                existing_questions=existing_q_texts,
            )

            next_q = Question(
                id=uuid.uuid4(),
                assessment_id=assessment_id,
                concept_id=concept.id,
                question_type=next_type,
                difficulty=difficulty,
                question_text=question_data["question_text"],
                options=question_data.get("options"),
                correct_answer=question_data["correct_answer"],
                explanation=question_data["explanation"],
            )
            db.add(next_q)
    else:
        # Complete the assessment
        assessment.status = AssessmentStatus.completed
        assessment.completed_at = datetime.now(timezone.utc)
        total_q = assessment.total_questions or 1
        assessment.score_pct = (assessment.correct_count / total_q) * 100

        complete_event = Event(
            id=uuid.uuid4(),
            user_id=current_user.id,
            project_id=project_id,
            event_type="quiz_completed",
            payload={
                "assessment_id": str(assessment_id),
                "score_pct": assessment.score_pct,
                "correct": assessment.correct_count,
                "total": assessment.total_questions,
            },
        )
        db.add(complete_event)

        # Trigger learning workflow asynchronously
        from app.workers.learning_workflow import process_quiz_completion
        process_quiz_completion.delay(
            assessment_id=str(assessment_id),
            user_id=str(current_user.id),
            project_id=str(project_id),
        )

    await db.commit()

    return AnswerResultOut(
        question_id=question.id,
        is_correct=is_correct,
        ai_score=ai_score,
        ai_feedback=feedback,
        understood_correctly=understood,
        missing_concepts=missing,
        correct_answer=question.correct_answer if not is_correct else None,
        explanation=question.explanation,
        next_question_available=next_available,
    )


@router.get("/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}/next",
            response_model=Optional[QuestionOut])
async def get_next_question(
    space_id: UUID,
    project_id: UUID,
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get the next unanswered question in an assessment."""
    await _verify_project_access(project_id, current_user.id, db)

    assessment_result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    if assessment.status == AssessmentStatus.completed:
        return None

    # Find unanswered question
    questions_result = await db.execute(
        select(Question).where(Question.assessment_id == assessment_id).order_by(Question.created_at)
    )
    questions = questions_result.scalars().all()
    if not questions:
        return None

    answered_res = await db.execute(
        select(Answer.question_id).where(Answer.question_id.in_([q.id for q in questions]))
    )
    answered_ids = set(answered_res.scalars().all())
    unanswered = [q for q in questions if q.id not in answered_ids]

    if not unanswered:
        return None

    next_q = unanswered[0]
    question_number = len(answered_ids) + 1

    return QuestionOut(
        id=next_q.id,
        assessment_id=assessment_id,
        question_type=next_q.question_type.value,
        difficulty=next_q.difficulty,
        question_text=next_q.question_text,
        options=next_q.options,
        question_number=question_number,
        total_questions=assessment.total_questions,
    )


@router.get("/spaces/{space_id}/projects/{project_id}/quiz/{assessment_id}",
            response_model=AssessmentOut)
async def get_assessment(
    space_id: UUID,
    project_id: UUID,
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_project_access(project_id, current_user.id, db)
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


# ──────────────────────────────────────────────
# Direct / Simplified Quiz Routes
# ──────────────────────────────────────────────
from fastapi import Query
from pydantic import BaseModel
from typing import Any
import asyncio


class DirectQuizAnswerRequest(BaseModel):
    question_id: UUID
    selected_option: Optional[Any] = None
    open_ended_answer: Optional[str] = None


@router.post("/quiz/start")
async def start_adaptive_quiz_direct(
    project_id: UUID = Query(...),
    question_count: int = Query(5),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Start an adaptive quiz with questions generated up front."""
    project = await _verify_project_access(project_id, current_user.id, db)

    # Get available concepts
    concepts_result = await db.execute(
        select(Concept).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        )
    )
    concepts = concepts_result.scalars().all()

    total_q = min(max(question_count, 1), 10)

    assessment = Assessment(
        id=uuid.uuid4(),
        project_id=project_id,
        user_id=current_user.id,
        status=AssessmentStatus.in_progress,
        total_questions=total_q,
        correct_count=0,
    )
    db.add(assessment)
    await db.flush()

    used_concept_ids = []
    concept_strategies_map = {}
    assessment_existing_questions = []
    used_strategies = []
    questions_out = []

    for i in range(total_q):
        concept, score, difficulty = await _select_adaptive_concept(
            db, project_id, current_user.id, used_concept_ids
        )
        concept_prev_strategies = []
        if concept:
            used_concept_ids.append(concept.id)
            cid_str = str(concept.id)
            concept_prev_strategies = concept_strategies_map.get(cid_str, [])

        # Diverse question type distribution (e.g. MCQ primarily, with open-ended strategically interspersed)
        q_type = QuestionType.open_ended if (i % 3 == 2 and concept) else QuestionType.mcq

        if concept:
            q_data = await generate_grounded_adaptive_question(
                db=db,
                concept=concept,
                difficulty=difficulty,
                question_type=q_type,
                project_id=project_id,
                user_id=current_user.id,
                project_name=project.name,
                learning_goal=project.learning_goal,
                assessment_existing_questions=assessment_existing_questions,
                used_strategies=used_strategies,
                concept_used_strategies=concept_prev_strategies,
            )
            assessment_existing_questions.append(q_data["question_text"])
            if "strategy" in q_data:
                used_strategies.append(q_data["strategy"])
                concept_strategies_map.setdefault(cid_str, []).append(q_data["strategy"])
        else:
            # Fallback question if no concept extracted yet
            q_data = {
                "question_text": f"Explain the core database mechanisms related to {project.learning_goal or project.name}.",
                "options": [
                    f"Core data management and relational integrity rules in {project.name}.",
                    f"Temporary memory buffer configuration protocol.",
                    f"Automated client-side rendering engine.",
                    f"Unindexed filesystem directory structure."
                ] if q_type == QuestionType.mcq else None,
                "correct_answer": f"Core data management and relational integrity rules in {project.name}." if q_type == QuestionType.mcq else f"Clear explanation of {project.name}",
                "explanation": f"Understanding fundamental concepts of {project.name}.",
                "strategy": "concept_understanding",
            }
            assessment_existing_questions.append(q_data["question_text"])

        q = Question(
            id=uuid.uuid4(),
            assessment_id=assessment.id,
            concept_id=concept.id if concept else None,
            question_type=q_type,
            difficulty=difficulty,
            question_text=q_data["question_text"],
            options=q_data.get("options"),
            correct_answer=q_data.get("correct_answer"),
            explanation=q_data.get("explanation"),
        )
        db.add(q)
        questions_out.append({
            "id": str(q.id),
            "question_type": q_type.value,
            "difficulty": difficulty,
            "question_text": q.question_text,
            "options": q.options,
            "concept_name": concept.name if concept else project.name,
            "strategy": q_data.get("strategy"),
        })

    project.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "id": str(assessment.id),
        "project_id": str(project.id),
        "status": assessment.status.value,
        "total_questions": total_q,
        "questions": questions_out,
    }


@router.get("/quiz/{assessment_id}")
async def get_quiz_direct(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Quiz not found")

    qs_result = await db.execute(
        select(Question).where(Question.assessment_id == assessment_id).order_by(Question.created_at.asc())
    )
    questions = qs_result.scalars().all()

    return {
        "id": str(assessment.id),
        "project_id": str(assessment.project_id),
        "status": assessment.status.value,
        "total_questions": assessment.total_questions,
        "correct_count": assessment.correct_count,
        "score_pct": assessment.score_pct,
        "questions": [
            {
                "id": str(q.id),
                "question_type": q.question_type.value,
                "difficulty": q.difficulty,
                "question_text": q.question_text,
                "options": q.options,
            }
            for q in questions
        ],
    }


@router.post("/quiz/{assessment_id}/answer")
async def submit_quiz_answer_direct(
    assessment_id: UUID,
    body: DirectQuizAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct answer endpoint matching frontend quizApi."""
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Quiz not found")

    q_res = await db.execute(
        select(Question).where(
            Question.id == body.question_id,
            Question.assessment_id == assessment_id,
        )
    )
    question = q_res.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    is_correct = False
    ai_score = 0.0
    feedback = ""
    understood = []
    missing = []
    misconceptions = []
    user_answer_text = ""

    if question.question_type == QuestionType.mcq:
        # Check option index or text
        user_choice = body.selected_option
        if isinstance(user_choice, int) and question.options and 0 <= user_choice < len(question.options):
            user_answer_text = question.options[user_choice]
        else:
            user_answer_text = str(user_choice or "")

        correct_ans = question.correct_answer or ""
        # Check exact string or matching index
        is_correct = (
            user_answer_text.strip().lower() == correct_ans.strip().lower() or
            (isinstance(user_choice, int) and question.options and correct_ans in question.options and question.options.index(correct_ans) == user_choice)
        )
        ai_score = 1.0 if is_correct else 0.0
        feedback = question.explanation or ("Correct! Great job." if is_correct else f"The correct answer is: {correct_ans}")
        if is_correct:
            understood = ["Core concept definition"]
        else:
            missing = ["Correct choice identification"]
    else:
        user_answer_text = body.open_ended_answer or ""
        concept = None
        if question.concept_id:
            c_res = await db.execute(select(Concept).where(Concept.id == question.concept_id))
            concept = c_res.scalar_one_or_none()

        eval_res = await _evaluate_open_ended(
            question_text=question.question_text,
            correct_answer=question.correct_answer or "",
            user_answer=user_answer_text,
            concept_name=concept.name if concept else "this topic",
            db=db,
            user_id=current_user.id,
            project_id=assessment.project_id,
        )
        ai_score = eval_res.get("score", 0.5)
        is_correct = ai_score >= 0.6
        feedback = eval_res.get("feedback", "")
        understood = eval_res.get("understood_correctly", [])
        missing = eval_res.get("missing_concepts", [])
        misconceptions = eval_res.get("misconceptions", [])

    # Save or update answer
    ans_res = await db.execute(select(Answer).where(Answer.question_id == question.id))
    existing_ans = ans_res.scalar_one_or_none()
    if existing_ans:
        existing_ans.user_answer = user_answer_text
        existing_ans.is_correct = is_correct
        existing_ans.ai_score = ai_score
        existing_ans.ai_feedback = feedback
        existing_ans.understood_correctly = understood
        existing_ans.missing_concepts = missing
        existing_ans.misconceptions = misconceptions
        existing_ans.evaluated_at = datetime.now(timezone.utc)
    else:
        ans = Answer(
            id=uuid.uuid4(),
            question_id=question.id,
            user_id=current_user.id,
            user_answer=user_answer_text,
            is_correct=is_correct,
            ai_score=ai_score,
            ai_feedback=feedback,
            understood_correctly=understood,
            missing_concepts=missing,
            misconceptions=misconceptions,
            evaluated_at=datetime.now(timezone.utc),
        )
        db.add(ans)

    if is_correct:
        assessment.correct_count += 1

    await db.commit()

    return {
        "question_id": str(question.id),
        "is_correct": is_correct,
        "ai_score": ai_score,
        "ai_feedback": feedback,
        "correct_answer": question.correct_answer,
        "explanation": question.explanation,
        "understood_correctly": understood,
        "missing_concepts": missing,
        "misconceptions": misconceptions,
    }


@router.post("/quiz/{assessment_id}/complete")
async def complete_quiz_direct(
    assessment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Complete a quiz session and trigger post-quiz learning workflow."""
    result = await db.execute(
        select(Assessment).where(
            Assessment.id == assessment_id,
            Assessment.user_id == current_user.id,
        )
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=404, detail="Quiz not found")

    assessment.status = AssessmentStatus.completed
    assessment.completed_at = datetime.now(timezone.utc)
    if assessment.total_questions > 0:
        assessment.score_pct = (assessment.correct_count / assessment.total_questions) * 100.0
    else:
        assessment.score_pct = 0.0

    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        project_id=assessment.project_id,
        event_type="quiz_completed",
        payload={
            "assessment_id": str(assessment_id),
            "score_pct": assessment.score_pct,
            "correct_count": assessment.correct_count,
            "total_questions": assessment.total_questions,
        },
    )
    db.add(event)
    await db.commit()

    # Trigger post-quiz learning workflow (Celery or background thread fallback)
    dispatched = False
    try:
        from app.workers.learning_workflow import post_quiz_learning_workflow
        post_quiz_learning_workflow.delay(
            assessment_id=str(assessment.id),
            user_id=str(current_user.id),
            project_id=str(assessment.project_id),
        )
        dispatched = True
    except Exception as e:
        print(f"[quiz] Celery dispatch failed: {e}")

    if not dispatched:
        from app.workers.learning_workflow import execute_learning_workflow_sync
        asyncio.create_task(
            asyncio.to_thread(
                execute_learning_workflow_sync,
                str(assessment.id),
                str(current_user.id),
                str(assessment.project_id),
            )
        )

    return {
        "assessment_id": str(assessment.id),
        "score_pct": assessment.score_pct,
        "correct_count": assessment.correct_count,
        "total_questions": assessment.total_questions,
        "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
    }

