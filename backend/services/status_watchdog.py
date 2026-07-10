"""Сторож статусной гигиены лотов — алерт в Telegram, если после подметания
_update_statuses остаётся много ACTIVE с уже закрытым окном подачи.

Мотив (10.07.2026): протухшие ACTIVE в норме ~0 — их закрывает _update_statuses
каждые 30 мин. Но если задача статусов перестаёт отрабатывать (Celery-луп,
engine dispose, зависший worker), лоты с закрытым окном висят как живые везде:
на карте, в списке, в heatmap, в alerts, в TG-дайджесте. Суточный morning_check
это заметит только утром — здесь проверка при каждом прогоне статусов, с
дебаунсом, чтобы не спамить одним и тем же алертом. Зеркалит queue_watchdog.
"""
from __future__ import annotations

import time

import httpx
import redis

from core.config import settings

STALE_THRESHOLD = 500      # выше — считаем, что закрытие структурно не работает
REALERT_HOURS = 4          # не повторять алерт чаще, пока проблема не ушла
_STATE_KEY = "health:status:state"
_LAST_ALERT_KEY = "health:status:last_alert"


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
        print(f"[status_watchdog] telegram send failed: {e}")


def check_stale_active(remaining: int) -> None:
    """remaining — число ACTIVE с истёкшим окном ПОСЛЕ прогона _update_statuses.
    В норме ~0. Стабильно высокое значение = закрытие не срабатывает."""
    try:
        r = redis.Redis.from_url(settings.REDIS_URL)
    except Exception as e:  # noqa: BLE001
        print(f"[status_watchdog] redis unavailable: {e}")
        return
    was_alerting = r.get(_STATE_KEY) == b"alert"

    if remaining > STALE_THRESHOLD:
        now = time.time()
        last_alert = r.get(_LAST_ALERT_KEY)
        should_alert = not was_alerting or (
            last_alert and now - float(last_alert) > REALERT_HOURS * 3600
        )
        if should_alert:
            _notify(
                f"🔴 Сторож статусов: {remaining} ACTIVE с закрытым окном подачи "
                f"остались НЕ закрыты после прогона _update_statuses.\n"
                f"Обычно значит: задача статусов не отрабатывает (Celery/event-loop) "
                f"— протухшие лоты висят как живые на карте, в списке, в алертах.\n"
                f"Проверить: docker compose logs celery_worker | grep statuses"
            )
            r.set(_LAST_ALERT_KEY, now)
        r.set(_STATE_KEY, "alert")
    else:
        if was_alerting:
            _notify(f"🟢 Сторож статусов: протухших ACTIVE снова в норме ({remaining}).")
        r.set(_STATE_KEY, "ok")
