from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime, timezone

from db.database import get_db
from models.lot import Lot
from models.user import User, SubscriptionPlan
from api.users import get_current_user, get_current_user_optional
from services.ai_assessment import assess_lot, lot_to_ai_dict

router = APIRouter()

# AI-оценка во время beta открыта для всех залогиненных
AI_ALLOWED_PLANS = {SubscriptionPlan.FREE, SubscriptionPlan.PRO, SubscriptionPlan.INVESTOR, SubscriptionPlan.BURO, SubscriptionPlan.BURO_PLUS, SubscriptionPlan.ENTERPRISE}


# Инвестор НЕ безлимитный — у него 100 аудитов/мес через пополнение free_audits_left.
UNLIMITED_PLANS = {SubscriptionPlan.BURO, SubscriptionPlan.BURO_PLUS, SubscriptionPlan.ENTERPRISE}


@router.post("/assess/{lot_id}")
async def request_assessment(
    lot_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.subscription_plan not in AI_ALLOWED_PLANS:
        raise HTTPException(
            status_code=403,
            detail="Войдите в аккаунт чтобы получить AI-оценку"
        )

    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    # Кэш — без списания. Бюро/Бюро+/Enterprise — без лимита и кэша.
    is_cached = False
    # Кэш по отпечатку: если ключевые поля лота не менялись и оценка не старше 30 дней —
    # отдаём кэш и не тратим API. Раньше был 24-часовой TTL без учёта данных — каждое утро
    # одни и те же лоты пере-оценивались (~500₽/сутки лишних).
    from services.ai_assessment import compute_ai_fingerprint
    current_fp = compute_ai_fingerprint(lot)
    if lot.ai_assessment and lot.ai_assessed_at and lot.ai_assessment_hash == current_fp:
        age_days = (datetime.now(timezone.utc) - lot.ai_assessed_at).total_seconds() / 86400
        if age_days < 30:
            is_cached = True
            await _record_audit_purchase(db, user.id, lot_id)
            return {"lot_id": lot_id, "assessment": lot.ai_assessment, "cached": True}

    # Лимиты: Free/Pro расходуют free_audits_left; Бюро+ — без лимита.
    # Списание АТОМАРНОЕ (UPDATE ... WHERE free_audits_left > 0): иначе параллельные
    # запросы проходят проверку до декремента и жгут больше платных AI-вызовов, чем лимит.
    if user.subscription_plan not in UNLIMITED_PLANS:
        res = await db.execute(
            update(User)
            .where(User.id == user.id, User.free_audits_left > 0)
            .values(free_audits_left=User.free_audits_left - 1)
            .returning(User.free_audits_left)
        )
        if res.first() is None:
            raise HTTPException(
                status_code=402,
                detail="Лимит бесплатных AI-аудитов исчерпан. Купите разовый аудит за 490 ₽ или подключите тариф Бюро.",
            )
        await db.commit()

    # Если AI-провайдер недоступен (нет баланса / rate limit / упал сервер) —
    # возвращаем free_audits_left обратно и говорим пользователю понятным текстом.
    try:
        assessment = await assess_lot(lot_to_ai_dict(lot))
    except Exception as e:
        # Откат списанного free-аудита при сбое AI (атомарно, без гонки).
        if user.subscription_plan not in UNLIMITED_PLANS:
            await db.execute(
                update(User)
                .where(User.id == user.id)
                .values(free_audits_left=User.free_audits_left + 1)
            )
            await db.commit()
        err_text = str(e)
        if "402" in err_text or "Insufficient balance" in err_text or "credit" in err_text.lower():
            raise HTTPException(
                status_code=503,
                detail="AI-оценка временно недоступна. Мы уже работаем над восстановлением — попробуйте через несколько минут.",
            )
        if "429" in err_text or "rate" in err_text.lower():
            raise HTTPException(
                status_code=503,
                detail="AI-сервис сейчас перегружен. Попробуйте через минуту.",
            )
        raise HTTPException(
            status_code=503,
            detail="AI-оценка временно недоступна. Попробуйте позже.",
        )

    lot.ai_assessment = assessment
    lot.ai_assessed_at = datetime.now(timezone.utc)
    lot.ai_assessment_hash = current_fp
    await db.commit()
    await _record_audit_purchase(db, user.id, lot_id)

    return {"lot_id": lot_id, "assessment": assessment, "cached": False}


async def _record_audit_purchase(db: AsyncSession, user_id: int, lot_id: int) -> None:
    """Фиксируем аудит в истории пользователя (идемпотентно, ON CONFLICT DO NOTHING).
    Запись даёт постоянный доступ к оценке лота (независимо от тарифа) и строит
    таблицу «Мои AI-аудиты» в кабинете."""
    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        from models.user import AiAuditPurchase
        stmt = pg_insert(AiAuditPurchase).values(
            user_id=user_id, lot_id=lot_id, created_at=datetime.now(timezone.utc)
        ).on_conflict_do_nothing(constraint="uq_ai_audit_user_lot")
        await db.execute(stmt)
        await db.commit()
    except Exception as e:
        # История — не повод ронять сам аудит
        print(f"[ai-audit] purchase record error: {type(e).__name__}: {e}")


@router.get("/assess/{lot_id}")
async def get_assessment(
    lot_id: int,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Получить готовую AI-оценку. Pro+ видит батч-оценку по тарифу; Free —
    только лоты из своей истории аудитов (потратил квоту/купил разово).
    Аноним → assessment=None (фронт зовёт войти)."""
    if user is None:
        return {"lot_id": lot_id, "assessment": None}
    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")
    if not lot.ai_assessment:
        return {"lot_id": lot_id, "assessment": None}
    from core.plans import plan_rank, RANK_PRO
    if plan_rank(user) < RANK_PRO:
        from models.user import AiAuditPurchase
        purchased = (await db.execute(
            select(AiAuditPurchase.id).where(
                AiAuditPurchase.user_id == user.id,
                AiAuditPurchase.lot_id == lot_id,
            )
        )).scalar_one_or_none()
        if purchased is None:
            # locked=true — фронт показывает CTA «потратить аудит / купить Pro»
            return {"lot_id": lot_id, "assessment": None, "locked": True}
    return {"lot_id": lot_id, "assessment": lot.ai_assessment}


@router.get("/my-audits")
async def my_audits(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Таблица «Мои AI-аудиты» в кабинете: какие лоты аудировал пользователь."""
    from models.user import AiAuditPurchase
    rows = (await db.execute(
        select(AiAuditPurchase, Lot)
        .join(Lot, Lot.id == AiAuditPurchase.lot_id)
        .where(AiAuditPurchase.user_id == user.id)
        .order_by(AiAuditPurchase.created_at.desc())
        .limit(200)
    )).all()
    items = []
    for p, lot in rows:
        a = lot.ai_assessment if isinstance(lot.ai_assessment, dict) else {}
        items.append({
            "lot_id": lot.id,
            "title": lot.title,
            "region_name": lot.region_name,
            "start_price": float(lot.start_price) if lot.start_price else None,
            "status": lot.status.value if lot.status else None,
            "audited_at": p.created_at.isoformat() if p.created_at else None,
            "ai_score": a.get("score"),
            "ai_strategy": a.get("best_strategy"),
        })
    return {"items": items, "total": len(items), "audits_left": user.free_audits_left or 0}
