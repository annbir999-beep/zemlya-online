"""Агент «Разведчик спроса» — ищет людей, которые прямо сейчас ищут землю.

Зачем именно так, а не рассылкой. Массовые личные сообщения незнакомым людям
в РФ — это ст. 18 закона о рекламе (нужно предварительное согласие) плюс
мгновенный бан аккаунта на любой площадке. Поэтому агент никому ничего не
пишет сам: он находит ПУБЛИЧНЫЕ вопросы про покупку земли, оценивает, насколько
человек «горячий», и готовит черновик ответа по существу. Отправляет — Анна,
одним нажатием.

Сила ответа в данных: мы единственные, кто может ответить «в вашем регионе
сейчас N активных аукционов, из них M дешевле рынка на четверть и больше».
Такой ответ читают как помощь, а не как рекламу.

Источники:
  1. Свой инбокс (inbox_messages) — комментарии и личка из ВК, Telegram, OK,
     YouTube, сайта. Самые тёплые: человек уже пришёл к нам сам.
  2. Комментарии под чужими роликами по теме земли (YouTube Data API, ключ
     YOUTUBE_API_KEY). Здесь люди, которые про нас ещё не знают.

Результат уходит на одобрение: requires_approval=True.
"""
from __future__ import annotations

import os
import re
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.inbox import InboxMessage
from models.lot import Lot, LotSource, LotStatus
from services.agents.base import BaseAgent

# Намерение купить. Вес 3 — прямая заявка, 1 — интерес к теме.
INTENT_STRONG = [
    "куплю", "хочу купить", "ищу участок", "ищу землю", "подскажите участок",
    "как купить", "как участвовать", "хочу участвовать", "как подать заявку",
    "интересует участок", "нужен участок", "присматриваю",
]
INTENT_WEAK = [
    "участок", "земл", "аукцион", "торги", "ижс", "лпх", "снт",
    "задаток", "кадастр", "межеван", "переуступк", "аренда земл",
]
# Не лид: конкуренты, спам, продажа своего
INTENT_NEGATIVE = [
    "продам", "продаю", "продаётся", "продается", "реклама", "заработок в интернете",
    "крипт", "ставк", "казино", "подпишись", "взаимн",
]
MIN_SCORE = 45          # ниже — не показываем, чтобы не тратить внимание Анны
HOT_SCORE = 65          # выше — помечаем как горячий

# Бюджет: «до 300 тысяч», «500 т.р.», «1,5 млн», «300000 руб»
BUDGET_RE = re.compile(
    r"(\d[\d\s.,]{2,})\s*(тыс|т\.?р|млн|миллион|000|руб|₽)", re.IGNORECASE
)
# Срочность
URGENCY = ["срочно", "до конца месяца", "в этом году", "уже определился",
           "готов купить", "деньги есть", "в ближайшее время"]

YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
YT_COMMENTS = "https://www.googleapis.com/youtube/v3/commentThreads"
# Запросы под разные формулировки одного и того же спроса. Каждый поиск стоит
# 100 единиц квоты YouTube из 10 000 бесплатных в сутки — 12 запросов это 1200,
# с запасом на всё остальное.
YT_QUERIES = [
    "земельный аукцион участок", "купить участок с торгов",
    "торги земля ижс", "аукцион земли администрация",
    "как купить землю у государства", "участок за копейки торги",
    "выкуп земельного участка аукцион", "торги по банкротству земля",
    "аренда земли у администрации", "земля под ижс дешево",
    "как найти земельный участок для покупки", "кадастровая стоимость выкуп участка",
]
YT_PER_QUERY = 8          # роликов на запрос
YT_COMMENTS_PER_VIDEO = 40


