from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text
from datetime import datetime, timezone

from db.database import Base


class AgentRun(Base):
    """Журнал запусков продукт-агентов.

    Каждый запуск агента (Лот дня, bug-triage, morning-check) пишет сюда
    строку: что сделал, статус, нужно ли одобрение, результат.
    Страница /admin → Агенты читает эту таблицу.
    """
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True)

    # Имя агента — машинный идентификатор: "tg_lot_of_the_day", "bug_triage", ...
    agent_name = Column(String(64), nullable=False, index=True)

    # running / done / failed / waiting_approval / published / skipped
    status = Column(String(32), nullable=False, default="running", index=True)

    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime(timezone=True))

    # Результат работы агента — произвольный JSON.
    # Для "Лот дня": {lot_id, post_text, channel}
    output = Column(JSON)

    # True — результат требует ручного одобрения Анны (например, пост в канал).
    requires_approval = Column(Boolean, default=False)
    approved_at = Column(DateTime(timezone=True))

    # Текст ошибки, если status = failed
    error = Column(Text)
