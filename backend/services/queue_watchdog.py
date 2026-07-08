"""Сторож очереди Celery — алерт в Telegram при накоплении бэклога.

Найдено 08.07.2026: enrich_with_rosreestr шёл ~100 мин вместо расчётных ~12
(замедлился Rosreestr/PKK), beat триггерил её каждый час — копии стакались
и забили все 4 worker-слота (concurrency=4), очередь выросла до 296 задач,
scrape_torgi_gov несколько часов не мог получить слот. Суточный отчёт
(morning_check) это бы заметил только на следующее утро — здесь проверка
каждые 30 минут с дебаунсом, чтобы не спамить одним и тем же алертом.
"""
from __future__ import annotations

import time

import httpx
import redis

from core.config import settings

QUEUE_THRESHOLD = 100      # выше — считаем бэклогом
REALERT_HOURS = 4          # не повторять алерт чаще, пока проблема не ушла
_STATE_KEY = "health:queue:state"
_LAST_ALERT_KEY = "health:queue:last_alert"


def _notify(text: str) -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": settings.ADMIN_TELEGRAM_CHAT_ID, "text": text,
                  "disable_web_page_preview": "true"},
            timeout=30,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[queue_watchdog] telegram send failed: {e}")


def check_queue_depth() -> int:
    """Проверяет глубину очереди celery, шлёт алерт при бэклоге и при
    восстановлении. Возвращает текущую глубину (для логов)."""
    r = redis.Redis.from_url(settings.REDIS_URL)
    depth = r.llen("celery")
    was_alerting = r.get(_STATE_KEY) == b"alert"

    if depth > QUEUE_THRESHOLD:
        now = time.time()
        last_alert = r.get(_LAST_ALERT_KEY)
        should_alert = not was_alerting or (
            last_alert and now - float(last_alert) > REALERT_HOURS * 3600
        )
        if should_alert:
            _notify(
                f"🔴 Очередь Celery переполнена: {depth} задач в ожидании "
                f"(порог {QUEUE_THRESHOLD}).\n"
                f"Обычно значит: periodic-задача зависла/замедлилась и копии "
                f"стакаются поверх друг друга, забивая worker-слоты — из-за "
                f"этого может тормозить весь ingest (torgi.gov и т.д.).\n"
                f"Проверить: docker compose exec celery_worker celery -A "
                f"worker.celery_app inspect active"
            )
            r.set(_LAST_ALERT_KEY, now)
        r.set(_STATE_KEY, "alert")
    else:
        if was_alerting:
            _notify(f"🟢 Очередь Celery разгружена ({depth} задач) — бэклог ушёл.")
        r.set(_STATE_KEY, "ok")

    return depth
