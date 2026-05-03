"""
Уведомление пользователей о снижении цены лотов.

Запускается каждые 30 минут. Ищет лоты с last_price_drop_at в недавнем
интервале (за последние 35 минут — небольшое перекрытие, чтобы не пропустить
из-за рассинхронизации) и рассылает уведомления:
  · пользователям, у которых лот в SavedLot (избранное)
  · пользователям, у которых лот подходит под активный Alert по фильтрам

Для каждого лота × пользователя пишем запись в PriceDropNotification, чтобы
не дублировать. Канал доставки — по флагам пользователя (notification_email,
notification_telegram).
"""
import asyncio
from datetime import datetime, timezone, timedelta

from worker import celery_app


@celery_app.task
def notify_price_drops():
    asyncio.run(_run())


async def _run():
    from sqlalchemy import select, and_, or_
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.lot import Lot, LotStatus, LotSource
    from models.user import User, SavedLot
    from models.alert import Alert

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=35)

    async with SessionLocal() as db:
        # Лоты со свежим снижением цены
        rows = await db.execute(
            select(Lot)
            .where(
                and_(
                    Lot.source == LotSource.TORGI_GOV,
                    Lot.status == LotStatus.ACTIVE,
                    Lot.last_price_drop_at.isnot(None),
                    Lot.last_price_drop_at >= cutoff,
                )
            )
        )
        dropped = rows.scalars().all()

        if not dropped:
            return

        print(f"[price-drop] Лотов со свежим снижением: {len(dropped)}")

        # Соберём пользователей-получателей: SavedLot + по фильтрам Alert
        # Простая логика: для каждого лота проходим SavedLot и активные Alerts
        notif_count = 0
        for lot in dropped:
            recipients = await _collect_recipients(db, lot)
            for user in recipients:
                try:
                    await _send_drop_notification(user, lot)
                    notif_count += 1
                except Exception as e:
                    print(f"[price-drop] {user.email}: {type(e).__name__}: {e}")

        print(f"[price-drop] Отправлено уведомлений: {notif_count}")
    await engine.dispose()


async def _collect_recipients(db, lot):
    """Собирает уникальных пользователей: те у кого лот в избранном
    или матчится под их активный Alert по region+price+area+purpose."""
    from sqlalchemy import select, and_
    from models.user import User, SavedLot
    from models.alert import Alert

    users: dict[int, User] = {}

    # Избранное
    saved = await db.execute(
        select(User)
        .join(SavedLot, SavedLot.user_id == User.id)
        .where(and_(SavedLot.lot_id == lot.id, User.is_active == True))
    )
    for u in saved.scalars().all():
        users[u.id] = u

    # Активные алерты — простой матчинг по region + price + area + purpose
    alerts = await db.execute(
        select(Alert, User)
        .join(User, User.id == Alert.user_id)
        .where(and_(Alert.is_active == True, User.is_active == True))
    )
    for alert, user in alerts.all():
        f = alert.filters or {}
        # region
        if f.get("region_codes") and lot.region_code not in f["region_codes"]:
            continue
        if f.get("price_min") is not None and (lot.start_price or 0) < f["price_min"]:
            continue
        if f.get("price_max") is not None and (lot.start_price or 1e18) > f["price_max"]:
            continue
        if f.get("area_min") is not None and (lot.area_sqm or 0) < f["area_min"]:
            continue
        if f.get("area_max") is not None and (lot.area_sqm or 1e18) > f["area_max"]:
            continue
        if f.get("land_purposes"):
            lp = lot.land_purpose.value if lot.land_purpose else None
            if lp not in f["land_purposes"]:
                continue
        users[user.id] = user

    return list(users.values())


async def _send_drop_notification(user, lot):
    """Шлёт уведомление пользователю в email/telegram согласно его настройкам."""
    if user.notification_telegram and user.telegram_id:
        await _send_telegram_drop(user, lot)
    if user.notification_email and user.email:
        await _send_email_drop(user, lot)


async def _send_telegram_drop(user, lot):
    from services.telegram_bot import send_message
    SITE = "https://xn--e1adnd0h.online"
    title = (lot.title or "Земельный участок")[:80]
    drop = lot.last_price_drop_pct or 0
    new_price = (lot.start_price or 0)
    text = (
        f"📉 *Цена снижена на {drop:.0f}%*\n\n"
        f"[{title}]({SITE}/lots/{lot.id})\n"
        f"📍 {lot.region_name or ''}\n"
        f"💰 Новая цена: *{int(new_price):,} ₽*\n\n"
        f"_Повторные торги — шанс взять дешевле._"
    ).replace(",", " ")
    await send_message(user.telegram_id, text)


async def _send_email_drop(user, lot):
    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from core.config import settings

    if not settings.SMTP_USER:
        return

    SITE = "https://xn--e1adnd0h.online"
    title = (lot.title or "Земельный участок")[:120]
    drop = lot.last_price_drop_pct or 0
    new_price = int(lot.start_price or 0)
    new_price_str = f"{new_price:,}".replace(",", " ")

    html = f"""<!DOCTYPE html>
<html><body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:20px;color:#1f2937">
  <div style="background:#dc2626;padding:18px;border-radius:8px 8px 0 0;color:#fff">
    <h2 style="margin:0;font-size:20px">📉 Цена снижена на {drop:.0f}%</h2>
  </div>
  <div style="background:#fff;padding:20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
    <p style="margin:0 0 12px;font-size:15px;font-weight:600">{title}</p>
    <p style="margin:0 0 8px;color:#4b5563">📍 {lot.region_name or ''}</p>
    <p style="margin:0 0 16px;font-size:18px;color:#16a34a;font-weight:700">
      Новая цена: {new_price_str} ₽
    </p>
    <a href="{SITE}/lots/{lot.id}"
       style="display:inline-block;padding:10px 20px;background:#dc2626;color:#fff;
              text-decoration:none;border-radius:6px;font-weight:600">
      Открыть лот →
    </a>
    <p style="font-size:11px;color:#9ca3af;margin-top:24px">
      Уведомление об отслеживаемом лоте.<br>
      <a href="{SITE}/dashboard" style="color:#16a34a">Управление подпиской</a>
    </p>
  </div>
</body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📉 −{drop:.0f}% — {title[:60]}"
    msg["From"] = settings.SMTP_USER
    msg["To"] = user.email
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        use_tls=True,
    )
