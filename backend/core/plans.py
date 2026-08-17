"""Ранжирование тарифов для серверного гейтинга премиум-данных.

Зеркало frontend/src/lib/plan.ts — держим синхронными. Это источник истины
по тому, какой тариф открывает какой блок лота на бэкенде (защита данных,
а не только UI: премиум-поля физически не уходят в ответе API).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from models.user import SubscriptionPlan, User

PLAN_RANK = {
    SubscriptionPlan.FREE: 0,
    SubscriptionPlan.PRO: 1,        # Pro (personal)
    SubscriptionPlan.INVESTOR: 2,   # Инвестор
    SubscriptionPlan.BURO: 3,       # Бюро (expert)
    SubscriptionPlan.BURO_PLUS: 4,  # Бюро+ (landlord)
    SubscriptionPlan.ENTERPRISE: 5,
}

RANK_PRO = 1
RANK_INVESTOR = 2


def effective_plan(user: Optional[User]) -> SubscriptionPlan:
    """Фактический тариф с учётом срока действия подписки.

    Оплата открывает доступ до `subscription_expires_at`; после этой даты гейты
    обязаны видеть FREE, даже если ночная задача даунгрейда ещё не прошла или упала
    (сама задача — tasks.subscription_tasks.downgrade_expired_subscriptions).
    `subscription_expires_at IS NULL` = бессрочный доступ, выданный руками через
    админку (Enterprise/партнёры) — такой не истекает.
    """
    if user is None:
        return SubscriptionPlan.FREE
    plan = user.subscription_plan or SubscriptionPlan.FREE
    if plan == SubscriptionPlan.FREE:
        return SubscriptionPlan.FREE
    expires = user.subscription_expires_at
    if expires is None:
        return plan
    if expires.tzinfo is None:  # наивная дата из БД — считаем UTC
        expires = expires.replace(tzinfo=timezone.utc)
    return plan if expires > datetime.now(timezone.utc) else SubscriptionPlan.FREE


def plan_rank(user: Optional[User]) -> int:
    """Ранг тарифа пользователя (0 для анонима/None и для истёкшей подписки)."""
    if user is None:
        return 0
    return PLAN_RANK.get(effective_plan(user), 0)


def has_rank(user: Optional[User], min_rank: int) -> bool:
    """True, если тариф пользователя >= требуемого ранга."""
    return plan_rank(user) >= min_rank
