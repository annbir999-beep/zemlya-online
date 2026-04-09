from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from db.database import Base


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    PERSONAL = "personal"     # Для себя
    EXPERT = "expert"         # Эксперт
    LANDLORD = "landlord"     # Лендлорд


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

    subscription_plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE)
    subscription_expires_at = Column(DateTime(timezone=True))

    # Ограничения по плану (кол-во сохранённых фильтров)
    saved_filters_limit = Column(Integer, default=3)

    notification_email = Column(Boolean, default=True)
    notification_telegram = Column(Boolean, default=False)

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