def _score(text: str) -> int:
    """0-100: насколько человек похож на готового покупателя."""
    low = text.lower()
    if any(k in low for k in INTENT_NEGATIVE):
        return 0
    score = 0
    if any(k in low for k in INTENT_STRONG):
        score += 45
    score += min(25, sum(5 for k in INTENT_WEAK if k in low))
    if BUDGET_RE.search(low):
        score += 15
    if any(k in low for k in URGENCY):
        score += 10
    if "?" in text:
        score += 5
    return min(100, score)


async def _regions(db: AsyncSession) -> list[str]:
    rows = await db.execute(
        select(Lot.region_name).where(Lot.region_name.isnot(None)).distinct()
    )
    return [r[0] for r in rows.all() if r[0]]


def _find_region(text: str, regions: list[str]) -> str | None:
    """Регион в тексте. Сравниваем по корню: «Тверская область» → «тверск»."""
    low = text.lower()
    for name in regions:
        root = re.split(r"\s+", name.lower())[0][:6]
        if len(root) >= 5 and root in low:
            return name
    return None


async def _region_pitch(db: AsyncSession, region: str | None) -> str:
    """Живая цифра для ответа. Без региона — сводка по стране."""
    base = [Lot.status == LotStatus.ACTIVE, Lot.source == LotSource.TORGI_GOV]
    where = base + ([Lot.region_name == region] if region else [])

    total = (await db.execute(select(func.count(Lot.id)).where(*where))).scalar() or 0
    discounted = (await db.execute(
        select(func.count(Lot.id)).where(*where, Lot.discount_to_market_pct >= 25)
    )).scalar() or 0
    cheapest = (await db.execute(
        select(func.min(Lot.start_price)).where(*where, Lot.start_price > 0)
    )).scalar()

    where_txt = f"в регионе «{region}»" if region else "по стране"
    parts = [f"сейчас {where_txt} {total} активных земельных аукционов"]
    if discounted:
        parts.append(f"{discounted} из них дешевле рынка на четверть и больше")
    if cheapest:
        parts.append(f"самый доступный стартует с {int(cheapest):,} ₽".replace(",", " "))
    return ", ".join(parts)


def _draft(text: str, region: str | None, pitch: str) -> str:
    """Черновик ответа: сначала польза, ссылка в конце и без нажима."""
    opener = ("Смотрю, вы подбираете участок" if region is None
              else f"Если смотрите землю в регионе «{region}» —")
    return (f"{opener} по данным государственных торгов {pitch}. "
            f"Все они на одной карте с проверкой по кадастру: torgi-zemli.ru — "
            f"поиск бесплатный, регистрация не нужна. "
            f"Если скажете район и бюджет, подскажу, на что смотреть в первую очередь.")


async def _from_inbox(db: AsyncSession, regions: list[str]) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(InboxMessage)
        .where(InboxMessage.status == "new")
        .order_by(InboxMessage.created_at.desc())
        .limit(200)
    )).scalars().all()

    found = []
    for m in rows:
        score = _score(m.text or "")
        m.score = score                       # скоринг сохраняем всегда
        if score < MIN_SCORE:
            continue
        region = _find_region(m.text or "", regions)
        pitch = await _region_pitch(db, region)
        if score >= HOT_SCORE:
            m.status = "escalated"
        found.append({
            "источник": m.source,
            "автор": m.author_name or m.author_id,
            "ссылка": m.author_url or m.post_ref,
            "текст": (m.text or "")[:300],
            "регион": region,
            "оценка": score,
            "черновик": _draft(m.text or "", region, pitch),
        })
    return found


