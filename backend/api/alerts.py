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
    auction_types: Optional[List[str]] = None
    keywords: Optional[str] = None


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
