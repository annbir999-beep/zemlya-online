"""Напоминания об истечении подписки — за 7 дней и за 1 день.

Клиент заранее решает, продлевать текущий план или менять (покупка тарифа
ниже активного заблокирована до истечения — см. api/payments.py create_payment).
Задача идемпотентна на суточном запуске: окна дат не пересекаются, за каждый
порог юзер получает ровно одно письмо.
"""
import asyncio

from worker import celery_app


def _run(coro):
    """Новый луп + dispose engine в том же лупе (см. agent_tasks._run)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_with_engine_cleanup(coro))
    finally:
        loop.close()


async def _with_engine_cleanup(coro):
    from db.database import engine
    try:
        return await coro
    finally:
        try:
            await engine.dispose()
        except Exception:
            pass


@celery_app.task
def notify_expiring_subscriptions():
    _run(_notify_expiring())


PLAN_LABELS = {"personal": "Pro", "investor": "Инвестор", "expert": "Бюро", "landlord": "Бюро+", "enterprise": "Enterprise"}


async def _notify_expiring():
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, and_
    from db.database import AsyncSessionLocal
    from models.user import User, SubscriptionPlan

    now = datetime.now(timezone.utc)
    windows = [
        (now + timedelta(days=6), now + timedelta(days=7), 7),
        (now, now + timedelta(days=1), 1),
    ]

    async with AsyncSessionLocal() as db:
        for start, end, days in windows:
            result = await db.execute(
                select(User).where(
                    and_(
                        User.is_active == True,
                        User.subscription_plan != SubscriptionPlan.FREE,
                        User.subscription_expires_at >= start,
                        User.subscription_expires_at < end,
                    )
                )
            )
            users = result.scalars().all()
            for u in users:
                try:
                    await _send_expiry_notice(u, days)
                except Exception as e:
                    print(f"[sub-expiry] {u.email}: {type(e).__name__}: {e}")
            if users:
                print(f"[sub-expiry] окно {days}д: уведомлено {len(users)}")


async def _send_expiry_notice(user, days: int):
    from core.config import settings

    plan_label = PLAN_LABELS.get(
        user.subscription_plan.value if user.subscription_plan else "", "подписка")
    when = "завтра" if days == 1 else f"через {days} дней"
    date_str = user.subscription_expires_at.strftime("%d.%m.%Y")
    SITE = settings.SITE_URL

    # Telegram
    if settings.TELEGRAM_BOT_TOKEN and user.telegram_id:
        import httpx
        text = (
            f"⏳ Ваш тариф «{plan_label}» истекает {when} ({date_str}).\n\n"
            f"Продлите сейчас — сохраните алерты, скоринг и AI-аудиты без перерыва. "
            f"Если хотите сменить план на следующий период — самое время выбрать.\n\n"
            f"{SITE}/pricing"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": user.telegram_id, "text": text},
                )
        except Exception as e:
            print(f"[sub-expiry] tg fail {user.id}: {e}")

    # Email
    if settings.SMTP_USER and user.email and user.notification_email:
        import aiosmtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto;padding:20px;color:#1f2937">
  <h2 style="margin:0 0 12px">⏳ Тариф «{plan_label}» истекает {when}</h2>
  <p style="font-size:14px;color:#4b5563">
    Действует до <b>{date_str}</b>. После окончания аккаунт перейдёт на бесплатный план:
    отключатся умные фильтры-алерты, скоринг, дисконт к рынку и AI-аналитика.
  </p>
  <p style="font-size:14px;color:#4b5563">
    Продлите текущий план или выберите другой на следующий период — переход на другой
    тариф удобнее оформить до истечения.
  </p>
  <div style="margin:20px 0">
    <a href="{SITE}/pricing" style="display:inline-block;background:#16a34a;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600">
      Продлить / выбрать план →
    </a>
  </div>
  <p style="font-size:11px;color:#9ca3af">Торги Земли · torgi-zemli.ru</p>
</body></html>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⏳ Тариф «{plan_label}» истекает {when} — torgi-zemli.ru"
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
