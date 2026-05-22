"""Celery-задачи продукт-агентов."""
import asyncio

from worker import celery_app


def _run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def agent_tg_lot_of_the_day(self):
    """Агент «Лот дня» — готовит черновик поста для @torgi_zemli.

    Запускается раз в день по beat schedule. Сам пост в канал не уходит —
    создаётся черновик со статусом waiting_approval, Анна одобряет в /admin.
    """
    try:
        _run(_run_lot_of_the_day())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_lot_of_the_day():
    from db.database import AsyncSessionLocal
    from services.agents.tg_lot_of_the_day import TgLotOfTheDayAgent

    async with AsyncSessionLocal() as db:
        agent = TgLotOfTheDayAgent()
        run = await agent.run(db)
        print(f"[agent:tg_lot_of_the_day] run #{run.id} → {run.status}")


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def agent_morning_check(self):
    """Агент «Утренний health-check» — собирает метрики прода и шлёт сводку в TG."""
    try:
        _run(_run_morning_check())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _run_morning_check():
    from db.database import AsyncSessionLocal
    from services.agents.morning_check import MorningCheckAgent

    async with AsyncSessionLocal() as db:
        agent = MorningCheckAgent()
        run = await agent.run(db)
        print(f"[agent:morning_check] run #{run.id} → {run.status}")
