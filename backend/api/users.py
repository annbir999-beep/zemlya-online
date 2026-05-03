from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from typing import Optional

from db.database import get_db
from models.user import User, SubscriptionPlan
from core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, oauth2_scheme

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: int
    email: str
    name: Optional[str]
    phone: Optional[str]
    telegram_id: Optional[str]
    subscription_plan: str
    subscription_expires_at: Optional[str]
    saved_filters_limit: int
    notification_email: bool
    notification_telegram: bool
    is_verified: bool

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    telegram_id: Optional[str] = None
    notification_email: Optional[bool] = None
    notification_telegram: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Невалидный токен")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return user


PLAN_FILTER_LIMITS = {
    SubscriptionPlan.FREE: 3,
    SubscriptionPlan.PERSONAL: 5,
    SubscriptionPlan.EXPERT: 15,
    SubscriptionPlan.LANDLORD: 30,
}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name,
        subscription_plan=SubscriptionPlan.FREE,
        saved_filters_limit=PLAN_FILTER_LIMITS[SubscriptionPlan.FREE],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт заблокирован")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    user_id = decode_token(refresh_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Невалидный refresh токен")
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(user: User = Depends(get_current_user)):
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        telegram_id=user.telegram_id,
        subscription_plan=user.subscription_plan.value,
        subscription_expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        saved_filters_limit=user.saved_filters_limit,
        notification_email=user.notification_email,
        notification_telegram=user.notification_telegram,
        is_verified=user.is_verified,
    )


@router.patch("/me", response_model=UserProfile)
async def update_profile(
    data: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.name is not None:
        user.name = data.name
    if data.phone is not None:
        user.phone = data.phone
    if data.telegram_id is not None:
        user.telegram_id = data.telegram_id
    if data.notification_email is not None:
        user.notification_email = data.notification_email
    if data.notification_telegram is not None:
        user.notification_telegram = data.notification_telegram

    await db.commit()
    await db.refresh(user)

    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        telegram_id=user.telegram_id,
        subscription_plan=user.subscription_plan.value,
        subscription_expires_at=user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        saved_filters_limit=user.saved_filters_limit,
        notification_email=user.notification_email,
        notification_telegram=user.notification_telegram,
        is_verified=user.is_verified,
    )


@router.get("/saved-lots")
async def get_saved_lots(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from models.user import SavedLot
    from models.lot import Lot
    q = select(Lot).join(SavedLot, SavedLot.lot_id == Lot.id).where(SavedLot.user_id == user.id)
    result = await db.execute(q)
    lots = result.scalars().all()
    return {"items": [{"id": l.id, "title": l.title, "start_price": l.start_price, "area_sqm": l.area_sqm, "status": l.status.value} for l in lots]}


@router.post("/saved-lots/{lot_id}")
async def save_lot(lot_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from models.user import SavedLot
    existing = await db.execute(select(SavedLot).where(SavedLot.user_id == user.id, SavedLot.lot_id == lot_id))
    if existing.scalar_one_or_none():
        return {"status": "already_saved"}
    db.add(SavedLot(user_id=user.id, lot_id=lot_id))
    await db.commit()
    return {"status": "saved"}


@router.delete("/saved-lots/{lot_id}")
async def unsave_lot(lot_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from models.user import SavedLot
    result = await db.execute(select(SavedLot).where(SavedLot.user_id == user.id, SavedLot.lot_id == lot_id))
    saved = result.scalar_one_or_none()
    if saved:
        await db.delete(saved)
        await db.commit()
    return {"status": "removed"}


@router.post("/views/{lot_id}")
async def record_view(lot_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Записывает просмотр лота. Дедуп: не более одной записи за 60 минут."""
    from models.user import LotView
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
    recent = await db.execute(
        select(LotView)
        .where(LotView.user_id == user.id, LotView.lot_id == lot_id, LotView.viewed_at >= cutoff)
        .order_by(LotView.viewed_at.desc())
        .limit(1)
    )
    if recent.scalar_one_or_none():
        return {"status": "deduped"}
    db.add(LotView(user_id=user.id, lot_id=lot_id))
    await db.commit()
    return {"status": "recorded"}


@router.get("/views")
async def get_view_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Последние 50 уникальных лотов, отсортированных по последнему просмотру."""
    from models.user import LotView
    from models.lot import Lot
    from sqlalchemy import func as _func, desc

    # Берём максимальный viewed_at для каждого lot_id, сортируем по нему
    subq = (
        select(LotView.lot_id, _func.max(LotView.viewed_at).label("last_view"))
        .where(LotView.user_id == user.id)
        .group_by(LotView.lot_id)
        .order_by(desc("last_view"))
        .limit(50)
        .subquery()
    )
    q = (
        select(Lot, subq.c.last_view)
        .join(subq, Lot.id == subq.c.lot_id)
        .order_by(desc(subq.c.last_view))
    )
    rows = (await db.execute(q)).all()
    return {
        "items": [
            {
                "id": l.id,
                "title": l.title,
                "start_price": l.start_price,
                "area_sqm": l.area_sqm,
                "region_name": l.region_name,
                "status": l.status.value if l.status else None,
                "score": l.score,
                "viewed_at": last_view.isoformat() if last_view else None,
            }
            for l, last_view in rows
        ]
    }
