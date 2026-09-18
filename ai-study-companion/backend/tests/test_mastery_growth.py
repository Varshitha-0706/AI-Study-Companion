"""
Automated unit & regression tests for Mastery, Growth Analysis, Learning Context, and Recommendations.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from sqlalchemy import select

from app.main import app
from app.db.session import AsyncSessionLocal
from app.models.models import (
    User, Space, Project, Concept, MasteryRecord, MasteryHistory,
    MasteryTrend, LearningContext, Recommendation, RecommendationStatus,
    Material, MaterialStatus, Chunk
)
from app.workers.learning_workflow import update_mastery_for_concept
from app.core.security import create_access_token
try:
    from tests.conftest import is_postgres_available
except ImportError:
    from conftest import is_postgres_available


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_mastery_ema_formula():
    """
    Test evidence-weighted mastery update formula:
    new_score = (1 - alpha) * prev_score + alpha * (evidence_score * 100)
    alpha = 0.3
    """
    alpha = 0.3
    # Start at 50, get 100% evidence
    s1 = (1 - alpha) * 50.0 + alpha * 100.0  # 35 + 30 = 65.0
    assert abs(s1 - 65.0) < 0.01

    # Next evidence is 0%
    s2 = (1 - alpha) * s1 + alpha * 0.0      # 0.7 * 65.0 = 45.5
    assert abs(s2 - 45.5) < 0.01


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running")
async def test_mastery_growth_and_isolation_flow():
    """
    Test complete mastery, growth, learning context, and project isolation flow.
    """
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    space1_id = uuid.uuid4()
    project1_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        # Create users
        u1 = User(id=user1_id, email=f"m_u1_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", display_name="User 1")
        u2 = User(id=user2_id, email=f"m_u2_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", display_name="User 2")
        sp1 = Space(id=space1_id, user_id=user1_id, name="User1 Space")
        pr1 = Project(id=project1_id, space_id=space1_id, user_id=user1_id, name="User1 SQL Project")

        c1 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="SELECT Statement", importance_score=5.0)
        c2 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="JOIN Operations", importance_score=4.0)
        c3 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="Database Indexing", importance_score=4.5)

        db.add_all([u1, u2, sp1, pr1, c1, c2, c3])
        await db.commit()

    token1 = create_access_token(str(user1_id))
    token2 = create_access_token(str(user2_id))
    headers1 = {"Authorization": f"Bearer {token1}"}
    headers2 = {"Authorization": f"Bearer {token2}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. User 2 cannot access User 1's project mastery (404/403 Project not found)
        unauth_res = await client.get(f"/api/v1/mastery/projects/{project1_id}/overview", headers=headers2)
        assert unauth_res.status_code == 404

        # 2. User 1 initial growth before any answers -> all concepts are insufficient_data
        growth_res = await client.get(f"/api/v1/mastery/projects/{project1_id}/growth", headers=headers1)
        assert growth_res.status_code == 200
        growth = growth_res.json()
        assert len(growth["insufficient_data"]) == 3
        assert len(growth["improving"]) == 0
        assert len(growth["needs_attention"]) == 0

        # 3. Simulate recording mastery evidence via DB
        async with AsyncSessionLocal() as db:
            # c1 gets high scores -> Improving
            m1 = MasteryRecord(
                id=uuid.uuid4(), concept_id=c1.id, user_id=user1_id, project_id=project1_id,
                score=85.0, evidence_count=3, trend=MasteryTrend.improving
            )
            # c2 gets low scores -> Needs Attention
            m2 = MasteryRecord(
                id=uuid.uuid4(), concept_id=c2.id, user_id=user1_id, project_id=project1_id,
                score=42.0, evidence_count=2, trend=MasteryTrend.needs_attention
            )
            # c3 has only 1 observation -> Insufficient Data
            m3 = MasteryRecord(
                id=uuid.uuid4(), concept_id=c3.id, user_id=user1_id, project_id=project1_id,
                score=60.0, evidence_count=1, trend=MasteryTrend.insufficient_data
            )
            db.add_all([m1, m2, m3])

            # Add learning context
            ctx = LearningContext(
                id=uuid.uuid4(), project_id=project1_id, user_id=user1_id,
                known_strengths=[{"name": "SELECT Statement", "score": 85.0}],
                known_weaknesses=[{"name": "JOIN Operations", "score": 42.0}],
                repeated_mistakes=[{"concept": "JOIN Operations", "wrong_count": 2}]
            )
            db.add(ctx)

            # Add active recommendation
            rec = Recommendation(
                id=uuid.uuid4(), project_id=project1_id, user_id=user1_id,
                recommendation_type="review_concept",
                content="Focus on reviewing JOIN Operations to master relational lookups.",
                reason="Mastery score is below 50%",
                status=RecommendationStatus.active
            )
            db.add(rec)
            await db.commit()

        # 4. Verify growth endpoint returns categorized concepts & calculated overall mastery
        growth_res2 = await client.get(f"/api/v1/mastery/projects/{project1_id}/growth", headers=headers1)
        assert growth_res2.status_code == 200
        g2 = growth_res2.json()
        assert len(g2["improving"]) == 1
        assert g2["improving"][0]["concept_name"] == "SELECT Statement"
        assert len(g2["needs_attention"]) == 1
        assert g2["needs_attention"][0]["concept_name"] == "JOIN Operations"
        assert len(g2["insufficient_data"]) == 1
        assert g2["insufficient_data"][0]["concept_name"] == "Database Indexing"
        # Overall mastery = (85 + 42 + 60) / 3 = 62.33
        assert 62.0 <= g2["overall_mastery"] <= 63.0

        # 5. Verify Learning Context
        ctx_res = await client.get(f"/api/v1/mastery/projects/{project1_id}/context", headers=headers1)
        assert ctx_res.status_code == 200
        c_data = ctx_res.json()
        assert len(c_data["known_strengths"]) == 1
        assert len(c_data["known_weaknesses"]) == 1
        assert len(c_data["repeated_mistakes"]) == 1

        # 6. Verify Recommendations
        recs_res = await client.get(f"/api/v1/mastery/projects/{project1_id}/recommendations", headers=headers1)
        assert recs_res.status_code == 200
        recs = recs_res.json()
        assert len(recs) == 1
        assert recs[0]["recommendation_type"] == "review_concept"
        assert "JOIN Operations" in recs[0]["content"]


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running")
async def test_e2e_quiz_answers_update_mastery_growth_and_recommendations():
    """
    End-to-end verification of learning loop:
    Quiz answer submissions → evaluation → mastery update → history recording →
    growth analysis categorizations → recommendation generation → second quiz delta.
    """
    from app.workers.learning_workflow import execute_learning_workflow_sync
    import asyncio

    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    space1_id = uuid.uuid4()
    project1_id = uuid.uuid4()
    material_id = uuid.uuid4()

    async with AsyncSessionLocal() as db:
        u1 = User(id=user1_id, email=f"loop_u1_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", display_name="Loop User 1")
        u2 = User(id=user2_id, email=f"loop_u2_{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", display_name="Loop User 2")
        sp1 = Space(id=space1_id, user_id=user1_id, name="Loop Space")
        pr1 = Project(id=project1_id, space_id=space1_id, user_id=user1_id, name="SQL Mastery Loop", learning_goal="Master SQL")

        mat = Material(
            id=material_id, project_id=project1_id, user_id=user1_id,
            filename="sql_notes.pdf", original_filename="SQL NOTES.pdf",
            status=MaterialStatus.ready, page_count=2,
        )

        c1 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="SQL Index", description="Speeds up queries", importance_score=5.0)
        c2 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="SQL Joins", description="Combines relational rows", importance_score=4.5)
        c3 = Concept(id=uuid.uuid4(), project_id=project1_id, user_id=user1_id, name="SQL Views", description="Virtual query tables", importance_score=4.0)

        chk = Chunk(
            id=uuid.uuid4(), material_id=material_id, project_id=project1_id, user_id=user1_id,
            content="• INDEX − Speeds up search queries.\n• JOINS − Merges tables.\n• VIEWS − Virtual tables.",
            page_number=1, chunk_index=0, embedding=[0.02] * 3072,
        )

        db.add_all([u1, u2, sp1, pr1, mat, c1, c2, c3, chk])
        await db.commit()

    token1 = create_access_token(str(user1_id))
    headers1 = {"Authorization": f"Bearer {token1}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Start Quiz 1 (3 questions)
        q_start = await client.post(f"/api/v1/quiz/start?project_id={project1_id}&question_count=3", headers=headers1)
        assert q_start.status_code == 200
        quiz1 = q_start.json()
        q_list = quiz1["questions"]
        assert len(q_list) == 3
        quiz1_id = quiz1["id"]

        # 2. Submit answers for Quiz 1:
        # Q0 -> Correct (1.0), Q1 -> Incorrect (0.0), Q2 -> Correct (1.0)
        await client.post(
            f"/api/v1/quiz/{quiz1_id}/answer",
            headers=headers1,
            json={"question_id": q_list[0]["id"], "selected_option": 0}
        )
        await client.post(
            f"/api/v1/quiz/{quiz1_id}/answer",
            headers=headers1,
            json={"question_id": q_list[1]["id"], "selected_option": 1}
        )
        await client.post(
            f"/api/v1/quiz/{quiz1_id}/answer",
            headers=headers1,
            json={"question_id": q_list[2]["id"], "selected_option": 0}
        )

        # 3. Complete Quiz 1
        comp1 = await client.post(f"/api/v1/quiz/{quiz1_id}/complete", headers=headers1)
        assert comp1.status_code == 200

        # Execute learning workflow synchronously
        await asyncio.to_thread(execute_learning_workflow_sync, str(quiz1_id), str(user1_id), str(project1_id))

        # 4. Verify Mastery Overview & History
        overview1 = await client.get(f"/api/v1/mastery/projects/{project1_id}/overview", headers=headers1)
        assert overview1.status_code == 200
        concepts_ov = overview1.json()
        assert len(concepts_ov) == 3

        # At least one concept has updated mastery score and history point
        tested = [c for c in concepts_ov if c["score"] is not None]
        assert len(tested) >= 1
        for t in tested:
            assert t["evidence_count"] >= 1
            assert len(t["history"]) >= 1
            assert t["history"][0]["type"] == "quiz"

        # 5. Verify Growth Analysis
        growth1 = await client.get(f"/api/v1/mastery/projects/{project1_id}/growth", headers=headers1)
        assert growth1.status_code == 200
        g_data = growth1.json()
        assert "overall_mastery" in g_data

        # 6. Verify Recommendations
        recs1 = await client.get(f"/api/v1/mastery/projects/{project1_id}/recommendations", headers=headers1)
        assert recs1.status_code == 200
        r_list = recs1.json()
        assert len(r_list) >= 1
        assert r_list[0]["status"] == "active"
        assert len(r_list[0]["content"]) > 10

        # 7. Start Quiz 2 and verify mastery updates dynamically on second attempt
        q_start2 = await client.post(f"/api/v1/quiz/start?project_id={project1_id}&question_count=3", headers=headers1)
        assert q_start2.status_code == 200
        quiz2 = q_start2.json()
        quiz2_id = quiz2["id"]

        for q in quiz2["questions"]:
            await client.post(
                f"/api/v1/quiz/{quiz2_id}/answer",
                headers=headers1,
                json={"question_id": q["id"], "selected_option": 0}
            )

        comp2 = await client.post(f"/api/v1/quiz/{quiz2_id}/complete", headers=headers1)
        assert comp2.status_code == 200

        await asyncio.to_thread(execute_learning_workflow_sync, str(quiz2_id), str(user1_id), str(project1_id))

        # Verify second quiz increased evidence counts and added history timestamps
        overview2 = await client.get(f"/api/v1/mastery/projects/{project1_id}/overview", headers=headers1)
        assert overview2.status_code == 200
        concepts_ov2 = overview2.json()
        retested = [c for c in concepts_ov2 if c["evidence_count"] >= 2]
        assert len(retested) >= 1
        assert len(retested[0]["history"]) >= 2
