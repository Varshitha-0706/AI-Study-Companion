"""Application configuration loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://asc_user:asc_password@localhost:5432/asc_db"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Auth
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Google Gemini — verified 2026-09-16
    # gemini-3.6-flash: confirmed available (gemini-2.0-flash is NOT available)
    # gemini-embedding-2: confirmed available, dimension=3072 (text-embedding-004 NOT available)
    GEMINI_API_KEY: str
    GEMINI_GENERATION_MODEL: str = "gemini-3.6-flash"
    GEMINI_EMBEDDING_MODEL: str = "models/gemini-embedding-2"
    EMBEDDING_DIMENSIONS: int = 3072  # Verified via live API call

    # Admin provisioning — NEVER auto-promote first user
    ADMIN_EMAIL: str = ""

    # Storage
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    UPLOAD_DIR: str = "./uploads"

    # S3 (optional)
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = ""  # e.g., "https://s3.amazonaws.com" or custom endpoint
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # AI / RAG configuration
    RETRIEVAL_CONFIDENCE_THRESHOLD: float = 0.50
    RETRIEVAL_TOP_K: int = 5
    TUTOR_CONTEXT_MESSAGES: int = 6
    DEFAULT_QUIZ_LENGTH: int = 10
    MASTERY_ALPHA: float = 0.3  # evidence weight in moving average

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
