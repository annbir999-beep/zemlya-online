"""Celery-задача: уведомления о новых письмах на info@torgi-zemli.ru в Telegram."""
from worker import celery_app


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def check_mail_notify(self):
    """Проверяет почту по IMAP и шлёт владельцу уведомления о новых письмах."""
    try:
        from services.mail_notify import check_new_mail
        n = check_new_mail()
        if n:
            print(f"[mail_notify] новых писем: {n}")
    except Exception as exc:  # noqa: BLE001
        print(f"[mail_notify] ошибка: {exc}")
        raise self.retry(exc=exc)
