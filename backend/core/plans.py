"""Ранжирование тарифов для серверного гейтинга премиум-данных.

Зеркало frontend/src/lib/plan.ts — держим синхронными. Это источник истины
по тому, какой тариф открывает какой блок лота на бэкенде (защита данных,
а не только UI: премиум-поля физически не уходят в ответе API).
"""
from __future__ import annotations

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


def plan_rank(user: Optional[User]) -> int:
    """Ранг тарифа пользователя (0 для анонима/None)."""
    if user is None:
        return 0
    return PLAN_RANK.get(user.subscription_plan, 0)


def has_rank(user: Optional[User], min_rank: int) -> bool:
    """True, если тариф пользователя >= требуемого ранга."""
    return plan_rank(user) >= min_rank
