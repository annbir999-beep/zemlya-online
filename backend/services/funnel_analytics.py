"""Сквозная аналитика авто-отдела продаж — этап 4.

Считает воронку «соцсети → лид → регистрация → оплата» по источникам (utm_source
= соцсеть) и выдаёт компактный текстовый блок для утренней сводки в Telegram.

Слои воронки и откуда берём:
- Инбокс (обратная связь из соцсетей): InboxMessage.source / .status / .score
- Лиды (захват email за чеклист):     Lead.source / .campaign
- Регистрации:                        User.signup_source / .signup_campaign
- Оплаты (выручка):                   Subscription (succeeded) → User.signup_source

Кампания видео-серии помечается utm_campaign=video30 в ссылках постов — по нему
отделяем трафик роликов от прочего.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models.inbox import InboxMessage
from models.lead import Lead
from models.user import User
from models.alert import Subscription

VIDEO_CAMPAIGN = "video30"

# utm_source роликов → человекочитаемая метка (для строк воронки)
SOURCE_LABEL = {
    "vk": "VK",
    "youtube": "YouTube",
    "tg": "Telegram",
    "telegram": "Telegram",
    "max": "Max",
    "ok": "Одноклассники",
    "rutube": "Rutube",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}

# source инбокса → метка
INBOX_LABEL = {
    "vk": "VK",
    "tg_comment": "TG-коммент",
    "tg_dm": "TG-личка",
    "youtube": "YouTube",
    "site": "Сайт",
    "ok": "ОК",
    "max": "Max",
    "mail": "Почта",
}


def _label(src: str | None, table: dict) -> str:
    if not src:
        return "—"
    return table.get(src, src)


async def collect_funnel(db: AsyncSession, days: int = 1) -> dict:
    """Собирает метрики воронки за последние `days` суток."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── Слой 1: инбокс (обратная связь) ──
    inbox_rows = (await db.execute(
        select(InboxMessage.source, InboxMessage.status, func.count())
        .where(InboxMessage.created_at > since)
        .group_by(InboxMessage.source, InboxMessage.status)
    )).all()
    inbox_by_source: dict[str, dict] = {}
    inbox_totals = {"total": 0, "answered": 0, "escalated": 0, "spam": 0}
    for src, status, cnt in inbox_rows:
        d = inbox_by_source.setdefault(src, {"total": 0, "answered": 0, "escalated": 0, "spam": 0})
        d["total"] += cnt
        inbox_totals["total"] += cnt
        if status in d:
            d[status] += cnt
            inbox_totals[status] += cnt

    # ── Слой 2: лиды (захват за чеклист) по источнику ──
    lead_rows = (await db.execute(
        select(Lead.source, func.count())
        .where(Lead.created_at > since)
        .group_by(Lead.source)
    )).all()
    leads_by_source = {src or "—": cnt for src, cnt in lead_rows}

    # ── Слой 3: регистрации по источнику ──
    reg_rows = (await db.execute(
        select(User.signup_source, func.count())
        .where(User.created_at > since)
        .group_by(User.signup_source)
    )).all()
    regs_by_source = {src or "—": cnt for src, cnt in reg_rows}

    # ── Слой 4: оплаты (выручка) по источнику регистрации плательщика ──
    pay_rows = (await db.execute(
        select(User.signup_source, func.count(), func.coalesce(func.sum(Subscription.amount), 0))
        .join(User, User.id == Subscription.user_id)
        .where(and_(Subscription.status == "succeeded", Subscription.paid_at > since))
        .group_by(User.signup_source)
    )).all()
    pay_by_source = {src or "—": {"count": cnt, "sum": float(amt or 0)} for src, cnt, amt in pay_rows}

    # ── Отдельно: срез кампании video30 (трафик роликов) ──
    video_leads = (await db.execute(
        select(func.count()).select_from(Lead)
        .where(and_(Lead.created_at > since, Lead.campaign == VIDEO_CAMPAIGN))
    )).scalar() or 0
    video_regs = (await db.execute(
        select(func.count()).select_from(User)
        .where(and_(User.created_at > since, User.signup_campaign == VIDEO_CAMPAIGN))
    )).scalar() or 0
    video_pay = (await db.execute(
        select(func.count(), func.coalesce(func.sum(Subscription.amount), 0))
        .join(User, User.id == Subscription.user_id)
        .where(and_(
            Subscription.status == "succeeded",
            Subscription.paid_at > since,
            User.signup_campaign == VIDEO_CAMPAIGN,
        ))
    )).first()

    return {
        "days": days,
        "inbox_totals": inbox_totals,
        "inbox_by_source": inbox_by_source,
        "leads_by_source": leads_by_source,
        "regs_by_source": regs_by_source,
        "pay_by_source": pay_by_source,
        "video": {
            "leads": video_leads,
            "regs": video_regs,
            "pay_count": (video_pay[0] if video_pay else 0),
            "pay_sum": float(video_pay[1]) if video_pay and video_pay[1] else 0.0,
        },
    }


async def build_funnel_section(db: AsyncSession, days: int = 1) -> str:
    """Готовый Markdown-блок для утренней сводки. Пустой строкой не роняет отчёт."""
    try:
        m = await collect_funnel(db, days=days)
    except Exception as e:  # аналитика не должна ронять утренний отчёт
        print(f"[funnel] collect error: {type(e).__name__}: {e}")
        return ""

    it = m["inbox_totals"]
    lines = ["📥 *Авто-отдел продаж за сутки*"]

    if it["total"]:
        lines.append(
            f"• Обращений: {it['total']} "
            f"(бот ответил {it['answered']}, горячих {it['escalated']}, спам {it['spam']})"
        )
        # разбивка по каналам, где было хоть одно обращение
        parts = []
        for src, d in sorted(m["inbox_by_source"].items(), key=lambda kv: -kv[1]["total"]):
            parts.append(f"{_label(src, INBOX_LABEL)} {d['total']}")
        if parts:
            lines.append("• Каналы: " + ", ".join(parts))
    else:
        lines.append("• Обращений за сутки: 0")

    # Воронка кампании роликов
    v = m["video"]
    if v["leads"] or v["regs"] or v["pay_count"]:
        lines.append(
            f"• Кампания роликов (video30): лидов {v['leads']} → "
            f"регистраций {v['regs']} → оплат {v['pay_count']} "
            f"({v['pay_sum']:,.0f} ₽)".replace(",", " ")
        )

    # Топ источников по деньгам (если были оплаты)
    pay = m["pay_by_source"]
    if pay:
        top = sorted(pay.items(), key=lambda kv: -kv[1]["sum"])[:5]
        money = ", ".join(
            f"{_label(src, SOURCE_LABEL)} {d['sum']:,.0f} ₽".replace(",", " ")
            for src, d in top if d["sum"] > 0
        )
        if money:
            lines.append("• Выручка по источникам: " + money)

    return "\n".join(lines) + "\n\n"
