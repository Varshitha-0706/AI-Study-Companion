"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.session import engine, Base
from app.api.v1 import auth, spaces, projects, materials, tutor, quiz, mastery, analytics, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Enable pgvector extension first before creating tables that use VECTOR
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Admin provisioning via ADMIN_EMAIL (NEVER auto-promote first user)
    if settings.ADMIN_EMAIL:
        await _provision_admin()

    yield

    await engine.dispose()


async def _provision_admin():
    """
    Provision admin role to the configured ADMIN_EMAIL user.
    This is the ONLY way to create an admin — no registration flow auto-promotes.
    """
    from app.db.session import AsyncSessionLocal
    from app.models.models import User, UserRole
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(User).where(User.email == settings.ADMIN_EMAIL.lower())
            )
            user = result.scalar_one_or_none()
            if user and user.role != UserRole.admin:
                user.role = UserRole.admin
                await db.commit()
                print(f"[startup] Admin role provisioned to: {settings.ADMIN_EMAIL}")
            elif user:
                print(f"[startup] Admin already provisioned: {settings.ADMIN_EMAIL}")
            else:
                print(f"[startup] ADMIN_EMAIL set but user not registered yet: {settings.ADMIN_EMAIL}")
        except Exception as e:
            print(f"[startup] Admin provisioning failed: {e}")


app = FastAPI(
    title="AI Study Companion",
    description="Persistent contextual AI learning companion with RAG, adaptive quizzes, and mastery tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(spaces.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(projects.direct_router, prefix="/api/v1")
app.include_router(materials.router, prefix="/api/v1")
app.include_router(tutor.router, prefix="/api/v1")
app.include_router(quiz.router, prefix="/api/v1")
app.include_router(mastery.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "product": "AI Study Companion",
        "version": "1.0.0",
        "status": "running",
        "models": {
            "generation": settings.GEMINI_GENERATION_MODEL,
            "embedding": settings.GEMINI_EMBEDDING_MODEL,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
        },
    }


@app.get("/health")
@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}
