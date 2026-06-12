"""Агент «Новостной скаут» — мониторит отраслевые RSS-ленты.

Логика:
1. Обходит источники из SOURCES (падение одного источника не валит прогон).
2. Парсит RSS (lxml), нормализует ссылки, дедуп по SHA256(url).
3. Считает релевантность по ключевым словам тематики земли/торгов.
4. Складывает прошедшие порог в news_items со статусом new.

Одобрение не требуется — скаут только собирает, публикаций не делает.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.content import NewsItem
from services.agents.base import BaseAgent

# (имя источника, url RSS-ленты) — все проверены с сервера 13.06.2026
SOURCES = [
    ("КонсультантПлюс: документы", "https://www.consultant.ru/rss/hotdocs.xml"),
    ("КонсультантПлюс: федеральные", "https://www.consultant.ru/rss/fd.xml"),
    ("Ведомости Недвижимость", "https://www.vedomosti.ru/rss/rubric/realty.xml"),
    ("Интерфакс", "https://www.interfax.ru/rss.asp"),
    ("ГАРАНТ Новости", "https://www.garant.ru/rss/news/"),
    ("Коммерсантъ", "https://www.kommersant.ru/RSS/news.xml"),
]

# Ключевые слова: вес 2 — прямая тематика, вес 1 — смежная
KEYWORDS_STRONG = [
    "земельн", "участок", "участк", "кадастр", "росреестр",
    "зк рф", "земельный кодекс", "аренда земл", "выкуп земл", "ижс",
]
KEYWORDS_WEAK = [
    "аукцион", "торги", "торгов", "снт", "лпх", "сельхоз", "генплан",
    "пзз", "межеван", "недвижимост", "муниципал", "изъят",
]
# Минус-слова: «участок» избирательный, «торги» биржевые — не наша тема
KEYWORDS_NEGATIVE = [
    "избирательн", "цик ", "выбор", "голосован", "бирж", "акци", "nasdaq",
    "котировк", "валют", "криптовалют", "футбол", "хокке",
]
MIN_RELEVANCE = 2  # порог: одно сильное слово («земельн», «кадастр») достаточно


def _relevance(text: str) -> int:
    low = text.lower()
    score = sum(2 for k in KEYWORDS_STRONG if k in low)
    score += sum(1 for k in KEYWORDS_WEAK if k in low)
    score -= sum(2 for k in KEYWORDS_NEGATIVE if k in low)
    return score


def _url_hash(url: str) -> str:
    normalized = url.strip().rstrip("/").split("?utm_")[0]
    return hashlib.sha256(normalized.encode()).hexdigest()


def _parse_rss(xml_bytes: bytes) -> list[dict[str, Any]]:
    """Минимальный RSS 2.0 парсер: item → {title, link, description, pub_date}."""
    root = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True, encoding=None))
    if root is None:
        return []
    items = []
    for item in root.iter("item"):
        def text_of(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None and el.text else ""

        pub_date = None
        raw_date = text_of("pubDate")
        if raw_date:
            try:
                pub_date = parsedate_to_datetime(raw_date)
            except (ValueError, TypeError):
                pass

        items.append({
            "title": text_of("title"),
            "link": text_of("link"),
            "description": text_of("description"),
            "pub_date": pub_date,
        })
    return items


class NewsScoutAgent(BaseAgent):
    name = "news_scout"

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        stats: dict[str, Any] = {"sources": {}, "added": 0, "duplicates": 0, "irrelevant": 0}

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ZemlyaOnlineBot/1.0)",
        }) as client:
            for source_name, feed_url in SOURCES:
                try:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    entries = _parse_rss(resp.content)
                except Exception as e:
                    stats["sources"][source_name] = f"error: {type(e).__name__}"
                    continue

                added = 0
                for entry in entries:
                    if not entry["link"] or not entry["title"]:
                        continue
                    score = _relevance(f"{entry['title']} {entry['description']}")
                    if score < MIN_RELEVANCE:
                        stats["irrelevant"] += 1
                        continue

                    h = _url_hash(entry["link"])
                    title_norm = entry["title"][:500].strip()
                    # Дедуп: по URL-хешу и по заголовку (КонсультантПлюс дублирует
                    # один документ в двух лентах с разными URL)
                    exists = (await db.execute(
                        select(NewsItem.id).where(
                            (NewsItem.url_hash == h) | (NewsItem.title == title_norm)
                        ).limit(1)
                    )).scalar_one_or_none()
                    if exists:
                        stats["duplicates"] += 1
                        continue

                    db.add(NewsItem(
                        url=entry["link"][:1000],
                        url_hash=h,
                        source=source_name,
                        title=entry["title"][:500],
                        summary=entry["description"][:5000] or None,
                        published_at=entry["pub_date"],
                        relevance_score=score,
                        status="new",
                    ))
                    added += 1

                stats["sources"][source_name] = f"ok: +{added} of {len(entries)}"
                stats["added"] += added

        await db.commit()
        return stats, False
