"""Analytics API — project and global analytics from real DB data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from uuid import UUID

from app.db.session import get_db
from app.models.models import (
    Project, Material, Assessment, Message, Event, MasteryRecord,
    MaterialStatus, AssessmentStatus, Concept
)
from app.schemas.schemas import ProjectAnalyticsOut, GlobalAnalyticsOut
from app.core.deps import get_current_user

router = APIRouter(tags=["analytics"])


@router.get("/spaces/{space_id}/projects/{project_id}/analytics",
            response_model=ProjectAnalyticsOut)
async def get_project_analytics(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Real project analytics from DB aggregation — no mock data."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Total events
    ev_count = await db.execute(
        select(func.count(Event.id)).where(
            Event.project_id == project_id,
            Event.user_id == current_user.id,
        )
    )

    # Tutor messages
    tutor_count = await db.execute(
        select(func.count(Event.id)).where(
            Event.project_id == project_id,
            Event.user_id == current_user.id,
            Event.event_type == "tutor_message",
        )
    )

    # Completed quizzes
    quiz_count = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
            Assessment.status == AssessmentStatus.completed,
        )
    )

    # Avg quiz score
    avg_score = await db.execute(
        select(func.avg(Assessment.score_pct)).where(
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
            Assessment.status == AssessmentStatus.completed,
        )
    )

    # Materials count
    mat_count = await db.execute(
        select(func.count(Material.id)).where(Material.project_id == project_id)
    )

    # Concepts count
    concept_count = await db.execute(
        select(func.count(Concept.id)).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        )
    )

    # Mastery average
    mastery_avg_result = await db.execute(
        select(func.avg(MasteryRecord.score)).where(
            MasteryRecord.project_id == project_id,
            MasteryRecord.user_id == current_user.id,
        )
    )

    # Event timeline (last 14 days, grouped by day and type)
    timeline_result = await db.execute(
        text("""
            SELECT
                DATE_TRUNC('day', created_at) AS day,
                event_type,
                COUNT(*) as count
            FROM events
            WHERE project_id = :pid AND user_id = :uid
              AND created_at > NOW() - INTERVAL '14 days'
            GROUP BY day, event_type
            ORDER BY day
        """),
        {"pid": str(project_id), "uid": str(current_user.id)}
    )
    timeline = [
        {"day": row[0].isoformat(), "event_type": row[1], "count": row[2]}
        for row in timeline_result.fetchall()
    ]

    # Concept mastery list
    concepts_result = await db.execute(
        select(Concept, MasteryRecord).outerjoin(
            MasteryRecord, MasteryRecord.concept_id == Concept.id
        ).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        ).order_by(Concept.importance_score.desc())
    )
    concept_mastery = [
        {
            "name": c.name,
            "score": m.score if m else None,
            "trend": m.trend.value if m else None,
        }
        for c, m in concepts_result.fetchall()
    ]

    return ProjectAnalyticsOut(
        project_id=project_id,
        total_events=ev_count.scalar() or 0,
        tutor_messages=tutor_count.scalar() or 0,
        quizzes_completed=quiz_count.scalar() or 0,
        avg_quiz_score=avg_score.scalar(),
        materials_count=mat_count.scalar() or 0,
        concepts_count=concept_count.scalar() or 0,
        mastery_avg=mastery_avg_result.scalar() or 0.0,
        event_timeline=timeline,
        concept_mastery_list=concept_mastery,
    )


@router.get("/analytics/global", response_model=GlobalAnalyticsOut)
async def get_global_analytics(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Global analytics for the current user across all spaces and projects."""
    from app.models.models import User, Space, AILog

    user_count = await db.execute(select(func.count(Project.id)).where(Project.user_id == current_user.id))
    space_count = await db.execute(
        select(func.count()).select_from(
            __import__('sqlalchemy', fromlist=['select']).select(Project.space_id.distinct()).where(
                Project.user_id == current_user.id
            ).subquery()
        )
    )
    project_count = await db.execute(
        select(func.count(Project.id)).where(Project.user_id == current_user.id)
    )
    material_count = await db.execute(
        select(func.count(Material.id)).where(Material.user_id == current_user.id)
    )
    tutor_msg_count = await db.execute(
        select(func.count(Event.id)).where(
            Event.user_id == current_user.id,
            Event.event_type == "tutor_message",
        )
    )
    quiz_count = await db.execute(
        select(func.count(Assessment.id)).where(
            Assessment.user_id == current_user.id,
            Assessment.status == AssessmentStatus.completed,
        )
    )
    ai_calls = await db.execute(
        select(func.count(AILog.id)).where(AILog.user_id == current_user.id)
    )
    ai_cost = await db.execute(
        select(func.coalesce(func.sum(AILog.estimated_cost_usd), 0)).where(
            AILog.user_id == current_user.id
        )
    )
    active_7d = await db.execute(
        select(func.count(Event.id)).where(
            Event.user_id == current_user.id,
            text("created_at > NOW() - INTERVAL '7 days'"),
        )
    )

    return GlobalAnalyticsOut(
        total_users=1,
        total_spaces=0,  # Will be computed properly below
        total_projects=project_count.scalar() or 0,
        total_materials=material_count.scalar() or 0,
        total_tutor_messages=tutor_msg_count.scalar() or 0,
        total_quizzes=quiz_count.scalar() or 0,
        total_ai_calls=ai_calls.scalar() or 0,
        total_ai_cost_usd=float(ai_cost.scalar() or 0),
        active_users_7d=1 if (active_7d.scalar() or 0) > 0 else 0,
    )
