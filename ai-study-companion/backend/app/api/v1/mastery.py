"""Mastery, Growth Analysis, and Recommendations APIs."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from uuid import UUID

from app.db.session import get_db
from app.models.models import (
    Project, Concept, MasteryRecord, MasteryHistory,
    MasteryTrend, Recommendation, RecommendationStatus
)
from app.schemas.schemas import (
    GrowthAnalysisOut, MasteryConceptOut, RecommendationOut
)
from app.core.deps import get_current_user

router = APIRouter(tags=["mastery"])


async def _verify_project_access(project_id: UUID, user_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/spaces/{space_id}/projects/{project_id}/mastery")
async def get_mastery(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get mastery levels for all concepts in the project."""
    await _verify_project_access(project_id, current_user.id, db)

    concepts_result = await db.execute(
        select(Concept).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        ).order_by(Concept.importance_score.desc())
    )
    concepts = concepts_result.scalars().all()

    result = []
    for concept in concepts:
        mastery_result = await db.execute(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
        )
        mastery = mastery_result.scalar_one_or_none()

        history = []
        if mastery:
            hist_result = await db.execute(
                select(MasteryHistory)
                .where(MasteryHistory.mastery_record_id == mastery.id)
                .order_by(MasteryHistory.recorded_at)
            )
            hist_rows = hist_result.scalars().all()
            history = [{"score": h.score, "date": h.recorded_at.isoformat(), "type": h.evidence_type}
                      for h in hist_rows]

        result.append({
            "concept_id": str(concept.id),
            "concept_name": concept.name,
            "description": concept.description,
            "importance_score": concept.importance_score,
            "score": mastery.score if mastery else None,
            "trend": mastery.trend.value if mastery else None,
            "evidence_count": mastery.evidence_count if mastery else 0,
            "history": history,
        })

    return result


@router.get("/spaces/{space_id}/projects/{project_id}/growth",
            response_model=GrowthAnalysisOut)
