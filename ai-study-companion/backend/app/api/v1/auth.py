"""Authentication API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import uuid

from app.db.session import get_db
from app.models.models import User, UserRole, Event
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. Role is always 'user' — admin provisioned via ADMIN_EMAIL."""
    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == body.email.lower()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if this user matches the configured ADMIN_EMAIL
    from app.core.config import settings
    is_admin = bool(settings.ADMIN_EMAIL and body.email.lower() == settings.ADMIN_EMAIL.lower())

    user = User(
        id=uuid.uuid4(),
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        display_name=body.display_name.strip(),
        role=UserRole.admin if is_admin else UserRole.user,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)

    # Track registration event
    event = Event(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type="user_registered",
        payload={"email": user.email},
    )
    db.add(event)
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        display_name=user.display_name,
        role=user.role.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last active
    user.last_active_at = datetime.now(timezone.utc)
    await db.commit()

    token = create_access_token(str(user.id))
    return TokenResponse(
        access_token=token,
        user_id=str(user.id),
        display_name=user.display_name,
        role=user.role.value,
    )


@router.get("/me")
async def get_me(current_user=Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "role": current_user.role.value,
        "created_at": current_user.created_at.isoformat(),
    }
