"""Бот Одноклассников — единый инбокс (авто-отдел продаж).

OK Bot API (api.ok.ru, семейство TamTam, как и Max): long-poll
GET /graph/me/updates с marker; токен группы передаётся query-параметром
access_token. Метод updates работает только при активной long-polling
подписке — её оформляем POST /graph/me/subscribe (types=[MESSAGE_CREATED]).
Входящие сообщения группы → инбокс; sales_agent отвечает через send_message().
Marker и флаг подписки держим в Redis.
"""
from typing import Optional

import httpx
import redis.asyncio as redis_async

from core.config import settings

BASE_URL = "https://api.ok.ru"
MARKER_KEY = "ok_bot:marker"
SUBSCRIBED_KEY = "ok_bot:subscribed"  # флаг активной подписки, TTL 30 мин

def _normalize_chat_id(chat_id) -> Optional[str]:
    """OK ждёт chat_id в форме 'chat:XXXX' и в URL, и в теле recipient."""
    if chat_id is None or chat_id == "":
        return None
    s = str(chat_id)
    return s if s.startswith("chat:") else f"chat:{s}"


async def _ensure_subscription(client: httpx.AsyncClient, rc: redis_async.Redis) -> None:
    """Оформляет long-polling подписку на MESSAGE_CREATED (идемпотентно, раз в ~30 мин)."""
    if await rc.get(SUBSCRIBED_KEY):
        return
    try:
        r = await client.post(
            f"{BASE_URL}/graph/me/subscribe",
            params={"access_token": settings.OK_GROUP_TOKEN},
            json={"longPolling": True, "types": ["MESSAGE_CREATED"]},
        )
        if r.status_code == 200:
            await rc.set(SUBSCRIBED_KEY, "1", ex=1800)
        else:
            print(f"[ok-bot] subscribe HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[ok-bot] subscribe error: {type(e).__name__}: {e}")


async def send_message(chat_id, text: str) -> bool:
    """Отправляет сообщение в чат ОК от имени группы."""
    if not settings.OK_GROUP_TOKEN or not chat_id:
        return False
    cid = _normalize_chat_id(chat_id)
    if not cid:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BASE_URL}/graph/{cid}/messages",
                params={"access_token": settings.OK_GROUP_TOKEN},
                headers={"Content-Type": "application/json;charset=utf-8"},
                json={"recipient": {"chat_id": cid}, "message": {"text": text[:3900]}},
            )
            if r.status_code != 200:
                print(f"[ok-bot] send HTTP {r.status_code}: {r.text[:200]}")
            return r.status_code == 200
    except Exception as e:
        print(f"[ok-bot] send error: {type(e).__name__}: {e}")
        return False


async def poll_updates() -> int:
    """Забирает свежие апдейты ОК и складывает сообщения в инбокс."""
    if not settings.OK_GROUP_TOKEN:
        return 0

    from db.database import AsyncSessionLocal
    from services.inbox_hub import ingest

    # Redis-клиент создаём локально на вызов, не кэшируем на модуле: _run()
    # в inbox_tasks крутит каждую задачу в новом event loop и закрывает его
    # по завершении, а закэшированный клиент остаётся привязан к закрытому
    # лупу и на следующем вызове роняет задачу RuntimeError("different loop").
    rc = redis_async.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        marker = await rc.get(MARKER_KEY)
        params = {"access_token": settings.OK_GROUP_TOKEN, "timeout": 5, "count": 50}
        if marker:
            params["marker"] = marker

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                await _ensure_subscription(client, rc)
                r = await client.get(f"{BASE_URL}/graph/me/updates", params=params)
                if r.status_code != 200:
                    print(f"[ok-bot] updates HTTP {r.status_code}: {r.text[:200]}")
                    return 0
                data = r.json()
        except Exception as e:
            print(f"[ok-bot] poll error: {type(e).__name__}: {e}")
            return 0

        updates = data.get("updates") or []
        new_marker = data.get("marker")
        new_count = 0

        async with AsyncSessionLocal() as db:
            for upd in updates:
                if str(upd.get("update_type") or "").lower() != "message_created":
                    continue
                m = upd.get("message") or {}
                body = m.get("body") or {}
                sender = m.get("sender") or {}
                recipient = m.get("recipient") or {}
                text = body.get("text") or ""
                if not text or sender.get("is_bot"):
                    continue
                chat_id = recipient.get("chat_id")
                msg = await ingest(
                    db,
                    source="ok",
                    event_type="dm",
                    external_id=str(body.get("mid") or f"{chat_id}_{upd.get('timestamp')}"),
                    author_id=str(sender.get("user_id") or ""),
                    author_name=sender.get("name"),
                    text=text,
                    raw={"chat_id": chat_id, "mid": body.get("mid")},
                )
                if msg:
                    new_count += 1

        # Диагностика: пришли апдейты, но ни одного message_created не распознали —
        # печатаем структуру первого, чтобы поправить парсинг по реальному формату ОК.
        if updates and new_count == 0:
            print(f"[ok-bot] unparsed updates sample: {str(updates[0])[:400]}")

        if new_marker is not None:
            await rc.set(MARKER_KEY, str(new_marker))
        return new_count
    finally:
        await rc.aclose()
