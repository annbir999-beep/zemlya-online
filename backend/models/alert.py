from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from db.database import Base
from models.lot import LandPurpose, AuctionType


class AlertChannel(str, enum.Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    BOTH = "both"


class Alert(Base):
    """Сохранённый поиск с уведомлениями"""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200))  # Название фильтра, заданное пользователем
    is_active = Column(Boolean, default=True)
    channel = Column(Enum(AlertChannel), default=AlertChannel.EMAIL)

    # Фильтры (хранятся как JSON для гибкости)
    filters = Column(JSON, nullable=False)
    # Пример:
    # {
    #   "region_codes": ["77", "50"],
    #   "price_min": 100000,
    #   "price_max": 5000000,
    #   "area_min": 600,
    #   "area_max": 100000,
    #   "land_purposes": ["izhs", "snt"],
    #   "auction_types": ["sale"],
    #   "near_water": false,
    #   "keywords": "Подмосковье лес"
    # }

    last_triggered_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="alerts")
    notifications = relationship("AlertNotification", back_populates="alert")


class AlertNotification(Base):
    """История уведомлений"""
    __tablename__ = "alert_notifications"

    id = Column(Integer, primary_key=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    lot_ids = Column(JSON)  # [lot_id, ...]
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    channel = Column(Enum(AlertChannel))
    success = Column(Boolean, default=True)

    alert = relationship("Alert", back_populates="notifications")


class Subscription(Base):
    """История оплат / подписок"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(String(50))
    amount = Column(Float)
    currency = Column(String(10), default="RUB")
    yukassa_payment_id = Column(String(100))
    status = Column(String(50))   # pending, succeeded, cancelled
    months = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="subscriptions")
