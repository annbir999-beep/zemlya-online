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
    include=["tasks.scrape_tasks", "tasks.alert_tasks", "tasks.ai_batch_tasks", "tasks.digest_tasks", "tasks.price_drop_tasks", "tasks.drip_tasks", "tasks.agent_tasks"],
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
        # Парсинг bankrot.fedresurs.ru — каждые 6 часов со сдвигом :40
        # (чтобы не пересекаться с torgi.gov на чётных часах).
        # Берёт активные банкротные торги по земельным участкам.
        "scrape-bankrot": {
            "task": "tasks.scrape_tasks.scrape_bankrot_fedresurs",
            "schedule": crontab(minute=40, hour="*/6"),
        },
        # Ежедневный re-parse PDF договоров обновлёнными regex'ами contract_parser.
        # Берёт лоты, у которых contract_terms ещё пуст / неполный — повторно скачивает
        # contract.pdf и применяет новые патерны. ~500 лотов за прогон = ~10 минут.
        "reparse-contract-terms": {
            "task": "tasks.scrape_tasks.reparse_contract_terms",
            "schedule": crontab(minute=45, hour=4),
            "args": (500,),
        },
        # Ежедневный пересчёт флагов переуступки и субаренды по тексту лота
        # (поля, установленные из PDF договора в enrich_torgi_details, не трогаются).
        # 03:30 МСК — до утренних beat-задач, после ночного scrape_avito.
        "enrich-sublease-flags": {
            "task": "tasks.scrape_tasks.enrich_sublease_flags",
            "schedule": crontab(minute=30, hour=3),
            "args": (2000,),
        },
        # Обогащение данными Росреестра — каждый час по 1000 лотов
        # batch=2000 заваливал очередь (3.6ч на прогон при hourly beat → накапливалось).
        # 1000 × 0.35с = ~6 минут на прогон — влезает в час с запасом.
        "enrich-rosreestr": {
            "task": "tasks.scrape_tasks.enrich_with_rosreestr",
            "schedule": crontab(minute=30, hour="*"),
            "args": (1000,),
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
        # Контакты организатора из подписанного JSON-извещения (раз в час по 200 лотов)
        "enrich-organizer-from-notice": {
            "task": "tasks.scrape_tasks.enrich_organizer_from_notice",
            "schedule": crontab(minute=25, hour="*"),
            "args": (200,),
        },
        # Ночной батч-анализ ОТКЛЮЧЁН 2026-05-22 — экономия Anthropic-бюджета
        # (~500 ₽/сутки). AI-анализ работает только по требованию: когда
        # пользователь открывает лот и запрашивает AI-аудит. Включить обратно —
        # раскомментировать блок ниже (и при желании поднять AI_BATCH_LIMIT).
        # "ai-batch-analyze": {
        #     "task": "tasks.ai_batch_tasks.ai_batch_analyze",
        #     "schedule": crontab(minute=30, hour=6),
        # },
        # Еженедельный email-дайджест: воскресенье 10:00 МСК — топ-10 лотов недели
        "weekly-digest": {
            "task": "tasks.digest_tasks.send_weekly_digest",
            "schedule": crontab(minute=0, hour=10, day_of_week=0),
        },
        # Drip-серия для не-платящих: каждый день в 11:00 МСК шлёт day-3/7/14 письма
        "drip-emails": {
            "task": "tasks.drip_tasks.send_drips",
            "schedule": crontab(minute=0, hour=11),
        },
        # Уведомление о снижении цены — каждые 30 мин (со сдвигом от check_alerts)
        "notify-price-drops": {
            "task": "tasks.price_drop_tasks.notify_price_drops",
            "schedule": crontab(minute="5,35"),
        },
        # Продукт-агент «Лот дня» — ежедневно 10:00 МСК готовит черновик
        # поста для @torgi_zemli (публикация — вручную из /admin → Агенты).
        "agent-tg-lot-of-the-day": {
            "task": "tasks.agent_tasks.agent_tg_lot_of_the_day",
            "schedule": crontab(minute=0, hour=10),
        },
    },
)
