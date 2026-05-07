"""Модели промокодов и их использования.

Промокод — короткая строка (FIRST50, EARLY100), даёт скидку при покупке.
Может быть ограничен по числу использований, сроку действия, конкретному
тарифу. Применяется на /api/payments/create через поле `promo_code`.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from db.database import Base


class PromoCode(Base):
    __tablename__ = "promo_codes"

    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, nullable=False, index=True)  # хранится в UPPER

    # Скидка: либо процент (10..100), либо фикс. сумма в рублях. Указать одно из.
    discount_pct = Column(Integer)        # 50 = -50%
    discount_fixed = Column(Integer)       # 200 = -200 ₽

    # Ограничения
    max_uses = Column(Integer)             # None = без лимита
    used_count = Column(Integer, default=0)
    valid_until = Column(DateTime(timezone=True))  # None = бессрочный
    plan_filter = Column(String(40))       # None = на всё; 'audit_lot' = только разовый аудит

    # Только для новых пользователей (1+ покупка → промокод не действует)
    new_users_only = Column(Boolean, default=False)

    is_active = Column(Boolean, default=True)
    description = Column(String(200))      # для админа — пометка где применяется
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PromoUsage(Base):
    __tablename__ = "promo_usages"

    id = Column(Integer, primary_key=True)
    promo_code_id = Column(Integer, ForeignKey("promo_codes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    discount_applied = Column(Integer)      # фактически применённая скидка в копейках/рублях
    used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    promo = relationship("PromoCode")
