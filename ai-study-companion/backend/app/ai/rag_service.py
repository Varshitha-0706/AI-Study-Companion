import uuid
import re
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.models import Chunk, Material
from app.ai.gemini_client import gemini_client
from app.core.config import settings

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "and", "or", "but", "if", "then", "else", "when", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "can", "will", "just", "should", "now", "what", "which", "who", "whom",
    "this", "that", "these", "those", "am", "it", "its", "used", "use", "using",
    "explain", "describe", "tell", "me", "about", "please", "give", "example"
}


class RetrievalResult:
    def __init__(self, chunk_id: str, content: str, page_number: int,
                 source_filename: str, similarity: float):
        self.chunk_id = chunk_id
        self.content = content
        self.page_number = page_number
        self.source_filename = source_filename
        self.similarity = similarity

    def to_dict(self) -> dict:
        return {
            "chunk_id": str(self.chunk_id),
            "content": self.content,
            "page_number": self.page_number,
            "source": self.source_filename,
            "similarity": self.similarity,
        }


def extract_salient_terms(query: str) -> list[str]:
    """Extract non-stopword alphanumeric terms of length >= 2."""
    raw_tokens = re.findall(r'[a-zA-Z0-9_\-\+]+', query.lower())
    return [t for t in raw_tokens if t not in STOP_WORDS and len(t) >= 2]


def get_term_variations(term: str) -> list[str]:
    """Generate simple morphological variations (singular, plural, suffixes)."""
    variations = {term}
    if term.endswith("ies") and len(term) > 3:
        variations.add(term[:-3] + "y")
    elif term.endswith("es") and len(term) > 3:
        variations.add(term[:-2])
        variations.add(term[:-1])
    elif term.endswith("s") and len(term) > 2:
        variations.add(term[:-1])
    else:
        variations.add(term + "s")
        variations.add(term + "es")
    return list(variations)


def compute_lexical_score(content: str, terms: list[str]) -> tuple[float, int]:
    """
    Compute lexical relevance score in [0.0, 1.0] and matched term count.
    Awards bonus for definition patterns, headings, and bullet points.
    """
    if not terms:
        return 0.0, 0

    content_lower = content.lower()
    matched_terms = 0
    total_score = 0.0

    for term in terms:
        variations = get_term_variations(term)
        var_pattern = r'\b(?:' + '|'.join(re.escape(v) for v in variations) + r')\b'
        matches = len(re.findall(var_pattern, content_lower))
        if matches > 0:
            matched_terms += 1
            term_score = min(0.65, 0.35 + (matches * 0.1))

            # Bonus for definition/heading pattern e.g. "• index -", "INDEX −", "index:", "index is"
            def_pattern = (
                r'(?:[•\*\-]\s*|\b)(?:' +
                '|'.join(re.escape(v) for v in variations) +
                r')(?:\s*[:\-\u2013\u2014\u2212]\s*|\s+is\s+|\s+are\s+|\s+means\s+|\s+used\s+to\s+|\s+command|\s+statement|\s+clause)'
            )
            if re.search(def_pattern, content_lower):
                term_score += 0.45

            total_score += term_score

    term_coverage = matched_terms / len(terms)
    raw_lexical = (total_score / len(terms)) * 0.7 + (term_coverage * 0.3)
    return min(1.0, raw_lexical), matched_terms


async def retrieve_relevant_chunks(
    db: AsyncSession,
    query: str,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    top_k: Optional[int] = None,
) -> tuple[list[RetrievalResult], float]:
    """
    Hybrid semantic + keyword retrieval with lexical re-ranking.

    SECURITY: project_id AND user_id are strictly applied to all SQL queries.
    Never exposes chunks across project or user boundaries.

    Returns (results, best_similarity).
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    salient_terms = extract_salient_terms(query)

    # 1. Generate query embedding
    query_embedding = gemini_client.embed(query)

    # 2. Retrieve top semantic candidates via pgvector cosine distance
    semantic_stmt = text("""
        SELECT
            c.id,
            c.content,
            c.page_number,
            m.original_filename,
            1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM chunks c
        JOIN materials m ON c.material_id = m.id
        WHERE
            c.project_id = :project_id
            AND c.user_id = :user_id
            AND m.status = 'ready'
            AND c.embedding IS NOT NULL
        ORDER BY c.embedding <=> CAST(:embedding AS vector)
        LIMIT 25
    """)

    sem_res = await db.execute(semantic_stmt, {
        "embedding": str(query_embedding),
        "project_id": str(project_id),
        "user_id": str(user_id),
    })
    rows = sem_res.fetchall()

    candidate_dict = {r[0]: r for r in rows}

    # 3. Retrieve keyword match candidates for salient terms to prevent vocabulary mismatch
    if salient_terms:
        kw_conditions = " OR ".join([f"c.content ILIKE :t_{i}" for i in range(len(salient_terms))])
        kw_stmt = text(f"""
            SELECT
                c.id,
                c.content,
                c.page_number,
                m.original_filename,
                1 - (c.embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM chunks c
            JOIN materials m ON c.material_id = m.id
            WHERE
                c.project_id = :project_id
                AND c.user_id = :user_id
                AND m.status = 'ready'
                AND ({kw_conditions})
            LIMIT 15
        """)
        params = {
            "embedding": str(query_embedding),
            "project_id": str(project_id),
            "user_id": str(user_id),
        }
        for i, term in enumerate(salient_terms):
            params[f"t_{i}"] = f"%{term}%"

        try:
            kw_res = await db.execute(kw_stmt, params)
            for kr in kw_res.fetchall():
                if kr[0] not in candidate_dict:
                    candidate_dict[kr[0]] = kr
        except Exception:
            pass

    candidate_rows = list(candidate_dict.values())
    if not candidate_rows:
        return [], 0.0

    # 4. Score and re-rank candidates
    scored = []
    for row in candidate_rows:
        chunk_id, content, page_num, filename, vec_sim = (
            row[0], row[1], row[2], row[3], float(row[4])
        )
        lex_score, matched_count = compute_lexical_score(content, salient_terms)

        if salient_terms:
            if matched_count > 0:
                hybrid_score = (0.55 * vec_sim) + (0.45 * lex_score)
            else:
                hybrid_score = vec_sim * 0.75
        else:
            hybrid_score = vec_sim

        scored.append((chunk_id, content, page_num, filename, hybrid_score))

    # Sort descending by hybrid score
    scored.sort(key=lambda x: x[4], reverse=True)

    results = [
        RetrievalResult(
            chunk_id=s[0],
            content=s[1],
            page_number=s[2],
            source_filename=s[3],
            similarity=s[4],
        )
        for s in scored[:top_k]
    ]

    best_similarity = results[0].similarity if results else 0.0

    # If query had salient terms but zero were found across all chunks, or best score is very low
    if salient_terms and scored[0][4] < 0.45:
        return [], 0.0

    return results, best_similarity
