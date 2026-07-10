"""AI-первая линия авто-отдела продаж — этап 2.

Разбирает новые записи inbox_messages: классифицирует, отвечает по базе знаний
в исходный канал (VK личка/коммент, Telegram личка/коммент), ставит скоринг
готовности лида и эскалирует горячих (score >= 70) карточкой в TG-чат Анны.

Заявки с сайта и почта не автоответятся (нет канала) — только скоринг+карточка.
"""
import json
from typing import Optional

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.inbox import InboxMessage
from services.kb_content import KNOWLEDGE_BASE

MODEL = "claude-sonnet-4-6"
HOT_SCORE = 70

_base_url = getattr(settings, "ANTHROPIC_BASE_URL", None)
_client = anthropic.AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    base_url=_base_url if _base_url else None,
)

_PROMPT_HEAD = (
    "Ты — первая линия отдела продаж платформы «Торги Земли» (torgi-zemli.ru).\n"
    "Отвечаешь на комментарии и сообщения из соцсетей от имени команды («мы»).\n\n"
    + KNOWLEDGE_BASE + "\n"
)

_PROMPT_RULES = """ПРАВИЛА ОТВЕТА:
1. Коротко: 2-5 предложений, по делу, тёплый экспертный тон. Без канцелярита и «инфоцыганства», без обещаний («точно выиграете», «гарантируем доход» — запрещено).
2. Не выдумывай факты, цены и сроки. Чего нет в базе знаний — честно скажи «уточню у команды» и попроси контакт, поле escalate=true.
3. Юридические гарантии не давай — только информируй и предлагай AI-аудит или сопровождение.
4. Каждый ответ мягко веди к следующему шагу: карта лотов, AI-аудит, чеклист или канал @torgi_zemli. Один CTA на ответ, не дави.
5. Если человек интересуется покупкой — задай ОДИН уточняющий вопрос для квалификации (регион? бюджет? себе или инвестиция?).
6. Агрессия, жалоба, претензия — не спорь, поблагодари за обратную связь, escalate=true.
7. Комментарий-эмодзи или «👍» — короткая дружелюбная реакция, score низкий.
8. Пиши на русском. Без хэштегов. Эмодзи — максимум один.

СКОРИНГ ГОТОВНОСТИ (0-100):
- 0-20: спам, флуд, просто эмодзи/лайк словами.
- 21-40: общий интерес, вопрос «как это работает».
- 41-69: предметный интерес — спрашивает про регион, цену, конкретный лот, процедуру.
- 70-89: горячий — назвал регион/бюджет/срок, спрашивает как купить/оплатить, просит помощь с конкретным лотом.
- 90-100: просит человека, готов платить, оставил контакты.

Ответь СТРОГО одним JSON без markdown:
{"category": "spam" | "question" | "lead" | "complaint" | "other",
 "score": <0-100>,
 "reply": "<текст ответа>" или null (для спама — null),
 "summary": "<1 предложение: кто и что хочет>",
 "qualification": {"region": <str|null>, "budget": <str|null>, "goal": <str|null>},
 "escalate": true|false,
 "escalate_reason": "<почему>" или null}"""

SYSTEM_PROMPT = _PROMPT_HEAD + _PROMPT_RULES


# ── Каналы отправки ответов ──────────────────────────────────────────────────

async def _vk_api(method: str, params: dict) -> dict:
    params = {**params, "access_token": settings.VK_GROUP_TOKEN, "v": "5.199"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"https://api.vk.com/method/{method}", data=params)
        return r.json()


async def _send_reply(msg: InboxMessage, reply: str) -> bool:
    """Отправляет ответ в канал, откуда пришло сообщение. True = доставлено."""
    raw = msg.raw or {}
    try:
        if msg.source == "vk" and msg.event_type == "dm":
            if not settings.VK_GROUP_TOKEN or not msg.author_id:
                return False
            res = await _vk_api("messages.send", {
                "peer_id": int(msg.author_id),
                "message": reply[:3900],
                "random_id": 900_000_000 + msg.id,
            })
            return "response" in res

        if msg.source == "vk" and msg.event_type == "comment":
            owner_id = raw.get("owner_id") or raw.get("post_owner_id")
            post_id = raw.get("post_id")
            if not (settings.VK_GROUP_TOKEN and owner_id and post_id):
                return False
            params = {
                "owner_id": owner_id,
                "post_id": post_id,
                "from_group": 1,
                "message": reply[:3900],
            }
            if raw.get("id"):
                params["reply_to_comment"] = raw["id"]
            res = await _vk_api("wall.createComment", params)
            return "response" in res

        if msg.source == "max":
            from services.max_bot import send_message as max_send
            return await max_send((raw or {}).get("chat_id"), reply)

        if msg.source in ("tg_dm", "tg_comment"):
            chat_id = raw.get("chat_id")
            if not (settings.TELEGRAM_BOT_TOKEN and chat_id):
                return False
            payload = {"chat_id": chat_id, "text": reply[:3900],
                       "disable_web_page_preview": True}
            if msg.source == "tg_comment" and raw.get("message_id"):
                payload["reply_to_message_id"] = raw["message_id"]
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json=payload,
                )
                return bool(r.json().get("ok"))
    except Exception as e:
        print(f"[sales-agent] send reply error msg#{msg.id}: {type(e).__name__}: {e}")
    return False


