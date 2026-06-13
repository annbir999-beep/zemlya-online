"""Ежедневная drip-серия для лидов воронки A (подписчики чеклиста).

Шаги по дням с момента захвата: 1, 3, 5, 8 (день 0 шлётся синхронно при захвате).
Останавливается, если лид отписался или зарегистрировался (converted_user_id).
"""
import asyncio
from datetime import datetime, timezone, timedelta

from worker import celery_app

LEAD_DRIP_DAYS = (1, 3, 5, 8)
MAX_PER_RUN = 200


@celery_app.task
def send_lead_drips():
    asyncio.run(_run())


async def _run():
    from sqlalchemy import select, and_, or_
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.lead import Lead
    from services.lead_emails import send_lead_email

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    sent_total = 0

    async with SessionLocal() as db:
        for day in LEAD_DRIP_DAYS:
            cutoff = now - timedelta(days=day)
            q = (
                select(Lead)
                .where(
                    and_(
                        Lead.unsubscribed == False,  # noqa: E712
                        Lead.converted_user_id.is_(None),
                        Lead.created_at <= cutoff,
                        or_(Lead.last_drip_step.is_(None), Lead.last_drip_step < day),
                    )
                )
                .limit(MAX_PER_RUN - sent_total)
            )
            leads = (await db.execute(q)).scalars().all()
            for lead in leads:
                ok = await send_lead_email(lead.email, lead.token, day)
                if ok:
                    lead.last_drip_step = day
                    lead.last_drip_at = now
                    sent_total += 1
                if sent_total >= MAX_PER_RUN:
                    break
            await db.commit()
            if sent_total >= MAX_PER_RUN:
                break

    print(f"[lead-drip] Отправлено: {sent_total}")
    await engine.dispose()
