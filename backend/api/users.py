from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timezone
from typing import Optional

from db.database import get_db
from models.user import User, SubscriptionPlan
from core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, oauth2_scheme, oauth2_scheme_optional

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    utm_source: Optional[str] = None      # из ?utm_source — TG-канал, blog и т.д.
    utm_campaign: Optional[str] = None
    referral_code: Optional[str] = None   # из ?ref=XXXX — код пригласившего


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
    free_audits_left: int = 0
    is_admin: bool = False

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


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Как get_current_user, но возвращает None для неавторизованных вместо 401.

    Нужно для public endpoint'ов, которые отдают расширенные данные авторизованным
    (например, контакты администрации только для Pro+).
    """
    if not token:
        return None
    try:
        user_id = decode_token(token)
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            return None
        return user
    except Exception:
        return None


PLAN_FILTER_LIMITS = {
    SubscriptionPlan.FREE: 1,
    SubscriptionPlan.PRO: 5,
    SubscriptionPlan.BURO: 15,
    SubscriptionPlan.BURO_PLUS: 30,
    SubscriptionPlan.ENTERPRISE: 100,
}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    import secrets as _s

    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    # Реферальный код пригласившего → находим его и даём бонус +1 аудит обоим
    referrer = None
    if data.referral_code:
        ref_norm = data.referral_code.strip().upper()
        referrer_q = await db.execute(select(User).where(User.referral_code == ref_norm))
        referrer = referrer_q.scalar_one_or_none()
        if referrer:
            referrer.free_audits_left = (referrer.free_audits_left or 0) + 1

    # Свой реферальный код (8 символов URL-safe, в верхнем регистре)
    own_code = _s.token_urlsafe(6).rstrip("-_=")[:8].upper()

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        name=data.name,
        subscription_plan=SubscriptionPlan.FREE,
        saved_filters_limit=PLAN_FILTER_LIMITS[SubscriptionPlan.FREE],
        free_audits_left=2 if referrer else 1,  # +1 бонус если по реф-ссылке
        signup_source=(data.utm_source or ("ref" if referrer else "direct"))[:80],
        signup_campaign=(data.utm_campaign or None) and data.utm_campaign[:80],
        referral_code=own_code,
        referred_by=referrer.id if referrer else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Welcome email — асинхронно, не блокирует регистрацию
    try:
        from services.welcome_email import send_welcome_email
        import asyncio as _asyncio
        _asyncio.create_task(send_welcome_email(user))
    except Exception as e:
        print(f"[welcome] error: {type(e).__name__}: {e}")

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
        free_audits_left=user.free_audits_left or 0,
        is_admin=user.is_admin or False,
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
        free_audits_left=user.free_audits_left or 0,
        is_admin=user.is_admin or False,
    )


@router.get("/referral")
async def my_referral(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Реферальная статистика и ссылка для приглашений."""
    from models.alert import Subscription
    from sqlalchemy import func, distinct

    invited_count = (await db.execute(
        select(func.count()).select_from(User).where(User.referred_by == user.id)
    )).scalar() or 0

    # Сколько приглашённых сделали хотя бы одну успешную покупку
    paying_q = await db.execute(
        select(func.count(distinct(Subscription.user_id)))
        .join(User, User.id == Subscription.user_id)
        .where(User.referred_by == user.id, Subscription.status == "succeeded")
    )
    invited_paying = paying_q.scalar() or 0

    return {
        "code": user.referral_code,
        "url": f"https://xn--e1adnd0h.online/register?ref={user.referral_code}",
        "invited_count": invited_count,
        "invited_paying": invited_paying,
        "free_audits_left": user.free_audits_left or 0,
    }


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


@router.get("/subscriptions")
async def get_payment_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """История покупок пользователя — оплаченные и pending подписки/разовые услуги."""
    from models.alert import Subscription
    from sqlalchemy import desc

    rows = (await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(desc(Subscription.created_at))
        .limit(100)
    )).scalars().all()

    return {
        "items": [
            {
                "id": s.id,
                "plan": s.plan,
                "amount": s.amount,
                "currency": s.currency,
                "months": s.months,
                "status": s.status,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "paid_at": s.paid_at.isoformat() if s.paid_at else None,
            }
            for s in rows
        ]
    }


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
