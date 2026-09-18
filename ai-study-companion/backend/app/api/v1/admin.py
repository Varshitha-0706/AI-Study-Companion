"""Admin Dashboard API — requires admin role."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID
from typing import Optional

from app.db.session import get_db
from app.models.models import (
    User, Space, Project, Material, Assessment, Event, AILog, BackgroundJob
)
from app.core.deps import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
@router.get("/dashboard")
async def admin_overview(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    """Platform-level overview for administrators."""
    users = await db.execute(select(func.count(User.id)))
    spaces = await db.execute(select(func.count(Space.id)))
    projects = await db.execute(select(func.count(Project.id)))
    materials = await db.execute(select(func.count(Material.id)))

    active_today = await db.execute(
        text("SELECT COUNT(DISTINCT user_id) FROM events WHERE created_at > NOW() - INTERVAL '24 hours'")
    )
    ai_calls_today = await db.execute(
        text("SELECT COUNT(*) FROM ai_logs WHERE created_at > NOW() - INTERVAL '24 hours'")
    )
    ai_cost_today = await db.execute(
        text("SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM ai_logs WHERE created_at > NOW() - INTERVAL '24 hours'")
    )
    pending_jobs = await db.execute(
        text("SELECT COUNT(*) FROM background_jobs WHERE status IN ('pending', 'running')")
    )
    failed_24h = await db.execute(
        text("SELECT COUNT(*) FROM background_jobs WHERE status = 'failed' AND created_at > NOW() - INTERVAL '24 hours'")
    )

    return {
        "total_users": users.scalar() or 0,
        "total_spaces": spaces.scalar() or 0,
        "total_projects": projects.scalar() or 0,
        "total_materials": materials.scalar() or 0,
        "active_users_24h": active_today.scalar() or 0,
        "ai_calls_24h": ai_calls_today.scalar() or 0,
        "ai_cost_usd_24h": float(ai_cost_today.scalar() or 0),
        "pending_jobs": pending_jobs.scalar() or 0,
        "failed_jobs_24h": failed_24h.scalar() or 0,
    }


@router.get("/users")
async def admin_list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """List all users with activity summary."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    out = []
    for user in users:
        space_count = await db.execute(select(func.count(Space.id)).where(Space.user_id == user.id))
        project_count = await db.execute(select(func.count(Project.id)).where(Project.user_id == user.id))
        ai_count = await db.execute(select(func.count(AILog.id)).where(AILog.user_id == user.id))

        out.append({
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role.value,
            "created_at": user.created_at.isoformat(),
            "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
            "space_count": space_count.scalar() or 0,
            "project_count": project_count.scalar() or 0,
            "ai_call_count": ai_count.scalar() or 0,
        })
    return out


@router.get("/users/{user_id}")
async def admin_get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Detailed user view: spaces, projects, activity, AI usage."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    spaces_result = await db.execute(select(Space).where(Space.user_id == user_id))
    spaces = spaces_result.scalars().all()

    projects_result = await db.execute(select(Project).where(Project.user_id == user_id))
    projects = projects_result.scalars().all()

    recent_events = await db.execute(
        select(Event).where(Event.user_id == user_id)
        .order_by(Event.created_at.desc()).limit(20)
    )
    events = recent_events.scalars().all()

    ai_summary = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) as total_cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency
            FROM ai_logs WHERE user_id = :uid
        """),
        {"uid": str(user_id)}
    )
    ai_row = ai_summary.fetchone()

    return {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role.value,
            "created_at": user.created_at.isoformat(),
        },
        "spaces": [{"id": str(s.id), "name": s.name} for s in spaces],
        "projects": [{"id": str(p.id), "name": p.name, "space_id": str(p.space_id)} for p in projects],
        "recent_events": [
            {"type": e.event_type, "created_at": e.created_at.isoformat(), "project_id": str(e.project_id) if e.project_id else None}
            for e in events
        ],
        "ai_usage": {
            "total_calls": ai_row[0],
            "total_tokens": ai_row[1],
            "total_cost_usd": float(ai_row[2]),
            "avg_latency_ms": float(ai_row[3]),
        },
    }


@router.get("/activity")
async def admin_activity_feed(
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    event_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Platform activity feed with filters."""
    query = select(Event).order_by(Event.created_at.desc())

    if user_id:
        query = query.where(Event.user_id == UUID(user_id))
    if project_id:
        query = query.where(Event.project_id == UUID(project_id))
    if event_type:
        query = query.where(Event.event_type == event_type)

    result = await db.execute(query.offset(skip).limit(limit))
    events = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "user_id": str(e.user_id),
            "project_id": str(e.project_id) if e.project_id else None,
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/ai-usage")
@router.get("/ai-stats")
async def admin_ai_usage(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """AI usage statistics for the platform."""
    summary = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_calls,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(estimated_cost_usd), 0) as total_cost,
                COALESCE(AVG(latency_ms), 0) as avg_latency,
                COALESCE(AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END), 0) as success_rate
            FROM ai_logs
        """)
    )
    row = summary.fetchone()

    by_feature = await db.execute(
        text("""
            SELECT feature, COUNT(*) as calls, COALESCE(SUM(estimated_cost_usd), 0) as cost
            FROM ai_logs GROUP BY feature ORDER BY calls DESC
        """)
    )
    by_model = await db.execute(
        text("""
            SELECT model, COUNT(*) as calls, COALESCE(SUM(total_tokens), 0) as tokens
            FROM ai_logs GROUP BY model ORDER BY calls DESC
        """)
    )

    return {
        "total_calls": row[0],
        "total_tokens": row[1],
        "total_cost_usd": float(row[2]),
        "avg_latency_ms": float(row[3]),
        "success_rate": float(row[4]),
        "by_feature": [{"feature": r[0], "calls": r[1], "cost_usd": float(r[2])} for r in by_feature],
        "by_model": [{"model": r[0], "calls": r[1], "tokens": r[2]} for r in by_model],
    }


@router.get("/jobs")
async def admin_jobs(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    """Background job status."""
    result = await db.execute(
        select(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(100)
    )
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "job_type": j.job_type,
            "status": j.status,
            "retries": j.retries,
            "error": j.error,
            "created_at": j.created_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/health")
async def admin_health(db: AsyncSession = Depends(get_db), admin=Depends(require_admin)):
    """System health check."""
    import redis
    from app.core.config import settings

    # DB check
    db_ok = False
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # Redis check
    redis_ok = False
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    return {
        "db_status": "healthy" if db_ok else "unhealthy",
        "redis_status": "healthy" if redis_ok else "unhealthy",
        "generation_model": settings.GEMINI_GENERATION_MODEL,
        "embedding_model": settings.GEMINI_EMBEDDING_MODEL,
        "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
    }
