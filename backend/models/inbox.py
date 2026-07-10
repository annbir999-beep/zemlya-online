"""Единый инбокс обратной связи — этап 1 авто-отдела продаж.

Все входящие из соцсетей (комменты, личка, заявки) нормализуются в одну
таблицу inbox_messages и дублируются уведомлением в Telegram-чат Анны.
Этап 2 добавит AI-первую линию: автоответы, скоринг и эскалацию горячих лидов.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, UniqueConstraint
from datetime import datetime, timezone

from db.database import Base


class InboxMessage(Base):
    __tablename__ = "inbox_messages"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_inbox_source_external"),
    )

    id = Column(Integer, primary_key=True)

    # Откуда: vk / tg_comment / tg_dm / site / ok / youtube / instagram / max / mail
    source = Column(String(30), nullable=False, index=True)
    # Тип: comment / dm / lead_form
    event_type = Column(String(20), nullable=False, default="comment")

    # Идентификатор события в исходной сети — для дедупликации ретраев вебхуков
    external_id = Column(String(120))

    author_id = Column(String(80))
    author_name = Column(String(200))
    author_url = Column(String(300))

    text = Column(Text, nullable=False, default="")
    # Ссылка на пост/страницу, под которым оставлен комментарий
    post_ref = Column(String(400))

    raw = Column(JSON)

    # new / answered / escalated / spam / closed
    status = Column(String(20), default="new", index=True)
    # Скоринг готовности лида (0-100), заполняет AI на этапе 2
    score = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
