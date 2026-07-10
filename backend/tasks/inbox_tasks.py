"""Celery-задача AI-первой линии: разбор новых сообщений единого инбокса."""
import asyncio

from worker import celery_app


def _run(coro):
    """Новый луп + dispose глобального engine в том же лупе (паттерн alert_tasks)."""
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
def process_inbox(limit: int = 20):
    """Классификация, автоответы и эскалация новых входящих из соцсетей."""
    from services.sales_agent import process_new_messages
    n = _run(process_new_messages(limit))
    if n:
        print(f"[inbox-task] processed {n} message(s)")
    return n
