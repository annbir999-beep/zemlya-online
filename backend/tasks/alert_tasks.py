import asyncio
from worker import celery_app


@celery_app.task
def check_and_notify():
    """Проверяем все активные алерты и шлём уведомления о новых лотах"""
    asyncio.run(_check_alerts())


async def _check_alerts():
    from db.database import AsyncSessionLocal
    from sqlalchemy import select, and_
    from models.alert import Alert, AlertChannel, AlertNotification
    from models.lot import Lot, LotStatus
    from models.user import User
    from services.notifications import send_email_alert, send_telegram_alert
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        # Берём все активные алерты
        result = await db.execute(select(Alert).where(Alert.is_active == True))
        alerts = result.scalars().all()

        for alert in alerts:
            user_result = await db.execute(select(User).where(User.id == alert.user_id))
            user = user_result.scalar_one_or_none()
            if not user:
                continue

            # Строим запрос по фильтрам алерта
            conditions = [
                Lot.status == LotStatus.ACTIVE,
                # Только новые лоты (появившиеся с момента последнего срабатывания)
                Lot.published_at > (alert.last_triggered_at or alert.created_at),
            ]

            filters = alert.filters or {}
            if filters.get("region_codes"):
                conditions.append(Lot.region_code.in_(filters["region_codes"]))
            if filters.get("price_min") is not None:
                conditions.append(Lot.start_price >= filters["price_min"])
            if filters.get("price_max") is not None:
                conditions.append(Lot.start_price <= filters["price_max"])
            if filters.get("area_min") is not None:
                conditions.append(Lot.area_sqm >= filters["area_min"])
            if filters.get("area_max") is not None:
                conditions.append(Lot.area_sqm <= filters["area_max"])
            if filters.get("land_purposes"):
                conditions.append(Lot.land_purpose.in_(filters["land_purposes"]))
            if filters.get("auction_types"):
                conditions.append(Lot.auction_type.in_(filters["auction_types"]))

            lots_result = await db.execute(select(Lot).where(and_(*conditions)).limit(20))
            new_lots = lots_result.scalars().all()

            if not new_lots:
                continue

            lot_ids = [l.id for l in new_lots]
            success = True

            try:
                if alert.channel in (AlertChannel.EMAIL, AlertChannel.BOTH) and user.email:
                    await send_email_alert(user, alert, new_lots)
                if alert.channel in (AlertChannel.TELEGRAM, AlertChannel.BOTH) and user.telegram_id:
                    await send_telegram_alert(user, alert, new_lots)
            except Exception as e:
                print(f"[alerts] Ошибка уведомления alert_id={alert.id}: {e}")
                success = False

            # Записываем в историю
            notification = AlertNotification(
                alert_id=alert.id,
                lot_ids=lot_ids,
                channel=alert.channel,
                success=success,
            )
            db.add(notification)
            alert.last_triggered_at = now

        await db.commit()
        print(f"[alerts] Обработано алертов: {len(alerts)}")
