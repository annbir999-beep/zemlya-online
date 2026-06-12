"""Одобрение/отклонение черновиков агентов — общая логика.

Используется двумя путями:
  · /admin → Агенты (api/agents.py)
  · inline-кнопки в Telegram-уведомлении (services/telegram_bot.py)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.agent_run import AgentRun


class PublishError(Exception):
    """Ошибка одобрения — человекочитаемое сообщение для UI/бота."""


async def approve_and_publish(db: AsyncSession, run: AgentRun) -> str:
    """Публикует одобренный черновик. Возвращает текст для подтверждения."""
    if run.status != "waiting_approval":
        raise PublishError(f"Запуск в статусе «{run.status}», публиковать нечего")

    output = run.output or {}

    if run.agent_name == "tg_lot_of_the_day":
        post_text = output.get("post_text")
        if not post_text:
            raise PublishError("В черновике нет текста поста")
        from services.agents.tg_lot_of_the_day import publish_to_channel
        await publish_to_channel(post_text, output.get("channel", "@torgi_zemli"))
        result = "Пост опубликован в @torgi_zemli"

    elif run.agent_name == "article_writer":
        from models.content import ContentPost
        post = (await db.execute(
            select(ContentPost).where(ContentPost.id == output.get("content_post_id"))
        )).scalar_one_or_none()
        if not post:
            raise PublishError("Статья из черновика не найдена в БД")
        post.status = "published"
        post.published_at = datetime.now(timezone.utc)
        result = f"Статья на сайте: {output.get('article_url', '')}"
        tg_text = f"{post.tg_text}\n\n🔗 {output.get('article_url', '')}".strip()
        from services.agents.tg_lot_of_the_day import publish_to_channel
        try:
            await publish_to_channel(tg_text, "@torgi_zemli")
            result += "\nАнонс ушёл в @torgi_zemli"
        except Exception as e:
            # Статья публикуется в любом случае, провал TG — не блокер
            print(f"[publishing] TG publish failed for post {post.id}: {e}")
            result += "\nАнонс в TG не ушёл — отправьте вручную"

    else:
        raise PublishError("Публикация не поддерживается для этого агента")

    run.status = "published"
    run.approved_at = datetime.now(timezone.utc)
    await db.commit()
    return result


async def skip_run(db: AsyncSession, run: AgentRun) -> str:
    if run.status != "waiting_approval":
        raise PublishError(f"Запуск в статусе «{run.status}», отклонять нечего")
    run.status = "skipped"
    output = run.output or {}
    if run.agent_name == "article_writer" and output.get("content_post_id"):
        from models.content import ContentPost
        post = (await db.execute(
            select(ContentPost).where(ContentPost.id == output["content_post_id"])
        )).scalar_one_or_none()
        if post:
            post.status = "skipped"
    await db.commit()
    return "Черновик отклонён"
