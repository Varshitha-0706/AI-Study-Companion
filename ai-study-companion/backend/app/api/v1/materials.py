"""Materials upload and processing status API."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional, List
import uuid
import asyncio

from app.db.session import get_db
from app.models.models import Material, MaterialStatus, Project, Space, Event, Chunk
from app.schemas.schemas import MaterialOut
from app.core.deps import get_current_user
from app.services.storage_service import storage_service

router = APIRouter(tags=["materials"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


async def _verify_project_access_by_id(project_id: UUID, user_id: UUID, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.user_id == user_id,
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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


async def _handle_upload(
    project: Project,
    file: UploadFile,
    current_user,
    db: AsyncSession,
) -> MaterialOut:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max size: 50MB")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    storage_key = await storage_service.save(
        file_data=content,
        user_id=str(current_user.id),
        project_id=str(project.id),
        filename=unique_name,
    )

    material = Material(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=current_user.id,
        filename=storage_key,
        original_filename=file.filename,
        file_size=len(content),
        status=MaterialStatus.queued,
    )
    db.add(material)

    event = Event(
        id=uuid.uuid4(),
        user_id=current_user.id,
        project_id=project.id,
        space_id=project.space_id,
        event_type="material_uploaded",
        payload={"filename": file.filename, "size": len(content)},
    )
    db.add(event)

    project.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    # Dispatch Celery processing task, or fallback to background thread
    dispatched = False
    try:
        from app.workers.document_pipeline import process_document
        task = process_document.delay(
            material_id=str(material.id),
            user_id=str(current_user.id),
            project_id=str(project.id),
        )
        material.celery_task_id = task.id
        await db.commit()
        dispatched = True
    except Exception as e:
        print(f"[materials] Celery dispatch failed, using async fallback: {e}")

    if not dispatched:
        from app.workers.document_pipeline import process_document_sync
        asyncio.create_task(
            asyncio.to_thread(
                process_document_sync,
                str(material.id),
                str(current_user.id),
                str(project.id),
            )
        )

    return MaterialOut(
        id=material.id,
        original_filename=material.original_filename,
        file_size=material.file_size,
        status=material.status.value,
        error_message=material.error_message,
        page_count=material.page_count,
        created_at=material.created_at,
        processed_at=material.processed_at,
    )


# ──────────────────────────────────────────────
# Nested Space Routes
# ──────────────────────────────────────────────
@router.post(
    "/spaces/{space_id}/projects/{project_id}/materials",
    response_model=MaterialOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_material(
    space_id: UUID,
    project_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access(project_id, space_id, current_user.id, db)
    return await _handle_upload(project, file, current_user, db)


@router.get(
    "/spaces/{space_id}/projects/{project_id}/materials",
    response_model=list[MaterialOut],
)
async def list_materials(
    space_id: UUID,
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_project_access(project_id, space_id, current_user.id, db)
    result = await db.execute(
        select(Material).where(
            Material.project_id == project_id,
            Material.user_id == current_user.id,
        ).order_by(Material.created_at.desc())
    )
    materials = result.scalars().all()
    return [
        MaterialOut(
            id=m.id,
            original_filename=m.original_filename,
            file_size=m.file_size,
            status=m.status.value,
            error_message=m.error_message,
            page_count=m.page_count,
            created_at=m.created_at,
            processed_at=m.processed_at,
        )
        for m in materials
    ]


@router.get(
    "/spaces/{space_id}/projects/{project_id}/materials/{material_id}",
    response_model=MaterialOut,
)
async def get_material_status(
    space_id: UUID,
    project_id: UUID,
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_project_access(project_id, space_id, current_user.id, db)
    result = await db.execute(
        select(Material).where(
            Material.id == material_id,
            Material.project_id == project_id,
            Material.user_id == current_user.id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    return MaterialOut(
        id=material.id,
        original_filename=material.original_filename,
        file_size=material.file_size,
        status=material.status.value,
        error_message=material.error_message,
        page_count=material.page_count,
        created_at=material.created_at,
        processed_at=material.processed_at,
    )


# ──────────────────────────────────────────────
# Direct / Simplified Project Routes
# ──────────────────────────────────────────────
@router.post(
    "/materials/upload",
    response_model=MaterialOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_material_direct(
    project_id: UUID = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    project = await _verify_project_access_by_id(project_id, current_user.id, db)
    return await _handle_upload(project, file, current_user, db)


@router.get(
    "/materials",
    response_model=list[MaterialOut],
)
async def list_materials_direct(
    project_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    await _verify_project_access_by_id(project_id, current_user.id, db)
    result = await db.execute(
        select(Material).where(
            Material.project_id == project_id,
            Material.user_id == current_user.id,
        ).order_by(Material.created_at.desc())
    )
    materials = result.scalars().all()
    return [
        MaterialOut(
            id=m.id,
            original_filename=m.original_filename,
            file_size=m.file_size,
            status=m.status.value,
            error_message=m.error_message,
            page_count=m.page_count,
            created_at=m.created_at,
            processed_at=m.processed_at,
        )
        for m in materials
    ]


@router.get(
    "/materials/{material_id}",
    response_model=MaterialOut,
)
async def get_material_direct(
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Material).where(
            Material.id == material_id,
            Material.user_id == current_user.id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    return MaterialOut(
        id=material.id,
        original_filename=material.original_filename,
        file_size=material.file_size,
        status=material.status.value,
        error_message=material.error_message,
        page_count=material.page_count,
        created_at=material.created_at,
        processed_at=material.processed_at,
    )


@router.get("/materials/{material_id}/chunks")
async def get_material_chunks(
    material_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """View extracted chunks and metadata for a processed material."""
    result = await db.execute(
        select(Material).where(
            Material.id == material_id,
            Material.user_id == current_user.id,
        )
    )
    material = result.scalar_one_or_none()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    chunks_res = await db.execute(
        select(Chunk).where(
            Chunk.material_id == material_id,
            Chunk.user_id == current_user.id,
        ).order_by(Chunk.page_number.asc(), Chunk.chunk_index.asc())
    )
    chunks = chunks_res.scalars().all()

    return [
        {
            "id": str(c.id),
            "page_number": c.page_number,
            "chunk_index": c.chunk_index,
            "content": c.content,
            "token_count": c.token_count,
            "has_embedding": c.embedding is not None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in chunks
    ]
