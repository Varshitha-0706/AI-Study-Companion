"""
AI Observability: logs all AI calls to the ai_logs table.
Provides visibility into model, latency, token usage, cost, and success/failure.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AILog


async def log_ai_call(
    db: AsyncSession,
    feature: str,
    model: str,
    latency_ms: int,
    success: bool,
    user_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    error_message: Optional[str] = None,
) -> None:
    """
    Persist an AI call observation to the database.
    Called after every Gemini API call (success or failure).
    """
    log = AILog(
        id=uuid.uuid4(),
        user_id=user_id,
        project_id=project_id,
        feature=feature,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        latency_ms=latency_ms,
        estimated_cost_usd=estimated_cost_usd,
        success=success,
        error_message=error_message,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    # Note: commit is handled by the caller's session lifecycle
