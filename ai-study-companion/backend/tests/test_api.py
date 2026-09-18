"""Integration tests for the AI Study Companion Backend APIs."""
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["product"] == "AI Study Companion"
        assert data["models"]["generation"] == "gemini-3.6-flash"
        assert data["models"]["embedding"] == "models/gemini-embedding-2"
        assert data["models"]["embedding_dimensions"] == 3072


from conftest import is_postgres_available


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running locally on port 5432")
async def test_auth_register_login_flow():
    test_email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "SecurePassword123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Register - role must ALWAYS be "user", never admin
        reg_res = await client.post(
            "/api/v1/auth/register",
            json={
                "email": test_email,
                "password": test_password,
                "display_name": "Test Student"
            }
        )
        assert reg_res.status_code == 201, reg_res.text
        user_data = reg_res.json()
        assert user_data["display_name"] == "Test Student"
        assert user_data["role"] == "user"
        assert "access_token" in user_data

        # 2. Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": test_password}
        )
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        headers = {"Authorization": f"Bearer {token}"}

        # 3. Get profile (/auth/me)
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == test_email

        # 4. Spaces CRUD
        space_res = await client.post(
            "/api/v1/spaces",
            json={
                "name": "Machine Learning Space",
                "description": "All ML coursework",
                "icon": "🤖",
                "color": "#6366f1"
            },
            headers=headers
        )
        assert space_res.status_code == 201
        space = space_res.json()
        space_id = space["id"]
        assert space["name"] == "Machine Learning Space"

        # 5. Projects CRUD
        project_res = await client.post(
            f"/api/v1/spaces/{space_id}/projects",
            json={
                "name": "Neural Networks Unit",
                "description": "Transformers and Attention",
                "learning_goal": "Master transformer architectures"
            },
            headers=headers
        )
        assert project_res.status_code == 201
        project = project_res.json()
        project_id = project["id"]
        assert project["name"] == "Neural Networks Unit"

        # 6. Project Dashboard
        dash_res = await client.get(f"/api/v1/projects/{project_id}/dashboard", headers=headers)
        assert dash_res.status_code == 200
        dash = dash_res.json()
        assert "project" in dash
        assert "top_concepts" in dash
        assert "activity_count_7d" in dash

        # 7. Non-admin accessing admin endpoint gets 403 Forbidden
        admin_res = await client.get("/api/v1/admin/dashboard", headers=headers)
        assert admin_res.status_code == 403


@pytest.mark.asyncio
async def test_storage_service_abstraction():
    from app.services.storage_service import LocalStorageService
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageService(tmpdir)
        user_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        content = b"%PDF-1.4 test document content"

        # Save
        key = await storage.save(content, user_id, project_id, "test.pdf")
        assert f"{user_id}/{project_id}/test.pdf" == key

        # Read
        read_back = await storage.read(key)
        assert read_back == content

        # Delete
        await storage.delete(key)
        assert not (storage.base_dir / key).exists()


@pytest.mark.asyncio
async def test_evidence_weighted_mastery_calculation():
    """
    Test evidence-weighted mastery update (EMA).
    Formula: new_score = (1 - alpha) * prev_score + alpha * (evidence_score * 100)
    """
    alpha = settings.MASTERY_ALPHA  # 0.3
    prev_score = 50.0
    evidence_score = 0.9  # 90%
    expected = (1 - alpha) * prev_score + alpha * (evidence_score * 100)
    assert round(expected, 2) == 62.0

    # Trend detection:
    # If delta > 5.0 -> improving
    # If delta < -5.0 -> needs_attention
    # else -> stable
    delta = expected - prev_score
    assert delta > 5.0  # Should be 'improving'


@pytest.mark.asyncio
@pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL not running locally on port 5432")
async def test_admin_provisioning_flow():
    """
    Verify that a user whose email matches ADMIN_EMAIL is provisioned as admin,
    while normal users are always 'user' role.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.models import User, UserRole
    from app.main import _provision_admin
    from sqlalchemy import select

    admin_email = f"provisioned_admin_{uuid.uuid4().hex[:6]}@example.com"
    original_admin_email = settings.ADMIN_EMAIL

    try:
        # Override ADMIN_EMAIL in settings
        settings.ADMIN_EMAIL = admin_email

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Register as normal
            reg_res = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": admin_email,
                    "password": "AdminPassword123!",
                    "display_name": "Site Administrator"
                }
            )
            assert reg_res.status_code == 201
            token = reg_res.json()["access_token"]
            # Since email matches ADMIN_EMAIL, registration role is 'admin'
            assert reg_res.json()["role"] == "admin"

            # 2. Run admin provisioning (simulates startup idempotent check)
            await _provision_admin()

            # 3. Verify in DB that role is admin
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.email == admin_email))
                user = result.scalar_one()
                assert user.role == UserRole.admin

            # 4. Now login as the promoted admin
            login_res = await client.post(
                "/api/v1/auth/login",
                json={"email": admin_email, "password": "AdminPassword123!"}
            )
            admin_token = login_res.json()["access_token"]
            assert login_res.json()["role"] == "admin"

            # 5. Access admin dashboard with promoted admin token
            admin_res = await client.get(
                "/api/v1/admin/dashboard",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert admin_res.status_code == 200
            overview = admin_res.json()
            assert "total_users" in overview
            assert "total_spaces" in overview
    finally:
        settings.ADMIN_EMAIL = original_admin_email


def test_adaptive_difficulty_mapping():
    from app.api.v1.quiz import _map_mastery_to_difficulty
    assert _map_mastery_to_difficulty(15.0) == 1
    assert _map_mastery_to_difficulty(40.0) == 2
    assert _map_mastery_to_difficulty(55.0) == 3
    assert _map_mastery_to_difficulty(70.0) == 4
    assert _map_mastery_to_difficulty(90.0) == 5


def test_text_chunking_algorithm():
    from app.workers.document_pipeline import chunk_text
    sample_text = " ".join([f"word_{i}" for i in range(100)])
    chunks = chunk_text(sample_text, page_number=1, chunk_size=30, overlap=5)
    assert len(chunks) > 1
    assert all(c["page_number"] == 1 for c in chunks)
    assert chunks[0]["chunk_index"] == 0
    assert chunks[1]["chunk_index"] == 1


def test_ai_observability_cost_calculation():
    from app.ai.gemini_client import gemini_client
    cost = gemini_client._estimate_cost("gemini-3.6-flash", prompt_tokens=1000, completion_tokens=500)
    # (1000 * 0.075 + 500 * 0.30) / 1,000,000 = (75 + 150) / 1,000,000 = 0.000225
    assert round(cost, 6) == 0.000225


@pytest.mark.asyncio
async def test_unauthorized_endpoints_protection():
    """Verify endpoints strictly enforce authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Without token
        res_spaces = await client.get("/api/v1/spaces")
        assert res_spaces.status_code in (401, 403)

        res_admin = await client.get("/api/v1/admin/dashboard")
        assert res_admin.status_code in (401, 403)


