"""Модели контент-машины: новости отрасли и статьи блога.

Конвейер: news_scout собирает новости в news_items → article_writer берёт
лучшую свежую, пишет статью + TG-пост (draft) → Анна одобряет в /admin →
статья публикуется в /blog, пост — в @torgi_zemli.
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey
from datetime import datetime, timezone

from db.database import Base


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True)

    url = Column(String(1000), nullable=False)
    # SHA256 нормализованного URL — дедуп при повторных прогонах скаута
    url_hash = Column(String(64), unique=True, nullable=False, index=True)

    source = Column(String(100))          # человекочитаемое имя источника
    title = Column(String(500))
    summary = Column(Text)                # описание/лид из RSS
    published_at = Column(DateTime(timezone=True))
    fetched_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Релевантность тематике земли/торгов: совпадения ключевых слов
    relevance_score = Column(Integer, default=0, index=True)

    # new — ждёт обработки; used — по ней написана статья; skipped — отброшена
    status = Column(String(32), default="new", index=True)


class ContentPost(Base):
    __tablename__ = "content_posts"

    id = Column(Integer, primary_key=True)

    slug = Column(String(200), unique=True, nullable=False, index=True)
    title = Column(String(300), nullable=False)
    excerpt = Column(String(500))

    body_md = Column(Text)                # исходник статьи (markdown)
    body_html = Column(Text)              # отрендеренный HTML — фронт показывает как есть
    tg_text = Column(Text)                # анонс-пост для TG-канала

    # draft — ждёт одобрения; published — на сайте; skipped — отклонена
    status = Column(String(32), default="draft", index=True)

    news_item_id = Column(Integer, ForeignKey("news_items.id"))
    agent_run_id = Column(Integer)        # agent_runs.id создавшего запуска

    reading_minutes = Column(Integer)     # оценка времени чтения для карточки

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), index=True)
