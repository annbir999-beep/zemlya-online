import asyncio
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from core.config import settings


@worker_process_init.connect
def init_worker_event_loop(**kwargs):
    """Каждый воркер-процесс получает чистый event loop — избегаем 'attached to a different loop'."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

celery_app = Celery(
    "sotka",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.scrape_tasks", "tasks.alert_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    # Расписание периодических задач
    beat_schedule={
        # Парсинг torgi.gov — каждые 2 часа
        "scrape-torgi-gov": {
            "task": "tasks.scrape_tasks.scrape_torgi_gov",
            "schedule": crontab(minute=0, hour="*/2"),
        },
        # Обогащение данными Росреестра — каждые 6 часов
        "enrich-rosreestr": {
            "task": "tasks.scrape_tasks.enrich_with_rosreestr",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        # Проверка алертов и отправка уведомлений — каждые 30 минут
        "check-alerts": {
            "task": "tasks.alert_tasks.check_and_notify",
            "schedule": crontab(minute="*/30"),
        },
        # Обновление статусов лотов (завершённые торги) — раз в час
        "update-lot-statuses": {
            "task": "tasks.scrape_tasks.update_lot_statuses",
            "schedule": crontab(minute=15, hour="*"),
        },
        # Парсинг Авито — раз в сутки в 3:00 (топ-10 регионов, 3 страницы каждый)
        "scrape-avito": {
            "task": "tasks.scrape_tasks.scrape_avito",
            "schedule": crontab(minute=0, hour=3),
        },
    },
)
