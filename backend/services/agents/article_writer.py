"""Агент «Автор статей» — пишет статью для /blog и анонс для TG по свежей новости.

Логика:
1. Берёт самую релевантную необработанную новость за последние 7 дней.
2. Одним AI-вызовом получает JSON: заголовок, лид, статья (markdown), TG-пост.
3. Рендерит markdown в HTML, создаёт ContentPost со статусом draft.
4. Шлёт Анне черновик в Telegram; публикация — кнопкой в /admin → Агенты.

Числа и факты агент берёт только из текста новости — сверка с БД лотов
здесь не нужна (статья про отрасль, не про конкретный лот).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.content import ContentPost, NewsItem
from services.agents.base import BaseAgent
from services.ai_assessment import client as anthropic_client
from services.telegram_bot import _tg_client

SITE = "https://земля.online"
CHANNEL = "@torgi_zemli"

ARTICLE_PROMPT = """Ты — редактор блога сервиса «Земля.ОНЛАЙН» (агрегатор земельных аукционов РФ с AI-оценкой участков).
По новости ниже напиши материал для блога и анонс для Telegram-канала.

Требования к статье:
- 400-700 слов, markdown (## подзаголовки, списки)
- Угол зрения: что это значит для инвестора в землю / покупателя участка на торгах
- Если новость про закон — назови конкретные статьи и что меняется на практике
- Без воды, без канцелярита, без выдуманных фактов: только то, что есть в новости, плюс общеизвестные нормы ЗК РФ
- НЕ вставляй ссылки и URL
- В конце — 1 абзац, как тема связана с покупкой земли на торгах

Требования к TG-посту:
- 40-70 слов, цепляющий заголовок с одним эмодзи, 2-3 факта, без ссылок

Новость:
Заголовок: {title}
Источник: {source}
Текст: {summary}

Верни СТРОГО JSON без пояснений и без markdown-обёртки:
{{"title": "заголовок статьи до 90 знаков", "excerpt": "лид 1-2 предложения до 200 знаков", "article_md": "статья в markdown", "tg_text": "текст TG-поста"}}"""

GATE_PROMPT = """Сервис «Земля.ОНЛАЙН» — агрегатор ЗЕМЕЛЬНЫХ аукционов: участки, аренда и выкуп земли, ЗК РФ, кадастр, ИЖС/СНТ/сельхоз.
Новость:
{title}
{summary}

Подходит ли эта новость для блога про инвестиции именно в ЗЕМЛЮ (не в здания, не в коммерческую недвижимость, не в квартиры)? Ответь одним словом: да или нет."""

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def make_slug(title: str, max_len: int = 80) -> str:
    low = title.lower()
    out = []
    for ch in low:
        if ch in TRANSLIT:
            out.append(TRANSLIT[ch])
        elif ch.isascii() and (ch.isalnum()):
            out.append(ch)
        else:
            out.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return slug[:max_len].rstrip("-") or "post"


def _extract_json(text: str) -> dict:
    """Достаёт JSON из ответа модели, терпим к ```json-обёрткам."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(json)?\s*|\s*```$", "", cleaned, flags=re.S)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("В ответе модели нет JSON")
    return json.loads(cleaned[start:end + 1])


class ArticleWriterAgent(BaseAgent):
    name = "article_writer"

    async def _pick_news(self, db: AsyncSession) -> NewsItem | None:
        """Кандидаты по убыванию ключевого скора + AI-фильтр «именно про землю».

        Ключевые слова дают ложные срабатывания (биржевые «торги», офисная
        «недвижимость» — кейс «Макфы»), поэтому каждого кандидата прогоняем
        через быстрый да/нет-вопрос модели. Не про землю → status=skipped.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        candidates = (await db.execute(
            select(NewsItem)
            .where(NewsItem.status == "new", NewsItem.fetched_at >= cutoff)
            .order_by(desc(NewsItem.relevance_score), desc(NewsItem.fetched_at))
            .limit(10)
        )).scalars().all()

        for news in candidates:
            message = await anthropic_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=5,
                messages=[{"role": "user", "content": GATE_PROMPT.format(
                    title=news.title,
                    summary=(news.summary or "")[:500],
                )}],
            )
            answer = message.content[0].text.strip().lower()
            if answer.startswith("да"):
                return news
            news.status = "skipped"
            await db.commit()
        return None

    async def _unique_slug(self, db: AsyncSession, base: str) -> str:
        slug = base
        n = 2
        while (await db.execute(
            select(ContentPost.id).where(ContentPost.slug == slug)
        )).scalar_one_or_none():
            slug = f"{base}-{n}"
            n += 1
        return slug

    async def execute(self, db: AsyncSession) -> tuple[dict[str, Any], bool]:
        news = await self._pick_news(db)
        if not news:
            return {"message": "Нет свежих необработанных новостей"}, False

        message = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4000,
            messages=[{"role": "user", "content": ARTICLE_PROMPT.format(
                title=news.title,
                source=news.source or "",
                summary=(news.summary or news.title)[:4000],
            )}],
        )
        data = _extract_json(message.content[0].text)
        for field in ("title", "excerpt", "article_md", "tg_text"):
            if not data.get(field):
                raise ValueError(f"Модель не вернула поле {field}")

        import markdown as md_lib
        body_html = md_lib.markdown(data["article_md"], extensions=["extra"])
        slug = await self._unique_slug(db, make_slug(data["title"]))
        words = len(data["article_md"].split())

        post = ContentPost(
            slug=slug,
            title=data["title"][:300],
            excerpt=data["excerpt"][:500],
            body_md=data["article_md"],
            body_html=body_html,
            tg_text=data["tg_text"],
            status="draft",
            news_item_id=news.id,
            reading_minutes=max(1, round(words / 160)),
        )
        db.add(post)
        news.status = "used"
        await db.commit()
        await db.refresh(post)

        output = {
            "content_post_id": post.id,
            "slug": slug,
            "title": post.title,
            "excerpt": post.excerpt,
            "tg_text": post.tg_text,
            "article_url": f"{SITE}/blog/{slug}",
            "news_url": news.url,
            "news_source": news.source,
        }
        await self._notify_admin(post)
        return output, True  # ждёт одобрения в /admin

    async def _notify_admin(self, post: ContentPost) -> None:
        admin_chat_id = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", None) or "574728046"
        if not settings.TELEGRAM_BOT_TOKEN:
            return
        text = (
            "📰 Черновик статьи готов\n\n"
            f"«{post.title}»\n\n{post.excerpt}\n\n"
            f"TG-анонс:\n{post.tg_text}\n\n"
            f"———\nОдобрить: {SITE}/admin (раздел «Агенты»)"
        )
        try:
            async with _tg_client(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_chat_id, "text": text, "disable_web_page_preview": True},
                )
        except Exception as e:
            print(f"[agent:article_writer] admin notify failed: {e}")
