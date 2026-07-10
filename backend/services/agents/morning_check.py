"""Агент «Утренний health-check» — раз в день собирает метрики прода
и шлёт сводку владельцу в Telegram. Одобрения не требует — просто отчёт.

Заменяет ручную проверку платформы каждое утро.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.lot import Lot, LotStatus, LotSource
from models.alert import Subscription
from models.agent_run import AgentRun
from services.agents.base import BaseAgent
from services.telegram_bot import _tg_client

SITE = settings.SITE_URL

# Источник → (label, порог часов без НОВЫХ строк в БД, прежде чем считать
# источник замолчавшим). По created_at (момент вставки к НАМ), не published_at
# (дата публикации на исходном сайте) — иначе здоровый источник может
# маскировать замолчавший другой источник в общем счётчике (найдено 08.07.2026:
# torgi.gov не писал новых лотов 4 суток, а общий new_24h оставался >0 только
# за счёт ЦИАН — старая проверка ничего не заметила).
_INGEST_SOURCES = [
    (LotSource.TORGI_GOV, "torgi.gov", 30),
    (LotSource.CIAN, "ЦИАН", 30),
]


def _pct(part: int, total: int) -> str:
    if not total:
        return "0%"
    return f"{round(part / total * 100)}%"


class MorningCheckAgent(BaseAgent):
    name = "morning_check"

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)

        # ── Лоты ──
        active = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.status == LotStatus.ACTIVE)
        )).scalar() or 0

        new_24h = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.published_at > day_ago)
        )).scalar() or 0

        on_map = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.location.isnot(None))
            )
        )).scalar() or 0

        scored = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.score.isnot(None))
            )
        )).scalar() or 0

        ai_analyzed = (await db.execute(
            select(func.count()).select_from(Lot).where(Lot.ai_assessment.isnot(None))
        )).scalar() or 0

        bankrupt = (await db.execute(
            select(func.count()).select_from(Lot).where(
                and_(Lot.status == LotStatus.ACTIVE, Lot.is_bankruptcy == True)
            )
        )).scalar() or 0

        # ── Деньги ──
        pay_q = (await db.execute(
            select(func.count(), func.coalesce(func.sum(Subscription.amount), 0)).where(
                and_(Subscription.status == "succeeded", Subscription.paid_at > day_ago)
            )
        )).first()
        pay_count = pay_q[0] if pay_q else 0
        pay_sum = float(pay_q[1]) if pay_q and pay_q[1] else 0.0

        # ── Агенты: упавшие запуски за сутки ──
        failed_agents = (await db.execute(
            select(func.count()).select_from(AgentRun).where(
                and_(AgentRun.status == "failed", AgentRun.started_at > day_ago)
            )
        )).scalar() or 0

        # ── Ingest по источникам (created_at — момент вставки к нам) ──
        ingest_by_source: dict[str, int] = {}
        for src, label, hours in _INGEST_SOURCES:
            cutoff = now - timedelta(hours=hours)
            cnt = (await db.execute(
                select(func.count()).select_from(Lot).where(
                    and_(Lot.source == src, Lot.created_at > cutoff)
                )
            )).scalar() or 0
            ingest_by_source[label] = cnt

        # ── Очередь Celery ──
        queue_depth = 0
        try:
            import redis
            queue_depth = redis.Redis.from_url(settings.REDIS_URL).llen("celery")
        except Exception:
            pass

        metrics = {
            "active_lots": active,
            "new_24h": new_24h,
            "on_map": on_map,
            "map_coverage": _pct(on_map, active),
            "scored": scored,
            "scored_pct": _pct(scored, active),
            "ai_analyzed": ai_analyzed,
            "bankrupt": bankrupt,
            "payments_24h": pay_count,
            "revenue_24h": pay_sum,
            "failed_agents_24h": failed_agents,
            "ingest_by_source": ingest_by_source,
            "queue_depth": queue_depth,
        }

        # ── Сборка отчёта ──
        warnings = []
        if new_24h == 0:
            warnings.append("⚠️ За сутки не добавилось ни одного лота — проверить скрейперы")
        for src, label, hours in _INGEST_SOURCES:
            if ingest_by_source.get(label, 0) == 0:
                warnings.append(
                    f"⚠️ {label}: 0 новых лотов за {hours}ч (по created_at) — источник мог замолчать, "
                    f"даже если общий счётчик выше нуля за счёт других источников"
                )
        if active and on_map / active < 0.5:
            warnings.append(f"⚠️ Покрытие карты низкое ({metrics['map_coverage']}) — много лотов без координат")
        if failed_agents:
            warnings.append(f"⚠️ Упавших запусков агентов за сутки: {failed_agents}")
        if queue_depth > 100:
            warnings.append(
                f"⚠️ Очередь Celery раздута: {queue_depth} задач — проверить, не стакаются ли "
                f"periodic-задачи (inspect active)"
            )

        report = (
            f"☀️ *Утренний отчёт — Торги Земли*\n"
            f"{now.strftime('%d.%m.%Y')}\n\n"
            f"📊 *Лоты*\n"
            f"• Активных: {active:,}\n".replace(",", " ") +
            f"• Новых за сутки: +{new_24h}\n"
            f"• На карте: {on_map:,} ({metrics['map_coverage']})\n".replace(",", " ") +
            f"• Со скором: {scored:,} ({metrics['scored_pct']})\n".replace(",", " ") +
            f"• С AI-анализом: {ai_analyzed:,}\n".replace(",", " ") +
            f"• Банкротных: {bankrupt:,}\n".replace(",", " ") +
            f"• Ingest 30ч: " + ", ".join(f"{l} +{c}" for l, c in ingest_by_source.items()) + "\n"
            f"• Очередь: {queue_depth}\n\n" +
            f"💰 *Деньги за сутки*\n"
            f"• Платежей: {pay_count}\n"
            f"• Выручка: {pay_sum:,.0f} ₽\n\n".replace(",", " ")
        )
        if warnings:
            report += "🔔 *Требует внимания*\n" + "\n".join(warnings) + "\n\n"
        else:
            report += "✅ Критичных проблем не обнаружено\n\n"
        report += f"[Открыть админку]({SITE}/admin)"

        await self._send(report)

        return {"metrics": metrics, "report": report}, False  # отчёт, одобрения не нужно

    async def _send(self, report: str) -> None:
        admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", None) or "574728046"
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        try:
            async with _tg_client(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": admin_chat_id,
                        "text": report,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
        except Exception as e:
            print(f"[agent:morning_check] send failed: {e}")
