from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from db.database import get_db
from models.lot import Lot
from models.user import User, SubscriptionPlan
from api.users import get_current_user
from services.ai_assessment import assess_lot

router = APIRouter()

# AI-оценка во время beta открыта для всех залогиненных
AI_ALLOWED_PLANS = {SubscriptionPlan.FREE, SubscriptionPlan.PERSONAL, SubscriptionPlan.EXPERT, SubscriptionPlan.LANDLORD}


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

    # Если оценка свежая (< 24ч) — возвращаем кэш
    if lot.ai_assessment and lot.ai_assessed_at:
        age_hours = (datetime.now(timezone.utc) - lot.ai_assessed_at).total_seconds() / 3600
        if age_hours < 24:
            return {"lot_id": lot_id, "assessment": lot.ai_assessment, "cached": True}

    lot_dict = {
        "title": lot.title,
        "cadastral_number": lot.cadastral_number,
        "start_price": lot.start_price,
        "area_sqm": lot.area_sqm,
        "area_ha": lot.area_ha,
        "land_purpose_raw": lot.land_purpose_raw,
        "auction_type": lot.auction_type.value if lot.auction_type else None,
        "region_name": lot.region_name,
        "address": lot.address,
        "auction_end_date": lot.auction_end_date.isoformat() if lot.auction_end_date else None,
        "organizer_name": lot.organizer_name,
        "description": lot.description,
        "rosreestr_data": lot.rosreestr_data,
    }

    assessment = await assess_lot(lot_dict)

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
