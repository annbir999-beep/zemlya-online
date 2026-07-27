"""Сторож очереди Celery — алерт в Telegram при накоплении бэклога, и
активная зачистка зависших «быстрых» задач.

Найдено 08.07.2026: enrich_with_rosreestr шёл ~100 мин вместо расчётных ~12
(замедлился Rosreestr/PKK), beat триггерил её каждый час — копии стакались
и забили все 4 worker-слота (concurrency=4), очередь выросла до 296 задач,
scrape_torgi_gov несколько часов не мог получить слот. Суточный отчёт
(morning_check) это бы заметил только на следующее утро — здесь проверка
каждые 5 минут с дебаунсом на алерт, чтобы не спамить одним и тем же.

Найдено 25.07.2026: poll_youtube_comments/poll_ok_updates зависли на
56ч/18ч (ожидание соединения из пула БД) — заняли 3 из 4 слотов, очередь
выросла до 485 незаметно (алерт раз в 30 мин не успевал среагировать
быстро, а глобального лимита времени на задачу не было вообще). Фикс:
task_soft_time_limit/task_time_limit в worker.py — страховка для ЛЮБОЙ
задачи; плюс FAST_TASKS ниже — для заведомо быстрых задач детектим и
снимаем зависшую копию немедленно, не дожидаясь celery time_limit (у него
запас 20-25 мин под честно долгие батчи).
"""
from __future__ import annotations

import time

import httpx
import redis

from core.config import settings
from worker import celery_app

QUEUE_THRESHOLD = 100      # выше — считаем бэклогом
REALERT_HOURS = 4          # не повторять алерт чаще, пока проблема не ушла
_STATE_KEY = "health:queue:state"
_LAST_ALERT_KEY = "health:queue:last_alert"

# Задачи, которые в норме отрабатывают за секунды (HTTP-опрос + пара
# запросов в БД). Если активны дольше лимита — считаем зависшими и снимаем
# сразу, не дожидаясь глобального task_time_limit (20-25 мин).
FAST_TASKS = {
    "tasks.inbox_tasks.poll_youtube_comments": 300,
    "tasks.inbox_tasks.poll_max_updates": 300,
    "tasks.inbox_tasks.poll_ok_updates": 300,
    "tasks.inbox_tasks.process_inbox": 420,
}


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


def _revoke_stuck_fast_tasks() -> list[str]:
    """Снимает активные задачи из FAST_TASKS, если они идут дольше своего
    лимита. Возвращает список человекочитаемых описаний снятых задач."""
    revoked: list[str] = []
    try:
        active = celery_app.control.inspect(timeout=5).active() or {}
    except Exception as e:  # noqa: BLE001
        print(f"[queue_watchdog] inspect active failed: {e}")
        return revoked

    now = time.time()
    for worker_name, tasks in active.items():
        for t in tasks:
            name = t.get("name")
            limit = FAST_TASKS.get(name)
            if not limit:
                continue
            started = t.get("time_start")
            if not started:
                continue
            age = now - started
            if age <= limit:
                continue
            task_id = t.get("id")
            try:
                celery_app.control.revoke(task_id, terminate=True, signal="SIGKILL")
                revoked.append(f"{name} (шла {age/60:.0f} мин, id {task_id[:8]}, {worker_name})")
            except Exception as e:  # noqa: BLE001
                print(f"[queue_watchdog] revoke {task_id} failed: {e}")
    return revoked


def check_queue_depth() -> int:
    """Снимает зависшие быстрые задачи, проверяет глубину очереди, шлёт
    алерт при бэклоге и при восстановлении. Возвращает текущую глубину."""
    revoked = _revoke_stuck_fast_tasks()
    if revoked:
        _notify(
            "🛠 Автосторож снял зависшие задачи (держали worker-слот дольше нормы):\n"
            + "\n".join(f"• {r}" for r in revoked)
        )

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
