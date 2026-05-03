"""
Еженедельный email-дайджест: топ-10 лотов недели всем пользователям с
notification_email=True (в воскресенье 10:00 МСК).

Отбор: ACTIVE, с computed score >= 70, появились за последние 7 дней
(coalesce published_at, created_at). Сортировка по score desc.
"""
import asyncio
from datetime import datetime, timezone, timedelta

from worker import celery_app


DIGEST_MIN_SCORE = 70
DIGEST_TOP_N = 10


@celery_app.task
def send_weekly_digest():
    asyncio.run(_send_weekly_digest())


async def _send_weekly_digest():
    from sqlalchemy import select, and_, func, or_
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.lot import Lot, LotStatus, LotSource
    from models.user import User
    from services.notifications import _format_price, _format_area  # переиспользуем

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    async with SessionLocal() as db:
        # Топ-10 лотов недели
        discovered_at = func.coalesce(Lot.published_at, Lot.created_at)
        result = await db.execute(
            select(Lot)
            .where(
                and_(
                    Lot.source == LotSource.TORGI_GOV,
                    Lot.status == LotStatus.ACTIVE,
                    Lot.score >= DIGEST_MIN_SCORE,
                    discovered_at >= week_ago,
                )
            )
            .order_by(Lot.score.desc().nulls_last())
            .limit(DIGEST_TOP_N)
        )
        top_lots = result.scalars().all()

        if not top_lots:
            print("[digest] Нет лотов для дайджеста — пропускаем рассылку")
            return

        # Получатели
        users_q = await db.execute(
            select(User).where(
                and_(User.is_active == True, User.notification_email == True, User.email.isnot(None))
            )
        )
        users = users_q.scalars().all()
        print(f"[digest] Найдено лотов: {len(top_lots)}, получателей: {len(users)}")

    await engine.dispose()

    if not users:
        return

    sent = 0
    for u in users:
        try:
            await _send_one_digest(u, top_lots)
            sent += 1
        except Exception as e:
            print(f"[digest] Ошибка для {u.email}: {type(e).__name__}: {e}")

    print(f"[digest] Отправлено: {sent}/{len(users)}")


async def _send_one_digest(user, lots):
    """Отправляет одно письмо с топ-N лотами."""
    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from core.config import settings
    from services.notifications import _format_price, _format_area

    if not settings.SMTP_USER:
        return

    SITE = "https://xn--e1adnd0h.online"
    rows_html = ""
    for i, lot in enumerate(lots, 1):
        title = (lot.title or "Земельный участок")[:80]
        price = _format_price(lot.start_price)
        area = _format_area(lot.area_sqm)
        region = lot.region_name or ""
        score = lot.score or 0
        discount = lot.discount_to_market_pct
        discount_html = (
            f'<span style="background:#dcfce7;color:#16a34a;padding:2px 6px;border-radius:4px;font-size:12px;font-weight:700">−{int(discount)}%</span>'
            if discount and discount >= 10 else ""
        )
        rows_html += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #e5e7eb">
            <div style="font-weight:700;color:#dc2626;font-size:18px;display:inline-block;width:42px">{score}</div>
            <a href="{SITE}/lots/{lot.id}" style="color:#1f2937;text-decoration:none;font-weight:500;font-size:14px">
              {title}
            </a>
            {discount_html}
            <div style="font-size:12px;color:#6b7280;margin-top:4px;margin-left:42px">
              📍 {region} &nbsp;·&nbsp; 📐 {area} &nbsp;·&nbsp; 💰 {price}
            </div>
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#1f2937">
  <div style="background:linear-gradient(135deg,#16a34a,#0d9488);padding:24px;border-radius:10px 10px 0 0;color:#fff">
    <h1 style="margin:0;font-size:22px">🔥 Топ участков недели</h1>
    <p style="margin:6px 0 0;opacity:.9;font-size:14px">Самые рентабельные лоты на земля.online</p>
  </div>
  <div style="background:#f9fafb;padding:20px;border-radius:0 0 10px 10px">
    <p style="margin:0 0 16px">Привет, <b>{user.name or user.email}</b>!</p>
    <p style="margin:0 0 16px;font-size:14px;color:#4b5563">
      За последние 7 дней появилось <b>{len(lots)}</b> лотов со score выше {DIGEST_MIN_SCORE}.
      Они вошли в подборку:
    </p>
    <table style="width:100%;border-collapse:collapse">{rows_html}</table>
    <div style="text-align:center;margin-top:24px">
      <a href="{SITE}/lots?score_min=70&sort_by=score&sort_order=desc"
         style="display:inline-block;padding:10px 24px;background:#16a34a;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">
        Открыть весь топ →
      </a>
    </div>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0">
    <p style="font-size:11px;color:#9ca3af;text-align:center;margin:0">
      Получаете это письмо потому, что у вас включены email-уведомления.<br>
      <a href="{SITE}/dashboard" style="color:#16a34a">Управление подпиской</a>
    </p>
  </div>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔥 Топ-{len(lots)} участков недели — земля.online"
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
