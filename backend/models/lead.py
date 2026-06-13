"""Лиды воронки A — подписки на лид-магнит «Чеклист: 12 проверок участка».

Лид — это email, оставленный посетителем за PDF-чеклист, ещё ДО регистрации.
Низкое трение (только email) = шире верх воронки. Drip-серия прогревает лида
к регистрации и первой покупке. Когда лид регистрируется тем же email —
проставляется converted_user_id, drip по нему останавливается.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime, timezone

from db.database import Base


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Откуда пришёл — из ?utm_source (tg_torgi_zemli, seo_blog, ...)
    source = Column(String(80))
    campaign = Column(String(80))

    # Токен для ссылки скачивания PDF и отписки (без раскрытия email в URL)
    token = Column(String(48), unique=True, index=True)

    pdf_sent = Column(Boolean, default=False)

    # Drip: какой шаг серии уже отправлен (0/1/3/5/8). 0 = только что захвачен.
    last_drip_step = Column(Integer, default=0)
    last_drip_at = Column(DateTime(timezone=True))

    unsubscribed = Column(Boolean, default=False)

    # Если лид позже зарегистрировался тем же email — drip останавливается
    converted_user_id = Column(Integer, ForeignKey("users.id"))
    converted_at = Column(DateTime(timezone=True))

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
