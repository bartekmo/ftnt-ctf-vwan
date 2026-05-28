from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import RegisterRequest, LoginRequest, TokenResponse, UserOut
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already taken")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=UserRole.attendee,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, username=user.username, email=user.email, role=user.role),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Eagerly load the team relationship in the same query — avoids lazy-load
    # greenlet error when accessing user.team.name outside an async context.
    result = await db.execute(
        select(User)
        .where(User.username == body.username)
        .options(selectinload(User.team))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    team_name = user.team.name if user.team else None

    token = create_access_token({"sub": str(user.id), "role": user.role})
    return TokenResponse(
        access_token=token,
        user=UserOut(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            team_id=user.team_id,
            team_name=team_name,
        ),
    )


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Eagerly load the team in the same query rather than relying on refresh
    result = await db.execute(
        select(User)
        .where(User.id == current_user.id)
        .options(selectinload(User.team))
    )
    user = result.scalar_one()
    team_name = user.team.name if user.team else None
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        team_id=user.team_id,
        team_name=team_name,
    )