async def get_growth_analysis(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Growth analysis: categorize concepts into improving/stable/needs_attention.
    All data is real — computed from mastery_records and mastery_history tables.
    """
    await _verify_project_access(project_id, current_user.id, db)

    concepts_result = await db.execute(
        select(Concept).where(
            Concept.project_id == project_id,
            Concept.user_id == current_user.id,
        )
    )
    concepts = concepts_result.scalars().all()

    improving = []
    stable = []
    needs_attention = []
    insufficient_data = []
    all_scores = []

    for concept in concepts:
        mastery_result = await db.execute(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept.id)
        )
        mastery = mastery_result.scalar_one_or_none()

        if not mastery:
            insufficient_data.append(MasteryConceptOut(
                concept_id=concept.id,
                concept_name=concept.name,
                score=50.0,
                trend="insufficient_data",
                evidence_count=0,
            ))
            continue

        all_scores.append(mastery.score)

        hist_result = await db.execute(
            select(MasteryHistory)
            .where(MasteryHistory.mastery_record_id == mastery.id)
            .order_by(MasteryHistory.recorded_at.desc()).limit(5)
        )
        history_rows = hist_result.scalars().all()
        history = [{"score": h.score, "date": h.recorded_at.isoformat(), "type": h.evidence_type}
                  for h in reversed(history_rows)]

        entry = MasteryConceptOut(
            concept_id=concept.id,
            concept_name=concept.name,
            score=mastery.score,
            trend=mastery.trend.value,
            evidence_count=mastery.evidence_count,
            history=history,
        )

        if mastery.trend == MasteryTrend.improving:
            improving.append(entry)
        elif mastery.trend == MasteryTrend.needs_attention:
            needs_attention.append(entry)
        elif mastery.trend == MasteryTrend.stable:
            stable.append(entry)
        else:
            insufficient_data.append(entry)

    overall = sum(all_scores) / len(all_scores) if all_scores else 0.0

    return GrowthAnalysisOut(
        project_id=project_id,
        improving=improving,
        stable=stable,
        needs_attention=needs_attention,
        insufficient_data=insufficient_data,
        overall_mastery=overall,
    )


@router.get("/spaces/{space_id}/projects/{project_id}/recommendations",
            response_model=list[RecommendationOut])
async def get_recommendations(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get active recommendations for the project. All from real learner state."""
    await _verify_project_access(project_id, current_user.id, db)

    result = await db.execute(
        select(Recommendation).where(
            Recommendation.project_id == project_id,
            Recommendation.user_id == current_user.id,
            Recommendation.status == RecommendationStatus.active,
        ).order_by(Recommendation.created_at.desc()).limit(5)
    )
    recommendations = result.scalars().all()
    return recommendations


@router.post("/spaces/{space_id}/projects/{project_id}/recommendations/{rec_id}/dismiss",
             status_code=204)
async def dismiss_recommendation(
    space_id: UUID,
    project_id: UUID,
    rec_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_project_access(project_id, current_user.id, db)
    result = await db.execute(
        select(Recommendation).where(
            Recommendation.id == rec_id,
            Recommendation.project_id == project_id,
            Recommendation.user_id == current_user.id,
        )
    )
    rec = result.scalar_one_or_none()
    if rec:
        rec.status = RecommendationStatus.dismissed
        await db.commit()


# ──────────────────────────────────────────────
# Direct / Simplified Mastery Routes
# ──────────────────────────────────────────────
from fastapi import Query
from typing import Optional


@router.get("/mastery/projects/{project_id}/overview")
async def get_mastery_overview_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct mastery overview matching frontend masteryApi."""
    project = await _verify_project_access(project_id, current_user.id, db)
    return await get_mastery(project.space_id, project_id, db, current_user)


@router.get("/mastery/projects/{project_id}/recommendations")
async def get_mastery_recommendations_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct recommendations endpoint matching frontend masteryApi."""
    project = await _verify_project_access(project_id, current_user.id, db)
    return await get_recommendations(project.space_id, project_id, db, current_user)


@router.get("/mastery/projects/{project_id}/history")
async def get_mastery_history_direct(
    project_id: UUID,
    concept_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct mastery history records."""
    await _verify_project_access(project_id, current_user.id, db)

    query = select(MasteryHistory).join(MasteryRecord).where(
        MasteryRecord.project_id == project_id,
        MasteryRecord.user_id == current_user.id,
    )
    if concept_id:
        query = query.where(MasteryRecord.concept_id == concept_id)

    query = query.order_by(MasteryHistory.recorded_at.asc())
    result = await db.execute(query)
    history_records = result.scalars().all()

    return [
        {
            "id": str(h.id),
            "mastery_record_id": str(h.mastery_record_id),
            "score": h.score,
            "evidence_type": h.evidence_type,
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h in history_records
    ]


@router.get("/mastery/projects/{project_id}/growth",
            response_model=GrowthAnalysisOut)
async def get_growth_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct growth analysis matching frontend masteryApi."""
    project = await _verify_project_access(project_id, current_user.id, db)
    return await get_growth_analysis(project.space_id, project_id, db, current_user)


@router.get("/mastery/projects/{project_id}/context")
async def get_learning_context_direct(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Direct learning context endpoint."""
    project = await _verify_project_access(project_id, current_user.id, db)
    from app.models.models import LearningContext
    result = await db.execute(
        select(LearningContext).where(
            LearningContext.project_id == project_id,
            LearningContext.user_id == current_user.id,
        )
    )
    context = result.scalar_one_or_none()
    if not context:
        return {
            "project_id": str(project_id),
            "known_strengths": [],
            "known_weaknesses": [],
            "repeated_mistakes": [],
            "updated_at": None,
        }
    return {
        "project_id": str(project_id),
        "known_strengths": context.known_strengths or [],
        "known_weaknesses": context.known_weaknesses or [],
        "repeated_mistakes": context.repeated_mistakes or [],
        "updated_at": context.updated_at.isoformat() if context.updated_at else None,
    }