async def _from_youtube(db: AsyncSession, regions: list[str]) -> list[dict[str, Any]]:
    """Комментарии под чужими роликами по теме — там нас ещё не знают."""
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        return []

    found: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for query in YT_QUERIES:
            try:
                r = await client.get(YT_SEARCH, params={
                    "part": "id", "q": query, "type": "video",
                    "maxResults": YT_PER_QUERY,
                    # relevance, а не date: свежие ролики почти без комментариев,
                    # а спрос живёт под популярными — там сотни вопросов
                    "order": "relevance", "relevanceLanguage": "ru", "key": key,
                })
                r.raise_for_status()
                video_ids = [i["id"]["videoId"] for i in r.json().get("items", [])]
            except Exception:
                continue

            for vid in video_ids:
                try:
                    c = await client.get(YT_COMMENTS, params={
                        "part": "snippet", "videoId": vid,
                        "maxResults": YT_COMMENTS_PER_VIDEO,
                        "order": "relevance", "textFormat": "plainText", "key": key,
                    })
                    if c.status_code != 200:      # комментарии часто закрыты
                        continue
                    threads = c.json().get("items", [])
                except Exception:
                    continue

                for t in threads:
                    sn = t["snippet"]["topLevelComment"]["snippet"]
                    text = sn.get("textDisplay", "")
                    score = _score(text)
                    if score < MIN_SCORE:
                        continue
                    region = _find_region(text, regions)
                    found.append({
                        "источник": "youtube (чужой ролик)",
                        "автор": sn.get("authorDisplayName"),
                        "ссылка": f"https://www.youtube.com/watch?v={vid}"
                                  f"&lc={t['id']}",
                        "текст": text[:300],
                        "регион": region,
                        "оценка": score,
                        "черновик": _draft(text, region,
                                           await _region_pitch(db, region)),
                    })
    return found


async def _notify(leads: list[dict[str, Any]], run_id: int | None) -> None:
    """Карточки лидов в Telegram Анне. Ответ пишет она — кнопки только
    закрывают карточку, никакой автоотправки."""
    from core.config import settings

    if not settings.TELEGRAM_BOT_TOKEN or not leads:
        return
    api = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    chat = settings.ADMIN_TELEGRAM_CHAT_ID

    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(api, json={
            "chat_id": chat,
            "text": f"🔎 Разведчик спроса: найдено {len(leads)} "
                    f"(горячих {sum(1 for x in leads if x['оценка'] >= HOT_SCORE)}). "
                    f"Ниже карточки — ответ пишете вы, агент ничего не отправляет.",
        })
        for x in leads[:10]:
            region = x["регион"] or "регион не указан"
            text = (
                f"👤 {x['автор'] or 'без имени'} · {x['источник']}\n"
                f"Готовность: {x['оценка']} из 100 · {region}\n\n"
                f"Вопрос:\n«{x['текст']}»\n\n"
                f"{x['ссылка'] or ''}\n\n"
                f"Черновик ответа (скопируйте и отправьте от себя):\n"
                f"<code>{x['черновик']}</code>"
            )
            payload = {"chat_id": chat, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": True}
            if run_id:
                payload["reply_markup"] = {"inline_keyboard": [[
                    {"text": "✅ Ответила", "callback_data": f"lead_done:{run_id}"},
                    {"text": "❌ Пропустить", "callback_data": f"lead_skip:{run_id}"},
                ]]}
            try:
                await client.post(api, json=payload)
            except Exception as e:
                print(f"[lead_scout] карточка не ушла: {type(e).__name__}: {e}")


class LeadScoutAgent(BaseAgent):
    name = "lead_scout"

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        regions = await _regions(db)

        leads = await _from_inbox(db, regions)
        try:
            leads += await _from_youtube(db, regions)
        except Exception as e:
            print(f"[lead_scout] youtube пропущен: {type(e).__name__}: {e}")

        await db.commit()
        leads.sort(key=lambda x: x["оценка"], reverse=True)

        out = {
            "найдено": len(leads),
            "горячих": sum(1 for x in leads if x["оценка"] >= HOT_SCORE),
            "лиды": leads[:15],          # больше 15 за раз всё равно не обработать
        }
        await _notify(out["лиды"], self.current_run.id if self.current_run else None)
        # Одобрение нужно всегда: отправляет ответы человек, не агент.
        return out, bool(leads)
