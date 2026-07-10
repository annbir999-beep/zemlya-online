"""Хаб единого инбокса: нормализованный приём событий из всех соцсетей.

ingest() — единственная точка входа: сохраняет сообщение в inbox_messages
(с дедупликацией по source+external_id) и шлёт уведомление в Telegram-чат.
Вызывается из вебхуков (api/inbox.py) и телеграм-бота (services/telegram_bot.py).
"""
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.inbox import InboxMessage

SOURCE_LABELS = {
    "vk": "VK",
    "tg_comment": "Telegram · коммент",
    "tg_dm": "Telegram · личка",
    "site": "Сайт",
    "ok": "Одноклассники",
    "youtube": "YouTube",
    "instagram": "Instagram",
    "max": "Max",
    "mail": "Почта",
}

EVENT_LABELS = {
    "comment": "комментарий",
    "dm": "сообщение",
    "lead_form": "заявка",
}


def _inbox_chat_id() -> str:
    return settings.INBOX_TELEGRAM_CHAT_ID or settings.ADMIN_TELEGRAM_CHAT_ID


async def ingest(
    db: AsyncSession,
    *,
    source: str,
    event_type: str,
    text: str,
    external_id: Optional[str] = None,
    author_id: Optional[str] = None,
    author_name: Optional[str] = None,
    author_url: Optional[str] = None,
    post_ref: Optional[str] = None,
    raw: Optional[dict] = None,
) -> Optional[InboxMessage]:
    """Сохраняет входящее и уведомляет админа. None — если дубликат ретрая."""
    text = (text or "").strip()
    if not text and event_type != "lead_form":
        return None

    if external_id:
        existing = await db.execute(
            select(InboxMessage.id).where(
                InboxMessage.source == source,
                InboxMessage.external_id == external_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            return None

    msg = InboxMessage(
        source=source,
        event_type=event_type,
        external_id=external_id,
        author_id=(author_id or None),
        author_name=(author_name or None),
        author_url=(author_url or None),
        text=text[:8000],
        post_ref=(post_ref or None),
        raw=raw,
    )
    db.add(msg)
    await db.commit()

    await _notify_admin(msg)
    return msg


async def _notify_admin(msg: InboxMessage) -> None:
    """Уведомление в TG-чат инбокса. Ошибки не роняют приём вебхука."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return

    src = SOURCE_LABELS.get(msg.source, msg.source)
    kind = EVENT_LABELS.get(msg.event_type, msg.event_type)
    who = msg.author_name or msg.author_id or "аноним"

    lines = [f"📥 {src} — {kind} · #{msg.id}", f"От: {who}"]
    if msg.author_url:
        lines.append(msg.author_url)
    lines.append("")
    lines.append(msg.text[:1500] if msg.text else "(без текста)")
    if msg.post_ref:
        lines.append("")
        lines.append(f"Под постом: {msg.post_ref}")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": _inbox_chat_id(),
                    "text": "\n".join(lines),
                    "disable_web_page_preview": True,
                },
            )
    except Exception as e:
        print(f"[inbox-hub] notify error: {type(e).__name__}: {e}")
