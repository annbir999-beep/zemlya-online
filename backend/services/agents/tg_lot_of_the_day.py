"""Агент «Лот дня» — раз в день готовит пост для TG-канала @torgi_zemli.

Логика:
1. Берёт топ-скор активный лот, который ещё не публиковали.
2. Генерит текст поста через Anthropic-прокси.
3. Сохраняет черновик в agent_runs (status=waiting_approval).
4. Шлёт Анне в Telegram черновик на одобрение.
5. Публикация в канал — вручную из /admin → Агенты (кнопка «Опубликовать»).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.lot import Lot, LotStatus
from models.agent_run import AgentRun
from services.agents.base import BaseAgent
from services.ai_assessment import client as anthropic_client
from services.telegram_bot import _tg_client

# Канонический адрес сайта (settings.SITE_URL). ИИ домен в промпт не даём —
# с punycode-формами он ошибался (писал лот.online вместо земля.online),
# поэтому ссылку всегда подставляем кодом отдельно.
SITE = settings.SITE_URL
CHANNEL = "@torgi_zemli"

POST_PROMPT = """Ты — SMM-редактор Telegram-канала про земельные аукционы РФ.
Напиши короткий пост «Лот дня» для канала по данным участка ниже.

Требования к посту:
- Цепляющий первый заголовок (1 строка, с эмодзи)
- 3-4 буллета с ключевыми фактами (цена, площадь, регион, дисконт/скор)
- Без воды и канцелярита, живой язык
- В конце — короткий призыв посмотреть лот на сайте
- 3-4 хэштега
- Всего 50-90 слов
- НЕ выдумывай факты — используй только данные ниже
- ВАЖНО: НЕ вставляй никаких ссылок, URL и доменов — ссылку добавим отдельно

Данные участка:
{lot_data}

Верни только текст поста, без пояснений и без ссылок."""


class TgLotOfTheDayAgent(BaseAgent):
    name = "tg_lot_of_the_day"

    async def _already_posted_lot_ids(self, db: AsyncSession) -> set[int]:
        """ID лотов, которые этот агент уже брал в прошлых запусках."""
        rows = (await db.execute(
            select(AgentRun.output).where(
                AgentRun.agent_name == self.name,
                AgentRun.output.isnot(None),
            )
        )).scalars().all()
        ids: set[int] = set()
        for out in rows:
            if isinstance(out, dict) and out.get("lot_id"):
                ids.add(int(out["lot_id"]))
        return ids

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        posted = await self._already_posted_lot_ids(db)

        # Топ-скор активный лот с координатами и ценой, ещё не публиковавшийся
        q = (
            select(Lot)
            .where(
                Lot.status == LotStatus.ACTIVE,
                Lot.score.isnot(None),
                Lot.start_price.isnot(None),
            )
            .order_by(desc(Lot.score))
            .limit(50)
        )
        candidates = (await db.execute(q)).scalars().all()
        lot = next((l for l in candidates if l.id not in posted), None)
        if not lot:
            return {"message": "Нет подходящих лотов для поста"}, False

        # Формируем данные для промпта
        lot_data = "\n".join(filter(None, [
            f"Название: {lot.title}" if lot.title else None,
            f"Регион: {lot.region_name}" if lot.region_name else None,
            f"Адрес: {lot.address}" if lot.address else None,
            f"Начальная цена: {lot.start_price:,.0f} ₽".replace(",", " ") if lot.start_price else None,
            f"Площадь: {lot.area_sqm:,.0f} м²".replace(",", " ") if lot.area_sqm else None,
            f"Назначение: {lot.land_purpose.value}" if lot.land_purpose else None,
            f"Скор инвестпривлекательности: {lot.score}/100" if lot.score else None,
            f"Дисконт к рынку: {lot.discount_to_market_pct:.0f}%" if lot.discount_to_market_pct else None,
            f"% НЦ к кадастровой: {lot.pct_price_to_cadastral:.0f}%" if lot.pct_price_to_cadastral else None,
        ]))
        lot_url = f"{SITE}/lots/{lot.id}"

        # Генерим пост (без ссылки — ИИ её перевирает)
        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": POST_PROMPT.format(
                lot_data=lot_data,
            )}],
        )
        ai_text = message.content[0].text.strip()
        # Ссылку добавляем сами, в готовом виде — гарантированно правильную
        post_text = f"{ai_text}\n\n🔗 {lot_url}"

        output = {
            "lot_id": lot.id,
            "lot_url": lot_url,
            "post_text": post_text,
            "channel": CHANNEL,
        }

        # Шлём черновик Анне на одобрение
        await self._notify_admin(post_text, lot_url)

        return output, True  # requires_approval=True

    async def _notify_admin(self, post_text: str, lot_url: str) -> None:
        """Отправляет черновик поста админу в Telegram с кнопками одобрения."""
        admin_chat_id = settings.ADMIN_TELEGRAM_CHAT_ID
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        run_id = self.current_run.id if self.current_run else None
        text = (
            "📝 *Черновик «Лот дня»* готов к публикации\n\n"
            f"{post_text}"
        )
        payload = {
            "chat_id": admin_chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        if run_id:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ Опубликовать", "callback_data": f"agent_pub:{run_id}"},
                    {"text": "❌ Пропустить", "callback_data": f"agent_skip:{run_id}"},
                ]]
            }
        try:
            async with _tg_client(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json=payload,
                )
        except Exception as e:
            print(f"[agent:tg_lot_of_the_day] admin notify failed: {e}")


async def publish_to_channel(post_text: str, channel: str = CHANNEL) -> dict:
    """Публикует одобренный пост в TG-канал. Вызывается из API при одобрении.

    Бот @ZemlyaOnlineBot должен быть администратором канала @torgi_zemli.
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан")
    async with _tg_client(timeout=15) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": channel,
                "text": post_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            },
        )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API: {data.get('description', 'unknown error')}")
    return data
