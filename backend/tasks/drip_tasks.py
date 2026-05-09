"""Ежедневная задача отправки drip-серии писем не-платящим юзерам."""
import asyncio
from datetime import datetime, timezone, timedelta

from worker import celery_app


DRIP_DAYS = (3, 7, 14)
MAX_PER_RUN = 200  # лимит писем за запуск, чтобы не упереться в SMTP-rate


@celery_app.task
def send_drips():
    asyncio.run(_run())


async def _run():
    from sqlalchemy import select, and_, or_, func, exists
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.user import User
    from models.alert import Subscription
    from services.drip_emails import send_drip_email

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    sent_total = 0
    async with SessionLocal() as db:
        for day in DRIP_DAYS:
            cutoff = now - timedelta(days=day)
            # Подзапрос: были ли успешные покупки
            paid_subq = (
                select(Subscription.id)
                .where(
                    Subscription.user_id == User.id,
                    Subscription.status == "succeeded",
                )
                .limit(1)
            )
            q = (
                select(User)
                .where(
                    and_(
                        User.is_active == True,  # noqa: E712
                        User.notification_email == True,  # noqa: E712
                        User.email.isnot(None),
                        User.created_at <= cutoff,
                        or_(User.last_drip_step.is_(None), User.last_drip_step < day),
                        ~exists(paid_subq),  # без успешных покупок
                    )
                )
                .limit(MAX_PER_RUN - sent_total)
            )
            users = (await db.execute(q)).scalars().all()
            if not users:
                continue

            for u in users:
                ok = await send_drip_email(u, day)
                if ok:
                    u.last_drip_step = day
                    u.last_drip_at = now
                    sent_total += 1
                if sent_total >= MAX_PER_RUN:
                    break
            await db.commit()
            if sent_total >= MAX_PER_RUN:
                break

    print(f"[drip] Отправлено: {sent_total}")
    await engine.dispose()
