"""
Automated regression tests for RAG retrieval quality and grounding.
Verifies that:
1. Queries targeting specific technical terms (e.g. 'Index in SQL') prioritize chunks defining Index over general/unrelated chunks (e.g. 'Views').
2. Unsupported queries correctly return insufficient evidence without hallucination.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.models import User, Space, Project, Material, Chunk, MaterialStatus
from app.ai.rag_service import retrieve_relevant_chunks, extract_salient_terms, compute_lexical_score
from app.ai.gemini_client import gemini_client
from conftest import is_postgres_available


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_salient_term_extraction():
    query = "What is an Index in SQL, and why is it used?"
    terms = extract_salient_terms(query)
    assert "index" in terms
    assert "sql" in terms
    assert "what" not in terms
    assert "is" not in terms
    assert "and" not in terms
    assert "why" not in terms


def test_lexical_scoring_prioritizes_definitions():
    terms = ["index", "sql"]

    # Chunk with definition of Index in SQL
    index_def = "• INDEX − Used to create and retrieve data in SQL database very quickly. Indexes improve performance."
    # Chunk about SQL Views (mentions SQL multiple times but zero index)
    views_chunk = "SQL Views SQL CREATE VIEW Statement. A view is a virtual table based on the result-set of an SQL statement."

    index_score, index_matches = compute_lexical_score(index_def, terms)
    views_score, views_matches = compute_lexical_score(views_chunk, terms)

    assert index_matches == 2
    assert index_score > views_score
    assert views_matches == 1  # only 'sql' matches


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running")
async def test_rag_retrieval_prioritizes_index_over_views():
    """
    Regression Test:
    When chunks exist for both 'Index' and 'Views', a query for 'Index in SQL'
    must prioritize the Index chunk and rank it above the Views chunk.
    """
    test_user_id = uuid.uuid4()
    test_space_id = uuid.uuid4()
    test_project_id = uuid.uuid4()
    test_material_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        # Create test user, space, project, material
        user = User(
            id=test_user_id,
            email=f"rag_test_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_dummy_pw",
            display_name="RAG Tester",
        )
        space = Space(id=test_space_id, user_id=test_user_id, name="Test Space")
        project = Project(id=test_project_id, space_id=test_space_id, user_id=test_user_id, name="SQL RAG Test")
        material = Material(
            id=test_material_id,
            project_id=test_project_id,
            user_id=test_user_id,
            original_filename="test_sql_doc.pdf",
            filename="/tmp/test.pdf",
            status=MaterialStatus.ready,
            page_count=2,
        )
        db.add_all([user, space, project, material])
        await db.flush()

        # Chunk 1: Index definition
        chunk1_text = "• INDEX − Used to create and retrieve data from the database very quickly. Constraints in SQL."
        chunk1_emb = gemini_client.embed(chunk1_text)
        chunk1 = Chunk(
            id=uuid.uuid4(),
            material_id=test_material_id,
            project_id=test_project_id,
            user_id=test_user_id,
            content=chunk1_text,
            page_number=37,
            chunk_index=0,
            embedding=chunk1_emb,
        )

        # Chunk 2: SQL Views (unrelated to Index)
        chunk2_text = "SQL Views SQL CREATE VIEW Statement In SQL, a view is a virtual table based on the result-set of an SQL statement."
        chunk2_emb = gemini_client.embed(chunk2_text)
        chunk2 = Chunk(
            id=uuid.uuid4(),
            material_id=test_material_id,
            project_id=test_project_id,
            user_id=test_user_id,
            content=chunk2_text,
            page_number=56,
            chunk_index=1,
            embedding=chunk2_emb,
        )

        db.add_all([chunk1, chunk2])
        await db.commit()

        # Query for Index
        query = "What is an Index in SQL, and why is it used?"
        results, best_sim = await retrieve_relevant_chunks(
            db=db,
            query=query,
            project_id=test_project_id,
            user_id=test_user_id,
            top_k=5,
        )

        assert len(results) > 0, "Expected retrieved chunks"
        top_chunk = results[0]
        assert top_chunk.page_number == 37, f"Expected page 37 (Index), got page {top_chunk.page_number}"
        assert "INDEX" in top_chunk.content or "index" in top_chunk.content.lower()
        assert best_sim >= 0.50, f"Expected similarity >= 0.50, got {best_sim}"


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running")
async def test_rag_retrieval_unsupported_query_insufficient_evidence():
    """
    Regression Test:
    Unsupported queries with unrelated concepts must return insufficient evidence.
    """
    test_user_id = uuid.uuid4()
    test_space_id = uuid.uuid4()
    test_project_id = uuid.uuid4()
    test_material_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        user = User(
            id=test_user_id,
            email=f"rag_unsup_{uuid.uuid4().hex[:6]}@example.com",
            hashed_password="hashed_dummy_pw",
            display_name="RAG Tester Unsup",
        )
        space = Space(id=test_space_id, user_id=test_user_id, name="Test Space")
        project = Project(id=test_project_id, space_id=test_space_id, user_id=test_user_id, name="SQL RAG Test 2")
        material = Material(
            id=test_material_id,
            project_id=test_project_id,
            user_id=test_user_id,
            original_filename="test_sql_doc.pdf",
            filename="/tmp/test.pdf",
            status=MaterialStatus.ready,
            page_count=1,
        )
        db.add_all([user, space, project, material])
        await db.flush()

        chunk_text = "SQL Commands: DDL, DML, DCL, TCL, DQL. Structured Query Language is used for relational databases."
        chunk_emb = gemini_client.embed(chunk_text)
        chunk = Chunk(
            id=uuid.uuid4(),
            material_id=test_material_id,
            project_id=test_project_id,
            user_id=test_user_id,
            content=chunk_text,
            page_number=1,
            chunk_index=0,
            embedding=chunk_emb,
        )
        db.add(chunk)
        await db.commit()

        # Completely unrelated question
        unsupported_query = "What is the biological lifecycle of a monarch butterfly?"
        results, best_sim = await retrieve_relevant_chunks(
            db=db,
            query=unsupported_query,
            project_id=test_project_id,
            user_id=test_user_id,
            top_k=5,
        )

        assert len(results) == 0 or best_sim < 0.50, f"Expected insufficient evidence, got score {best_sim}"
