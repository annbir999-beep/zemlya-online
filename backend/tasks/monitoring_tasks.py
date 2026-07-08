"""Служебный мониторинг платформы — фоновые проверки состояния (не бизнес-данных)."""
from worker import celery_app


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def check_queue_health(self):
    """Сторож очереди Celery — см. services/queue_watchdog.py."""
    from services.queue_watchdog import check_queue_depth
    try:
        depth = check_queue_depth()
        print(f"[queue_watchdog] depth={depth}")
    except Exception as exc:
        raise self.retry(exc=exc)
