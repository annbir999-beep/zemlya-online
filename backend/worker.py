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
    include=["tasks.scrape_tasks", "tasks.alert_tasks", "tasks.ai_batch_tasks"],
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
        # Подтягивание даты торгов из детального API torgi — каждые 3 часа
        "enrich-torgi-details": {
            "task": "tasks.scrape_tasks.enrich_torgi_details",
            "schedule": crontab(minute=45, hour="*/3"),
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
        # Пересчёт скора рентабельности — раз в час со сдвигом
        "update-lot-scores": {
            "task": "tasks.scrape_tasks.update_lot_scores",
            "schedule": crontab(minute=20, hour="*"),
        },
        # Расчёт ближайшего города и парсинг коммуникаций — раз в 6 часов
        "update-geo-comms": {
            "task": "tasks.scrape_tasks.update_lot_geo_and_comms",
            "schedule": crontab(minute=10, hour="*/6"),
        },
        # Парсинг PDF-документов лотов (раз в час, по 200 лотов)
        "enrich-pdfs": {
            "task": "tasks.scrape_tasks.enrich_lot_pdfs",
            "schedule": crontab(minute=35, hour="*"),
            "args": (200,),
        },
        # Парсинг Авито — раз в сутки в 3:00 (топ-10 регионов, 3 страницы каждый)
        "scrape-avito": {
            "task": "tasks.scrape_tasks.scrape_avito",
            "schedule": crontab(minute=0, hour=3),
        },
        # Парсинг ЦИАН — раз в сутки в 4:00 (15 регионов, 3 страницы каждый)
        "scrape-cian": {
            "task": "tasks.scrape_tasks.scrape_cian",
            "schedule": crontab(minute=0, hour=4),
        },
        # Парсинг Домклик — раз в сутки в 5:00 (20 регионов)
        "scrape-domclick": {
            "task": "tasks.scrape_tasks.scrape_domclick",
            "schedule": crontab(minute=0, hour=5),
        },
        # Обогащение лотов природными/инфраструктурными объектами из OSM
        # (по 100 лотов раз в час — Overpass лимит ~10k/день, успеваем все за пару дней)
        "enrich-nearby-features": {
            "task": "tasks.scrape_tasks.enrich_nearby_features",
            "schedule": crontab(minute=50, hour="*"),
            "args": (100,),
        },
        # Ночной батч-анализ топ-100 лотов через Claude (после всех скрапов и скоринга)
        "ai-batch-analyze": {
            "task": "tasks.ai_batch_tasks.ai_batch_analyze",
            "schedule": crontab(minute=30, hour=6),
        },
    },
)
