"""Инициализация Sentry — общая для FastAPI (main.py) и Celery (worker.py).

Без SENTRY_DSN в .env превращается в no-op, локальная разработка не шумит.
traces_sample_rate низкий: следим за ошибками, не за перфомансом — бережём
квоту бесплатного тарифа и RAM на VPS.
"""
from core.config import settings


def init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment="production",
        traces_sample_rate=0.05,
        send_default_pii=False,
    )
