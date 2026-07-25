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


# Задачи ниже — быстрые опросы (HTTP + пара запросов в БД), в норме доли
# секунды/несколько секунд. Собственный soft/hard-лимит (в дополнение к
# глобальному в worker.py) даёт быстрый самостоятельный recovery, если
# задача всё же зависнет (25.07.2026: poll_youtube_comments/poll_ok_updates
# зависли на 56ч/18ч на ожидании соединения из пула БД).


@celery_app.task(soft_time_limit=180, time_limit=240)
def process_inbox(limit: int = 20):
    """Классификация, автоответы и эскалация новых входящих из соцсетей."""
    from services.sales_agent import process_new_messages
    n = _run(process_new_messages(limit))
    if n:
        print(f"[inbox-task] processed {n} message(s)")
    return n


@celery_app.task(soft_time_limit=60, time_limit=90)
def poll_youtube_comments():
    """Свежие комментарии YouTube-канала → инбокс (read-only, ключ YOUTUBE_API_KEY)."""
    from services.youtube_comments import poll_comments
    n = _run(poll_comments())
    if n:
        print(f"[inbox-task] youtube: {n} new comment(s)")
    return n


@celery_app.task(soft_time_limit=60, time_limit=90)
def poll_max_updates():
    """Сообщения бота Max → инбокс (long-poll с marker в Redis, токен MAX_BOT_TOKEN)."""
    from services.max_bot import poll_updates
    n = _run(poll_updates())
    if n:
        print(f"[inbox-task] max: {n} new message(s)")
    return n


@celery_app.task(soft_time_limit=60, time_limit=90)
def poll_ok_updates():
    """Сообщения группы ОК → инбокс (long-poll api.ok.ru, токен OK_GROUP_TOKEN)."""
    from services.ok_bot import poll_updates
    n = _run(poll_updates())
    if n:
        print(f"[inbox-task] ok: {n} new message(s)")
    return n
