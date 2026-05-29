from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.models.models import User, UserRole
from app.schemas.schemas import UserListOut
from app.api.deps import get_current_trainer
from app.core.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserListOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(
        select(User).options(selectinload(User.team)).order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        UserListOut(
            id=u.id,
            username=u.username,
            email=u.email,
            role=u.role,
            team_id=u.team_id,
            team_name=u.team.name if u.team else None,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.put("/{user_id}/role")
async def set_user_role(
    user_id: int,
    role: UserRole,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.role = role
    return {"user_id": user_id, "role": role}


@router.put("/{user_id}/active")
async def set_user_active(
    user_id: int,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = is_active
    return {"user_id": user_id, "is_active": is_active}


@router.post("/seed-trainer")
async def seed_trainer(
    username: str,
    password: str,
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """One-time use: create the first trainer account. Disabled once a trainer exists."""
    existing_trainer = await db.execute(select(User).where(User.role == UserRole.trainer))
    if existing_trainer.scalar_one_or_none():
        raise HTTPException(403, "Trainer already exists")

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=UserRole.trainer,
    )
    db.add(user)
    await db.flush()
    return {"created": user.id}


@router.post("/admin/reset-db", status_code=200)
async def reset_database(
    db: AsyncSession = Depends(get_db),
    _trainer: User = Depends(get_current_trainer),
):
    """Drop and recreate all tables. Wipes all data. Trainer only."""
    from app.db.session import engine, Base
    from app.models import models  # noqa — ensure all models are loaded
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    return {"reset": True, "message": "Database wiped and schema recreated."}
