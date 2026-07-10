"""Вебхуки единого инбокса — приём обратной связи из соцсетей.

  · POST /api/inbox/vk    — VK Callback API (confirmation, комменты, сообщения)
  · POST /api/inbox/site  — форма обратной связи с сайта

Все события нормализуются через services.inbox_hub.ingest().
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.ratelimit import limiter
from db.database import get_db
from services.inbox_hub import ingest

router = APIRouter()


# ── VK Callback API ──────────────────────────────────────────────────────────
# VK ждёт в ответ строку кода подтверждения (на type=confirmation) либо "ok".
# На невалидный secret тоже отвечаем "ok" — иначе VK будет ретраить чужой мусор.

@router.post("/vk")
async def vk_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        data = await request.json()
    except Exception:
        return PlainTextResponse("ok")

    event_type = data.get("type")

    if event_type == "confirmation":
        return PlainTextResponse(settings.VK_CONFIRMATION_CODE or "")

    if settings.VK_CALLBACK_SECRET and data.get("secret") != settings.VK_CALLBACK_SECRET:
        return PlainTextResponse("ok")

    obj = data.get("object") or {}

    try:
        if event_type == "message_new":
            m = obj.get("message") or obj
            from_id = m.get("from_id")
            await ingest(
                db,
                source="vk",
                event_type="dm",
                external_id=f"dm_{from_id}_{m.get('conversation_message_id') or m.get('id')}",
                author_id=str(from_id),
                author_name=f"vk.com/id{from_id}",
                author_url=f"https://vk.com/id{from_id}" if (from_id or 0) > 0 else None,
                text=m.get("text", ""),
                raw=m,
            )
        elif event_type in ("wall_reply_new", "wall_reply_edit"):
            from_id = obj.get("from_id")
            owner_id = obj.get("owner_id") or obj.get("post_owner_id")
            post_id = obj.get("post_id")
            await ingest(
                db,
                source="vk",
                event_type="comment",
                external_id=f"wall_{obj.get('id')}",
                author_id=str(from_id),
                author_name=f"vk.com/id{from_id}",
                author_url=f"https://vk.com/id{from_id}" if (from_id or 0) > 0 else None,
                text=obj.get("text", ""),
                post_ref=f"https://vk.com/wall{owner_id}_{post_id}" if owner_id and post_id else None,
                raw=obj,
            )
        elif event_type in ("video_comment_new", "photo_comment_new", "board_post_new"):
            from_id = obj.get("from_id")
            await ingest(
                db,
                source="vk",
                event_type="comment",
                external_id=f"{event_type}_{obj.get('id')}",
                author_id=str(from_id),
                author_name=f"vk.com/id{from_id}",
                author_url=f"https://vk.com/id{from_id}" if (from_id or 0) > 0 else None,
                text=obj.get("text", ""),
                raw=obj,
            )
    except Exception as e:
        # Приём вебхука не должен падать: VK при не-"ok" зашлёт ретраями
        print(f"[inbox-vk] error on {event_type}: {type(e).__name__}: {e}")

    return PlainTextResponse("ok")


# ── Форма обратной связи с сайта ─────────────────────────────────────────────

class SiteFeedback(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact: str = Field(min_length=3, max_length=255)  # телефон / email / @telegram
    message: str = Field(default="", max_length=4000)
    page: str | None = Field(default=None, max_length=300)


@router.post("/site")
@limiter.limit("5/minute;20/hour")
async def site_feedback(
    request: Request,
    data: SiteFeedback,
    db: AsyncSession = Depends(get_db),
):
    msg = await ingest(
        db,
        source="site",
        event_type="lead_form",
        author_name=data.name.strip(),
        author_id=data.contact.strip(),
        text=f"Контакт: {data.contact.strip()}\n{data.message.strip()}",
        post_ref=data.page,
        raw=data.model_dump(),
    )
    return {"ok": True, "id": msg.id if msg else None}
