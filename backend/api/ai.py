from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from db.database import get_db
from models.lot import Lot
from models.user import User, SubscriptionPlan
from api.users import get_current_user
from services.ai_assessment import assess_lot, lot_to_ai_dict

router = APIRouter()

# AI-оценка во время beta открыта для всех залогиненных
AI_ALLOWED_PLANS = {SubscriptionPlan.FREE, SubscriptionPlan.PRO, SubscriptionPlan.BURO, SubscriptionPlan.BURO_PLUS, SubscriptionPlan.ENTERPRISE}


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
    if lot.ai_assessment and lot.ai_assessed_at:
        age_hours = (datetime.now(timezone.utc) - lot.ai_assessed_at).total_seconds() / 3600
        if age_hours < 24:
            is_cached = True
            return {"lot_id": lot_id, "assessment": lot.ai_assessment, "cached": True}

    # Лимиты: Free/Pro расходуют free_audits_left на аналитику; Бюро+ — без лимита.
    if user.subscription_plan not in UNLIMITED_PLANS:
        if (user.free_audits_left or 0) <= 0:
            raise HTTPException(
                status_code=402,
                detail="Лимит бесплатных AI-аудитов исчерпан. Купите разовый аудит за 490 ₽ или подключите тариф Бюро.",
            )
        # Списываем — для рестрикций, чтобы не зацикливалось на одной активной транзакции
        user.free_audits_left = (user.free_audits_left or 0) - 1
        await db.commit()

    assessment = await assess_lot(lot_to_ai_dict(lot))

    lot.ai_assessment = assessment
    lot.ai_assessed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"lot_id": lot_id, "assessment": assessment, "cached": False}


@router.get("/assess/{lot_id}")
async def get_assessment(lot_id: int, db: AsyncSession = Depends(get_db)):
    """Получить уже готовую оценку (без авторизации — для отображения на карточке)"""
    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")
    if not lot.ai_assessment:
        return {"lot_id": lot_id, "assessment": None}
    return {"lot_id": lot_id, "assessment": lot.ai_assessment}
