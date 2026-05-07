"""
Админ-API для владельца проекта. Защищён флагом User.is_admin.

Что делает:
  · /api/admin/stats      — сводка: пользователи, выручка, конверсия
  · /api/admin/users      — список пользователей + поиск
  · /api/admin/users/{id} — изменить (активировать тариф, выдать аудиты, is_admin)
  · /api/admin/promos     — CRUD промокодов
  · /api/admin/subscriptions — список платежей с фильтрами
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.user import User, SubscriptionPlan
from models.alert import Subscription
from models.promo import PromoCode, PromoUsage
from api.users import get_current_user, PLAN_FILTER_LIMITS


router = APIRouter()


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Доступ только для администратора")
    return user


# ── Сводка ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_users = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    paying_users = (await db.execute(
        select(func.count(func.distinct(Subscription.user_id))).where(Subscription.status == "succeeded")
    )).scalar() or 0
    new_users_week = (await db.execute(
        select(func.count()).select_from(User).where(User.created_at >= week_ago)
    )).scalar() or 0

    revenue_total = (await db.execute(
        select(func.coalesce(func.sum(Subscription.amount), 0)).where(Subscription.status == "succeeded")
    )).scalar() or 0
    revenue_30d = (await db.execute(
        select(func.coalesce(func.sum(Subscription.amount), 0)).where(
            and_(Subscription.status == "succeeded", Subscription.paid_at >= month_ago)
        )
    )).scalar() or 0

    paid_total = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == "succeeded")
    )).scalar() or 0
    pending_total = (await db.execute(
        select(func.count()).select_from(Subscription).where(Subscription.status == "pending")
    )).scalar() or 0

    # По тарифам
    by_plan_rows = (await db.execute(
        select(User.subscription_plan, func.count(User.id))
        .group_by(User.subscription_plan)
    )).all()
    by_plan = {(r[0].value if r[0] else "free"): r[1] for r in by_plan_rows}

    return {
        "users": {
            "total": total_users,
            "paying": paying_users,
            "new_7d": new_users_week,
            "by_plan": by_plan,
            "conversion_pct": round(paying_users / total_users * 100, 1) if total_users else 0,
        },
        "revenue": {
            "total": int(revenue_total),
            "last_30d": int(revenue_30d),
        },
        "subscriptions": {
            "succeeded": paid_total,
            "pending": pending_total,
        },
    }


# ── Пользователи ───────────────────────────────────────────────────────────────

class UserPatchRequest(BaseModel):
    plan: Optional[str] = None              # free / pro / buro / buro_plus / enterprise
    plan_months: Optional[int] = None       # 1 / 3 / 12 — продлить от текущей даты
    free_audits_add: Optional[int] = None   # +N к free_audits_left
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


PLAN_ID_TO_ENUM = {
    "free": SubscriptionPlan.FREE,
    "pro": SubscriptionPlan.PRO,
    "buro": SubscriptionPlan.BURO,
    "buro_plus": SubscriptionPlan.BURO_PLUS,
    "enterprise": SubscriptionPlan.ENTERPRISE,
}


@router.get("/users")
async def list_users(
    q: Optional[str] = Query(None, max_length=200),
    plan: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if q:
        pat = f"%{q.strip()}%"
        conditions.append(or_(User.email.ilike(pat), User.name.ilike(pat)))
    if plan and plan in PLAN_ID_TO_ENUM:
        conditions.append(User.subscription_plan == PLAN_ID_TO_ENUM[plan])

    where = and_(*conditions) if conditions else None
    base_q = select(User)
    if where is not None:
        base_q = base_q.where(where)

    total_q = select(func.count()).select_from(User)
    if where is not None:
        total_q = total_q.where(where)
    total = (await db.execute(total_q)).scalar() or 0

    offset = (page - 1) * per_page
    rows = (await db.execute(
        base_q.order_by(User.created_at.desc()).offset(offset).limit(per_page)
    )).scalars().all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": u.id,
                "email": u.email,
                "name": u.name,
                "plan": u.subscription_plan.value if u.subscription_plan else "free",
                "expires_at": u.subscription_expires_at.isoformat() if u.subscription_expires_at else None,
                "free_audits_left": u.free_audits_left or 0,
                "is_admin": u.is_admin,
                "is_active": u.is_active,
                "telegram_id": u.telegram_id,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ],
    }


@router.patch("/users/{user_id}")
async def patch_user(
    user_id: int,
    data: UserPatchRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if data.plan is not None:
        if data.plan not in PLAN_ID_TO_ENUM:
            raise HTTPException(status_code=400, detail="Неизвестный план")
        target.subscription_plan = PLAN_ID_TO_ENUM[data.plan]
        target.saved_filters_limit = PLAN_FILTER_LIMITS.get(target.subscription_plan, 1)
        # Если активируем платный — продляем срок
        if data.plan != "free" and data.plan_months:
            now = datetime.now(timezone.utc)
            base = target.subscription_expires_at if target.subscription_expires_at and target.subscription_expires_at > now else now
            target.subscription_expires_at = base + timedelta(days=30 * int(data.plan_months))

    if data.free_audits_add is not None:
        target.free_audits_left = (target.free_audits_left or 0) + int(data.free_audits_add)

    if data.is_admin is not None:
        target.is_admin = bool(data.is_admin)
    if data.is_active is not None:
        target.is_active = bool(data.is_active)

    await db.commit()
    await db.refresh(target)
    return {
        "id": target.id,
        "email": target.email,
        "plan": target.subscription_plan.value,
        "expires_at": target.subscription_expires_at.isoformat() if target.subscription_expires_at else None,
        "free_audits_left": target.free_audits_left or 0,
        "is_admin": target.is_admin,
        "is_active": target.is_active,
    }


# ── Промокоды ──────────────────────────────────────────────────────────────────

class PromoCreateRequest(BaseModel):
    code: str
    discount_pct: Optional[int] = None
    discount_fixed: Optional[int] = None
    max_uses: Optional[int] = None
    valid_until: Optional[str] = None
    plan_filter: Optional[str] = None
    new_users_only: bool = False
    description: Optional[str] = None


class PromoPatchRequest(BaseModel):
    is_active: Optional[bool] = None
    max_uses: Optional[int] = None
    valid_until: Optional[str] = None


@router.get("/promos")
async def list_promos(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(PromoCode).order_by(PromoCode.created_at.desc())
    )).scalars().all()
    return {
        "items": [
            {
                "id": p.id,
                "code": p.code,
                "discount_pct": p.discount_pct,
                "discount_fixed": p.discount_fixed,
                "max_uses": p.max_uses,
                "used_count": p.used_count or 0,
                "valid_until": p.valid_until.isoformat() if p.valid_until else None,
                "plan_filter": p.plan_filter,
                "new_users_only": p.new_users_only,
                "is_active": p.is_active,
                "description": p.description,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ]
    }


@router.post("/promos")
async def create_promo(
    data: PromoCreateRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    code_norm = data.code.strip().upper()
    if not code_norm:
        raise HTTPException(status_code=400, detail="Код не может быть пустым")
    if not data.discount_pct and not data.discount_fixed:
        raise HTTPException(status_code=400, detail="Укажите discount_pct или discount_fixed")

    existing = await db.execute(select(PromoCode).where(PromoCode.code == code_norm))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Промокод с таким кодом уже есть")

    valid_until = None
    if data.valid_until:
        try:
            valid_until = datetime.fromisoformat(data.valid_until.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="valid_until: неверный формат даты")

    promo = PromoCode(
        code=code_norm,
        discount_pct=data.discount_pct,
        discount_fixed=data.discount_fixed,
        max_uses=data.max_uses,
        valid_until=valid_until,
        plan_filter=data.plan_filter,
        new_users_only=data.new_users_only,
        description=data.description,
    )
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return {"id": promo.id, "code": promo.code}


@router.patch("/promos/{promo_id}")
async def patch_promo(
    promo_id: int,
    data: PromoPatchRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PromoCode).where(PromoCode.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Промокод не найден")

    if data.is_active is not None:
        promo.is_active = bool(data.is_active)
    if data.max_uses is not None:
        promo.max_uses = data.max_uses
    if data.valid_until is not None:
        try:
            promo.valid_until = datetime.fromisoformat(data.valid_until.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=400, detail="valid_until: неверный формат")

    await db.commit()
    return {"id": promo.id, "is_active": promo.is_active}


# ── Воронка ───────────────────────────────────────────────────────────────────

@router.get("/funnel")
async def admin_funnel(
    days: int = Query(30, ge=7, le=180),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Дашборд воронки: регистрации, платящие, источники, промокоды.

    Конверсия считается так: посетитель → регистрация (есть в БД) →
    первый успешный платёж (есть в БД). Visitor-метрики (просмотры
    страниц) пока не пишем — сбор UV нужно делать через Я.Метрику или
    Plausible, отдельно.
    """
    from models.alert import Subscription
    from models.promo import PromoCode, PromoUsage

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)

    # Регистрации по дням
    regs = (await db.execute(
        select(func.date(User.created_at).label("d"), func.count(User.id))
        .where(User.created_at >= since)
        .group_by(func.date(User.created_at))
        .order_by(func.date(User.created_at))
    )).all()
    daily_registrations = [{"date": r[0].isoformat() if r[0] else None, "count": r[1]} for r in regs]

    # Платежи по дням (succeeded)
    pays = (await db.execute(
        select(
            func.date(Subscription.paid_at).label("d"),
            func.count(Subscription.id),
            func.sum(Subscription.amount),
        )
        .where(and_(Subscription.status == "succeeded", Subscription.paid_at >= since))
        .group_by(func.date(Subscription.paid_at))
        .order_by(func.date(Subscription.paid_at))
    )).all()
    daily_payments = [
        {"date": r[0].isoformat() if r[0] else None, "count": r[1], "revenue": int(r[2] or 0)}
        for r in pays
    ]

    # Источники регистраций
    sources = (await db.execute(
        select(func.coalesce(User.signup_source, "direct"), func.count(User.id))
        .where(User.created_at >= since)
        .group_by(func.coalesce(User.signup_source, "direct"))
        .order_by(func.count(User.id).desc())
    )).all()
    by_source = [{"source": r[0], "count": r[1]} for r in sources]

    # Промокоды — топ
    promo_top = (await db.execute(
        select(
            PromoCode.code,
            PromoCode.used_count,
            PromoCode.discount_pct,
            PromoCode.discount_fixed,
            func.coalesce(func.sum(PromoUsage.discount_applied), 0).label("total_discount"),
        )
        .outerjoin(PromoUsage, PromoUsage.promo_code_id == PromoCode.id)
        .group_by(PromoCode.id)
        .order_by(PromoCode.used_count.desc().nulls_last())
        .limit(10)
    )).all()
    by_promo = [
        {
            "code": r[0],
            "used_count": r[1] or 0,
            "discount": (f"{r[2]}%" if r[2] else f"{r[3]}₽") if (r[2] or r[3]) else "—",
            "total_discount": int(r[4] or 0),
        }
        for r in promo_top
    ]

    # Воронка-сводка за период
    total_regs = sum(r["count"] for r in daily_registrations)
    total_payers = (await db.execute(
        select(func.count(func.distinct(Subscription.user_id)))
        .join(User, User.id == Subscription.user_id)
        .where(and_(Subscription.status == "succeeded", User.created_at >= since))
    )).scalar() or 0
    total_revenue = sum(r["revenue"] for r in daily_payments)

    # Среднее время от регистрации до первой покупки (часы)
    ttl_q = (await db.execute(
        select(
            func.avg(
                func.extract("epoch", Subscription.paid_at - User.created_at) / 3600
            )
        )
        .join(User, User.id == Subscription.user_id)
        .where(and_(Subscription.status == "succeeded", User.created_at >= since))
    )).scalar()
    avg_ttp_hours = round(float(ttl_q), 1) if ttl_q else None

    return {
        "period_days": days,
        "summary": {
            "registrations": total_regs,
            "payers": total_payers,
            "conversion_pct": round(total_payers / total_regs * 100, 1) if total_regs else 0,
            "revenue": total_revenue,
            "avg_time_to_purchase_hours": avg_ttp_hours,
        },
        "daily_registrations": daily_registrations,
        "daily_payments": daily_payments,
        "by_source": by_source,
        "by_promo": by_promo,
    }


# ── Подписки/платежи ───────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(
    status: Optional[str] = Query(None, pattern="^(succeeded|pending|failed)$"),
    user_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    conds = []
    if status:
        conds.append(Subscription.status == status)
    if user_id:
        conds.append(Subscription.user_id == user_id)

    base_q = select(Subscription, User).join(User, User.id == Subscription.user_id)
    if conds:
        base_q = base_q.where(and_(*conds))

    total_q = select(func.count()).select_from(Subscription)
    if conds:
        total_q = total_q.where(and_(*conds))
    total = (await db.execute(total_q)).scalar() or 0

    offset = (page - 1) * per_page
    rows = (await db.execute(
        base_q.order_by(Subscription.created_at.desc()).offset(offset).limit(per_page)
    )).all()

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": s.id,
                "user_id": s.user_id,
                "user_email": u.email,
                "plan": s.plan,
                "amount": s.amount,
                "months": s.months,
                "status": s.status,
                "yukassa_payment_id": s.yukassa_payment_id,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "paid_at": s.paid_at.isoformat() if s.paid_at else None,
            }
            for s, u in rows
        ],
    }
