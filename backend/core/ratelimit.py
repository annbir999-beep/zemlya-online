"""Rate limiting через slowapi (хранилище — Redis).

Лимитируются только явно декорированные эндпоинты (auth — вектор брутфорса).
Глобального лимита нет: SSR-запросы фронтенда идут с одного внутреннего IP,
общий лимит душил бы легитимный трафик. Широкая защита — на уровне Nginx
(limit_req), см. docs/platform-blueprint-2026.md разд. 7.
"""
from slowapi import Limiter

from core.config import settings


def client_ip(request) -> str:
    """IP клиента за Nginx.

    X-Real-IP Nginx перезаписывает на $remote_addr — подделать нельзя. В
    X-Forwarded-For он лишь дописывает адрес к присланному клиентом, поэтому
    первый элемент задаёт сам клиент (любой лимит обходился сменой заголовка);
    если X-Real-IP нет, берём последний элемент — его добавил наш прокси.
    """
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip, storage_uri=settings.REDIS_URL)
