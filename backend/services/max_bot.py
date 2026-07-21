"""Бот мессенджера Max — этап 3 единого инбокса.

Max Bot API (platform-api.max.ru): long-poll GET /updates с marker,
токен в заголовке Authorization. Входящие сообщения → инбокс;
sales_agent отвечает через send_message().
Marker хранится в Redis, чтобы не перечитывать старые события.
"""
import httpx
import redis.asyncio as redis_async

from core.config import settings

BASE_URL = "https://platform-api.max.ru"
MARKER_KEY = "max_bot:marker"


def _headers() -> dict:
    return {"Authorization": settings.MAX_BOT_TOKEN}


async def send_message(chat_id, text: str) -> bool:
    """Отправляет сообщение в чат Max от имени бота."""
    if not settings.MAX_BOT_TOKEN or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{BASE_URL}/messages",
                params={"chat_id": chat_id},
                headers=_headers(),
                json={"text": text[:3900]},
            )
            if r.status_code != 200:
                print(f"[max-bot] send HTTP {r.status_code}: {r.text[:200]}")
            return r.status_code == 200
    except Exception as e:
        print(f"[max-bot] send error: {type(e).__name__}: {e}")
        return False


async def poll_updates() -> int:
    """Забирает свежие апдейты и складывает сообщения в инбокс."""
    if not settings.MAX_BOT_TOKEN:
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
        params = {"timeout": 5, "limit": 50}
        if marker:
            params["marker"] = marker

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r = await client.get(f"{BASE_URL}/updates", params=params, headers=_headers())
                if r.status_code != 200:
                    print(f"[max-bot] updates HTTP {r.status_code}: {r.text[:200]}")
                    return 0
                data = r.json()
        except Exception as e:
            print(f"[max-bot] poll error: {type(e).__name__}: {e}")
            return 0

        updates = data.get("updates") or []
        new_marker = data.get("marker")
        new_count = 0

        async with AsyncSessionLocal() as db:
            for upd in updates:
                if upd.get("update_type") != "message_created":
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
                    source="max",
                    event_type="dm",
                    external_id=str(body.get("mid") or f"{chat_id}_{m.get('timestamp')}"),
                    author_id=str(sender.get("user_id") or ""),
                    author_name=sender.get("name") or sender.get("username"),
                    text=text,
                    raw={"chat_id": chat_id, "mid": body.get("mid")},
                )
                if msg:
                    new_count += 1

        if new_marker is not None:
            await rc.set(MARKER_KEY, str(new_marker))
        return new_count
    finally:
        await rc.aclose()
