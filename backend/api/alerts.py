from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List

from db.database import get_db
from models.alert import Alert, AlertChannel
from models.user import User
from api.users import get_current_user

router = APIRouter()


class AlertFilters(BaseModel):
    region_codes: Optional[List[str]] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    land_purposes: Optional[List[str]] = None
    # «Вид сделки» (купля-продажа / аренда / приватизация и т.д.) — что именно приобретается
    auction_types: Optional[List[str]] = None
    # «Вид торгов» (аукцион / конкурс / публичное предложение / без торгов) — форма проведения
    auction_forms: Optional[List[str]] = None
    deal_types: Optional[List[str]] = None  # ownership / lease / free_use / operational
    keywords: Optional[str] = None
    # Скоринг и финансы
    score_min: Optional[int] = None              # минимальная инвестпривлекательность (0-100)
    badges_min: Optional[int] = None             # минимальное число бейджей
    discount_min: Optional[float] = None         # мин. дисконт к рынку, %
    price_drop_min: Optional[float] = None       # мин. % снижения цены на повторных торгах
    liquidity: Optional[str] = None              # high / medium / low
    pct_cadastral_max: Optional[float] = None    # макс. цена в % от кадастровой
    cadastral_to_market_min: Optional[float] = None  # КС/Рынок ≥ X% (искать переоценённые)
    cadastral_to_market_max: Optional[float] = None  # КС/Рынок ≤ X% (искать недооценённые)
    cadastral_cost_min: Optional[float] = None
    cadastral_cost_max: Optional[float] = None
    deposit_pct_min: Optional[float] = None
    deposit_pct_max: Optional[float] = None
    sublease_allowed: Optional[bool] = None
    assignment_allowed: Optional[bool] = None


class AlertCreateRequest(BaseModel):
    name: str
    filters: AlertFilters
    channel: AlertChannel = AlertChannel.EMAIL


class AlertResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    channel: str
    filters: dict
    last_triggered_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[AlertResponse])
async def list_alerts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.user_id == user.id))
    alerts = result.scalars().all()
    return [
        AlertResponse(
            id=a.id,
            name=a.name,
            is_active=a.is_active,
            channel=a.channel.value,
            filters=a.filters,
            last_triggered_at=a.last_triggered_at.isoformat() if a.last_triggered_at else None,
            created_at=a.created_at.isoformat(),
        )
        for a in alerts
    ]


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(
    data: AlertCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Проверяем лимит по тарифу
    result = await db.execute(select(Alert).where(Alert.user_id == user.id))
    existing_count = len(result.scalars().all())

    if existing_count >= user.saved_filters_limit:
        raise HTTPException(
            status_code=403,
            detail=f"Достигнут лимит фильтров для вашего тарифа ({user.saved_filters_limit}). Обновите подписку."
        )

    alert = Alert(
        user_id=user.id,
        name=data.name,
        filters=data.filters.model_dump(exclude_none=True),
        channel=data.channel,
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        is_active=alert.is_active,
        channel=alert.channel.value,
        filters=alert.filters,
        last_triggered_at=None,
        created_at=alert.created_at.isoformat(),
    )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    data: AlertCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Фильтр не найден")

    alert.name = data.name
    alert.filters = data.filters.model_dump(exclude_none=True)
    alert.channel = data.channel
    await db.commit()
    await db.refresh(alert)

    return AlertResponse(
        id=alert.id,
        name=alert.name,
        is_active=alert.is_active,
        channel=alert.channel.value,
        filters=alert.filters,
        last_triggered_at=alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        created_at=alert.created_at.isoformat(),
    )


@router.patch("/{alert_id}/toggle")
async def toggle_alert(alert_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Фильтр не найден")
    alert.is_active = not alert.is_active
    await db.commit()
    return {"id": alert.id, "is_active": alert.is_active}


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Фильтр не найден")
    await db.delete(alert)
    await db.commit()


@router.post("/{alert_id}/test")
async def send_test_notification(alert_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Отправляет одноразовое тестовое уведомление — не списывает алерт, не трогает last_triggered_at.

    Берёт 3 самых свежих лота под фильтр (или просто 3 свежих active лота, если ничего не нашлось),
    и шлёт по каналу, выбранному в фильтре (email/telegram/both).
    Возвращает {sent_email, sent_telegram, lots_count}.
    """
    from models.lot import Lot, LotStatus
    from services.notifications import send_email_alert, send_telegram_alert
    from sqlalchemy import desc

    result = await db.execute(select(Alert).where(Alert.id == alert_id, Alert.user_id == user.id))
    alert = result.scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="Фильтр не найден")

    # Берём свежие active лоты под фильтр (мягко — без узких условий, чтобы что-то нашлось).
    # Цель — не точно совпасть с алертом, а проверить, что письмо/TG доходит.
    region_codes = (alert.filters or {}).get("region_codes")
    q = select(Lot).where(Lot.status == LotStatus.ACTIVE)
    if region_codes:
        q = q.where(Lot.region_code.in_(region_codes))
    q = q.order_by(desc(Lot.published_at)).limit(3)
    lots = (await db.execute(q)).scalars().all()

    if not lots:
        # Без региона — просто 3 свежих
        q2 = select(Lot).where(Lot.status == LotStatus.ACTIVE).order_by(desc(Lot.published_at)).limit(3)
        lots = (await db.execute(q2)).scalars().all()

    sent_email = False
    sent_telegram = False
    errors: list[str] = []

    try:
        if alert.channel.value in ("email", "both") and user.email:
            await send_email_alert(user, alert, list(lots))
            sent_email = True
    except Exception as e:
        errors.append(f"email: {type(e).__name__}: {e}")

    try:
        if alert.channel.value in ("telegram", "both") and user.telegram_id:
            await send_telegram_alert(user, alert, list(lots))
            sent_telegram = True
    except Exception as e:
        errors.append(f"telegram: {type(e).__name__}: {e}")

    if not sent_email and not sent_telegram:
        detail = "Не удалось отправить: "
        if alert.channel.value in ("email", "both") and not user.email:
            detail += "email не указан в профиле. "
        if alert.channel.value in ("telegram", "both") and not user.telegram_id:
            detail += "Telegram не привязан. "
        if errors:
            detail += "Ошибки: " + "; ".join(errors)
        raise HTTPException(status_code=400, detail=detail.strip())

    return {
        "sent_email": sent_email,
        "sent_telegram": sent_telegram,
        "lots_count": len(lots),
        "errors": errors,
    }
