"""Projects API — CRUD + dashboard."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
import uuid

from app.db.session import get_db
from app.models.models import (
    Project, Space, Material, Concept, MasteryRecord, Recommendation,
    Assessment, Event, LearningContext, MaterialStatus, RecommendationStatus
)
from app.schemas.schemas import (
    ProjectCreate, ProjectUpdate, ProjectOut, ProjectDashboard, ConceptSummary
)
from app.core.deps import get_current_user

router = APIRouter(prefix="/spaces/{space_id}/projects", tags=["projects"])


async def _verify_space_access(space_id: UUID, user_id: UUID, db: AsyncSession) -> Space:
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == user_id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


async def _verify_project_access(project_id: UUID, space_id: UUID, user_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.space_id == space_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _project_to_out(project: Project, db: AsyncSession) -> ProjectOut:
    mat_count = await db.execute(select(func.count(Material.id)).where(Material.project_id == project.id))
    ready_count = await db.execute(
        select(func.count(Material.id)).where(
            Material.project_id == project.id,
            Material.status == MaterialStatus.ready
        )
    )
    concept_count = await db.execute(select(func.count(Concept.id)).where(Concept.project_id == project.id))

    return ProjectOut(
        id=project.id,
        space_id=project.space_id,
        name=project.name,
        description=project.description,
        learning_goal=project.learning_goal,
        created_at=project.created_at,
        last_activity_at=project.last_activity_at,
        material_count=mat_count.scalar() or 0,
        ready_material_count=ready_count.scalar() or 0,
        concept_count=concept_count.scalar() or 0,
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_space_access(space_id, current_user.id, db)
    result = await db.execute(
        select(Project).where(
            Project.space_id == space_id,
            Project.user_id == current_user.id,
        ).order_by(Project.last_activity_at.desc().nullslast(), Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [await _project_to_out(p, db) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    space_id: UUID,
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    space = await _verify_space_access(space_id, current_user.id, db)

    project = Project(
        id=uuid.uuid4(),
        space_id=space_id,
        user_id=current_user.id,
        name=body.name.strip(),
        description=body.description,
        learning_goal=body.learning_goal,
        last_activity_at=datetime.now(timezone.utc),
    )
    db.add(project)
    await db.flush()

    # Create initial learning context
    context = LearningContext(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=current_user.id,
        goals=body.learning_goal,
        known_strengths=[],
        known_weaknesses=[],
        repeated_mistakes=[],
    )
    db.add(context)

    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        space_id=space_id,
        project_id=project.id,
        event_type="project_created",
        payload={"name": project.name, "goal": project.learning_goal},
    )
    db.add(event)
    await db.commit()
    return await _project_to_out(project, db)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access(project_id, space_id, current_user.id, db)
    return await _project_to_out(project, db)


@router.get("/{project_id}/dashboard", response_model=ProjectDashboard)
async def get_project_dashboard(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access(project_id, space_id, current_user.id, db)
    project_out = await _project_to_out(project, db)

    # Top concepts with mastery
    concepts_result = await db.execute(
        select(Concept).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        ).order_by(Concept.importance_score.desc()).limit(6)
    )
    concepts = concepts_result.scalars().all()

    top_concepts = []
    mastery_scores = []
    for concept in concepts:
        mastery_result = await db.execute(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
        )
        mastery = mastery_result.scalar_one_or_none()
        score = mastery.score if mastery else None
        trend = mastery.trend.value if mastery else None
        if score is not None:
            mastery_scores.append(score)
        top_concepts.append(ConceptSummary(
            id=concept.id,
            name=concept.name,
            description=concept.description,
            mastery_score=score,
            trend=trend,
        ))

    mastery_avg = sum(mastery_scores) / len(mastery_scores) if mastery_scores else None

    # Latest active recommendation
    rec_result = await db.execute(
        select(Recommendation).where(
            Recommendation.project_id == project_id,
            Recommendation.user_id == current_user.id,
            Recommendation.status == RecommendationStatus.active,
        ).order_by(Recommendation.created_at.desc()).limit(1)
    )
    rec = rec_result.scalar_one_or_none()

    # Latest assessment score
    ass_result = await db.execute(
        select(Assessment).where(
            Assessment.project_id == project_id,
            Assessment.user_id == current_user.id,
            Assessment.status == "completed",
        ).order_by(Assessment.completed_at.desc()).limit(1)
    )
    latest_assessment = ass_result.scalar_one_or_none()

    # 7-day activity count
    from sqlalchemy import text
    act_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM events
            WHERE project_id = :pid AND user_id = :uid
              AND created_at > NOW() - INTERVAL '7 days'
        """),
        {"pid": str(project_id), "uid": str(current_user.id)}
    )
    activity_count = act_result.scalar() or 0

    return ProjectDashboard(
        project=project_out,
        top_concepts=top_concepts,
        latest_recommendation={"content": rec.content, "type": rec.recommendation_type, "reason": rec.reason} if rec else None,
        recent_assessment_score=latest_assessment.score_pct if latest_assessment else None,
        mastery_avg=mastery_avg,
        activity_count_7d=activity_count,
    )


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(
    space_id: UUID,
    project_id: UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access(project_id, space_id, current_user.id, db)
    if body.name is not None:
        project.name = body.name.strip()
    if body.description is not None:
        project.description = body.description
    if body.learning_goal is not None:
        project.learning_goal = body.learning_goal
    project.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return await _project_to_out(project, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access(project_id, space_id, current_user.id, db)
    await db.delete(project)
    await db.commit()


# ──────────────────────────────────────────────
# Direct router (/projects/{project_id})
# ──────────────────────────────────────────────
direct_router = APIRouter(prefix="/projects", tags=["projects"])


@direct_router.get("/{project_id}", response_model=ProjectOut)
async def get_project_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await _project_to_out(project, db)


@direct_router.get("/{project_id}/dashboard", response_model=ProjectDashboard)
async def get_project_dashboard_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_project_dashboard(project.space_id, project_id, db, current_user)
