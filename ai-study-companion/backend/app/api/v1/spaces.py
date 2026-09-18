"""Spaces API — full CRUD with user isolation."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from uuid import UUID
import uuid

from app.db.session import get_db
from app.models.models import Space, Project, Event
from app.schemas.schemas import SpaceCreate, SpaceUpdate, SpaceOut
from app.core.deps import get_current_user

router = APIRouter(prefix="/spaces", tags=["spaces"])


def _space_to_out(space: Space, project_count: int) -> SpaceOut:
    return SpaceOut(
        id=space.id,
        name=space.name,
        description=space.description,
        color=space.color,
        icon=space.icon,
        created_at=space.created_at,
        project_count=project_count,
    )


@router.get("", response_model=list[SpaceOut])
async def list_spaces(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    """List all spaces for the current user."""
    result = await db.execute(
        select(Space).where(Space.user_id == current_user.id).order_by(Space.created_at.desc())
    )
    spaces = result.scalars().all()

    out = []
    for space in spaces:
        count_result = await db.execute(
            select(func.count(Project.id)).where(Project.space_id == space.id)
        )
        project_count = count_result.scalar() or 0
        out.append(_space_to_out(space, project_count))
    return out


@router.post("", response_model=SpaceOut, status_code=status.HTTP_201_CREATED)
async def create_space(
    body: SpaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    space = Space(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=body.name.strip(),
        description=body.description,
        color=body.color or "#6366f1",
        icon=body.icon or "📚",
    )
    db.add(space)
    await db.flush()

    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        space_id=space.id,
        event_type="space_created",
        payload={"name": space.name},
    )
    db.add(event)
    await db.commit()
    return _space_to_out(space, 0)


@router.get("/{space_id}", response_model=SpaceOut)
async def get_space(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == current_user.id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    count_result = await db.execute(
        select(func.count(Project.id)).where(Project.space_id == space.id)
    )
    return _space_to_out(space, count_result.scalar() or 0)


@router.put("/{space_id}", response_model=SpaceOut)
async def update_space(
    space_id: UUID,
    body: SpaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == current_user.id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    if body.name is not None:
        space.name = body.name.strip()
    if body.description is not None:
        space.description = body.description
    if body.color is not None:
        space.color = body.color
    if body.icon is not None:
        space.icon = body.icon
    space.updated_at = datetime.now(timezone.utc)
    await db.commit()

    count_result = await db.execute(
        select(func.count(Project.id)).where(Project.space_id == space.id)
    )
    return _space_to_out(space, count_result.scalar() or 0)


@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_space(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Space).where(Space.id == space_id, Space.user_id == current_user.id)
    )
    space = result.scalar_one_or_none()
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    await db.delete(space)
    await db.commit()