async def _escalate(msg: InboxMessage, verdict: dict, replied: bool) -> None:
    """Карточка горячего лида в TG-чат Анны."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return
    from services.inbox_hub import SOURCE_LABELS
    q = verdict.get("qualification") or {}
    qual_parts = [f"{k}: {v}" for k, v in
                  (("Регион", q.get("region")), ("Бюджет", q.get("budget")), ("Цель", q.get("goal")))
                  if v]
    lines = [
        f"🔥 Лид #{msg.id} · score {msg.score} · {SOURCE_LABELS.get(msg.source, msg.source)}",
        f"От: {msg.author_name or msg.author_id or 'аноним'}"
        + (f" · {msg.author_url}" if msg.author_url else ""),
        "",
        f"💬 «{msg.text[:400]}»",
        f"📋 {verdict.get('summary') or ''}",
    ]
    if qual_parts:
        lines.append("🎯 " + " · ".join(qual_parts))
    if verdict.get("escalate_reason"):
        lines.append(f"⚠️ {verdict['escalate_reason']}")
    if replied and verdict.get("reply"):
        lines.append(f"\n🤖 Бот ответил: «{verdict['reply'][:300]}»")
    elif verdict.get("reply") and not replied:
        lines.append("\n(автоответ не доставлен — канал недоступен, ответь вручную)")
    if msg.post_ref:
        lines.append(f"\n{msg.post_ref}")

    chat_id = settings.INBOX_TELEGRAM_CHAT_ID or settings.ADMIN_TELEGRAM_CHAT_ID
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": "\n".join(lines),
                      "disable_web_page_preview": True},
            )
    except Exception as e:
        print(f"[sales-agent] escalate notify error: {type(e).__name__}: {e}")


# ── Мозг ─────────────────────────────────────────────────────────────────────

async def _dialog_history(db: AsyncSession, msg: InboxMessage) -> str:
    """Последние сообщения того же автора из того же источника — контекст диалога."""
    if not msg.author_id:
        return ""
    rows = (await db.execute(
        select(InboxMessage)
        .where(
            InboxMessage.source == msg.source,
            InboxMessage.author_id == msg.author_id,
            InboxMessage.id < msg.id,
        )
        .order_by(InboxMessage.id.desc())
        .limit(5)
    )).scalars().all()
    if not rows:
        return ""
    lines = []
    for m in reversed(rows):
        lines.append(f"Клиент: {m.text[:300]}")
        bot_reply = (m.raw or {}).get("bot_reply")
        if bot_reply:
            lines.append(f"Мы: {bot_reply[:300]}")
    return "\n".join(lines)


async def _classify(msg: InboxMessage, history: str) -> Optional[dict]:
    channel = {"vk": "VK", "tg_comment": "комментарий в Telegram-канале",
               "tg_dm": "личка Telegram-бота", "site": "форма на сайте",
               "mail": "почта",
               "youtube": "комментарий на YouTube (автоответ невозможен — только оценить и зафиксировать)",
               "ok": "Одноклассники", "max": "мессенджер Max"}.get(msg.source, msg.source)
    kind = "комментарий под постом" if msg.event_type == "comment" else (
        "заявка с формы" if msg.event_type == "lead_form" else "личное сообщение")

    user_block = f"Канал: {channel}. Тип: {kind}.\n"
    if history:
        user_block += f"\nИстория диалога:\n{history}\n"
    user_block += f"\nНовое сообщение клиента:\n{msg.text[:2000]}"

    resp = await _client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_block}],
    )
    text = resp.content[0].text.strip()
    # Срезаем возможные ```json обёртки
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.startswith("json") else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    print(f"[sales-agent] unparseable verdict for msg#{msg.id}: {text[:200]}")
    return None


async def process_message(db: AsyncSession, msg: InboxMessage) -> None:
    # Свои же сообщения (группа VK = отрицательный from_id) не обрабатываем
    if msg.source == "vk" and msg.author_id and msg.author_id.startswith("-"):
        msg.status = "closed"
        await db.commit()
        return

    history = await _dialog_history(db, msg)
    verdict = await _classify(msg, history)
    if not verdict:
        return  # остаётся new — подхватит следующий прогон

    category = verdict.get("category") or "other"
    try:
        msg.score = max(0, min(100, int(verdict.get("score") or 0)))
    except (TypeError, ValueError):
        msg.score = 0

    if category == "spam":
        msg.status = "spam"
        await db.commit()
        return

    reply = (verdict.get("reply") or "").strip()
    replied = False
    # Заявкам с сайта/почты не автоответить — нет канала
    if reply and msg.source not in ("site", "mail"):
        replied = await _send_reply(msg, reply)
        if replied:
            raw = dict(msg.raw or {})
            raw["bot_reply"] = reply
            msg.raw = raw

    hot = msg.score >= HOT_SCORE or bool(verdict.get("escalate")) \
        or category == "complaint" or msg.event_type == "lead_form"
    msg.status = "escalated" if hot else ("answered" if replied else "closed")
    await db.commit()

    if hot:
        await _escalate(msg, verdict, replied)


async def process_new_messages(limit: int = 20) -> int:
    """Обрабатывает пачку новых входящих. Возвращает число обработанных."""
    from db.database import AsyncSessionLocal

    processed = 0
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(InboxMessage)
            .where(InboxMessage.status == "new")
            .order_by(InboxMessage.id)
            .limit(limit)
        )).scalars().all()

        for msg in rows:
            try:
                await process_message(db, msg)
                processed += 1
            except Exception as e:
                print(f"[sales-agent] error on msg#{msg.id}: {type(e).__name__}: {e}")
                await db.rollback()
    return processed
