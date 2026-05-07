from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from db.database import Base


class SubscriptionPlan(str, enum.Enum):
    """Тарифы по roadmap M1-M19. Старые value-строки сохранены для
    backward-compatibility с существующими записями в БД."""
    FREE = "free"               # Демо: 1 фильтр, AI 5/мес
    PRO = "personal"            # Pro 2900 ₽/мес — частный инвестор. (was PERSONAL)
    BURO = "expert"             # Бюро 29000 ₽/мес — риелторы/малые девелоперы (SMB).
    BURO_PLUS = "landlord"      # Бюро+ 49000 ₽/мес — растущие SMB + ТОР-модуль.
    ENTERPRISE = "enterprise"   # Enterprise от 120000 ₽/мес — по запросу.


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(200))
    phone = Column(String(20))
    telegram_id = Column(String(50))

    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    subscription_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    subscription_expires_at = Column(DateTime(timezone=True))

    # Ограничения по плану (кол-во сохранённых фильтров)
    saved_filters_limit = Column(Integer, default=3)

    notification_email = Column(Boolean, default=True)
    notification_telegram = Column(Boolean, default=False)

    # Бесплатный первый AI-аудит — снимает барьер первой покупки.
    # При регистрации = 1 (один аудит в подарок). Списывается при первом /api/ai/assess.
    free_audits_left = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login_at = Column(DateTime(timezone=True))

    # Связи
    saved_lots = relationship("SavedLot", back_populates="user")
    alerts = relationship("Alert", back_populates="user")
    subscriptions = relationship("Subscription", back_populates="user")
    views = relationship("LotView", back_populates="user")


class SavedLot(Base):
    __tablename__ = "saved_lots"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="saved_lots")
    lot = relationship("Lot", back_populates="saved_by")


class LotView(Base):
    __tablename__ = "lot_views"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # nullable — анонимные просмотры
    lot_id = Column(Integer, ForeignKey("lots.id"), nullable=False)
    viewed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="views")
    lot = relationship("Lot", back_populates="viewed_by")
