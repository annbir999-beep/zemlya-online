from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional
import yookassa
import hmac
import hashlib

from db.database import get_db
from models.user import User, SubscriptionPlan
from models.alert import Subscription
from api.users import get_current_user
from core.config import settings

router = APIRouter()

yookassa.Configuration.account_id = settings.YUKASSA_SHOP_ID
yookassa.Configuration.secret_key = settings.YUKASSA_SECRET_KEY

# Тарифы: (название, кол-во месяцев) -> цена в рублях
PLAN_PRICES = {
    ("personal", 1): 490,
    ("personal", 3): 1290,
    ("expert", 1): 990,
    ("expert", 3): 2690,
    ("expert", 12): 8990,
    ("landlord", 1): 1990,
    ("landlord", 3): 4990,
    ("landlord", 12): 16990,
}

PLAN_FILTERS = {
    "personal": 5,
    "expert": 15,
    "landlord": 30,
}

PLAN_ENUM = {
    "personal": SubscriptionPlan.PERSONAL,
    "expert": SubscriptionPlan.EXPERT,
    "landlord": SubscriptionPlan.LANDLORD,
}


class CreatePaymentRequest(BaseModel):
    plan: str          # personal | expert | landlord
    months: int        # 1 | 3 | 12
    return_url: Optional[str] = "https://yourdomain.ru/dashboard"


@router.get("/plans")
async def get_plans():
    """
    Тарифы по данным new.s0tka.ru:
    Demo (free) | Для себя (personal) | Эксперт (expert) | Лендлорд (landlord)
    """
    return {
        "plans": [
            {
                "id": "free",
                "name": "Демо",
                "price": 0,
                "months": None,
                "filters_limit": 0,
                "features_matrix": [
                    {"name": "Карта и каталог", "value": True},
                    {"name": "Координаты центра ЗУ", "value": True},
                    {"name": "Соотношение НЦ / КС", "value": True},
                    {"name": "Фильтр «Задаток»", "value": True},
                    {"name": "Фильтр «Рубрики»", "value": True},
                    {"name": "Сохранение фильтров", "value": "нет"},
                    {"name": "Уведомления об участках", "value": False},
                    {"name": "Переуступка «Можно»", "value": False},
                    {"name": "AI-оценка участка", "value": False},
                    {"name": "Добавление функционала", "value": "нет"},
                ],
                "features": [
                    "Карта и каталог",
                    "Координаты центра участка",
                    "Соотношение НЦ/КС",
                    "Фильтры: задаток, рубрики",
                ],
            },
            {
                "id": "personal",
                "name": "Для себя",
                "prices": {"1": 490, "3": 1290},
                "filters_limit": 5,
                "features_matrix": [
                    {"name": "Карта и каталог", "value": True},
                    {"name": "Координаты центра ЗУ", "value": False},
                    {"name": "Соотношение НЦ / КС", "value": False},
                    {"name": "Фильтр «Задаток»", "value": False},
                    {"name": "Фильтр «Рубрики»", "value": False},
                    {"name": "Сохранение фильтров", "value": "5"},
                    {"name": "Уведомления об участках", "value": False},
                    {"name": "Переуступка «Можно»", "value": False},
                    {"name": "AI-оценка участка", "value": False},
                    {"name": "Добавление функционала", "value": "минимально"},
                ],
                "features": [
                    "До 5 сохранённых фильтров",
                    "Базовая карта и каталог",
                    "Срок: 1 или 3 месяца",
                ],
            },
            {
                "id": "expert",
                "name": "Эксперт",
                "prices": {"1": 990, "3": 2690, "12": 8990},
                "filters_limit": 15,
                "popular": True,
                "features_matrix": [
                    {"name": "Карта и каталог", "value": True},
                    {"name": "Координаты центра ЗУ", "value": True},
                    {"name": "Соотношение НЦ / КС", "value": True},
                    {"name": "Фильтр «Задаток»", "value": True},
                    {"name": "Фильтр «Рубрики»", "value": True},
                    {"name": "Сохранение фильтров", "value": "15"},
                    {"name": "Уведомления об участках", "value": False},
                    {"name": "Переуступка «Можно»", "value": True},
                    {"name": "AI-оценка участка", "value": True},
                    {"name": "Добавление функционала", "value": "периодически"},
                ],
                "features": [
                    "До 15 сохранённых фильтров",
                    "Все расширенные фильтры (рубрики, задаток, НЦ/КС, даты заявок)",
                    "Координаты центра участка",
                    "Переуступка «Можно»",
                    "AI-оценка участка (Claude)",
                    "Срок: 1, 3 или 12 месяцев",
                ],
            },
            {
                "id": "landlord",
                "name": "Лендлорд",
                "prices": {"1": 1990, "3": 4990, "12": 16990},
                "filters_limit": 30,
                "features_matrix": [
                    {"name": "Карта и каталог", "value": True},
                    {"name": "Координаты центра ЗУ", "value": True},
                    {"name": "Соотношение НЦ / КС", "value": True},
                    {"name": "Фильтр «Задаток»", "value": True},
                    {"name": "Фильтр «Рубрики»", "value": True},
                    {"name": "Сохранение фильтров", "value": "30"},
                    {"name": "Уведомления об участках", "value": True},
                    {"name": "Переуступка «Можно» / «Уведомив» / «Согласовав»", "value": True},
                    {"name": "AI-оценка участка", "value": True},
                    {"name": "Добавление функционала", "value": "приоритетное"},
                ],
                "features": [
                    "До 30 сохранённых фильтров",
                    "Всё из тарифа Эксперт",
                    "Уведомления о новых участках",
                    "Переуступка: все 3 уровня (Можно / Уведомив / Согласовав)",
                    "Приоритетное добавление функционала",
                    "Срок: 1, 3 или 12 месяцев",
                ],
            },
        ]
    }


@router.post("/create")
async def create_payment(
    data: CreatePaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    price = PLAN_PRICES.get((data.plan, data.months))
    if not price:
        raise HTTPException(status_code=400, detail="Неверный тариф или период")

    payment = yookassa.Payment.create({
        "amount": {"value": str(price), "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": data.return_url},
        "capture": True,
        "description": f"Подписка «{data.plan}» на {data.months} мес. — Земля.ПРО",
        "metadata": {
            "user_id": str(user.id),
            "plan": data.plan,
            "months": str(data.months),
        },
    })

    # Сохраняем pending-платёж
    sub = Subscription(
        user_id=user.id,
        plan=data.plan,
        amount=price,
        months=data.months,
        yukassa_payment_id=payment.id,
        status="pending",
    )
    db.add(sub)
    await db.commit()

    return {
        "payment_id": payment.id,
        "confirmation_url": payment.confirmation.confirmation_url,
    }


@router.post("/webhook")
async def yukassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """ЮКасса отправляет сюда уведомления об оплате"""
    body = await request.body()
    data = await request.json()

    event = data.get("event")
    payment_obj = data.get("object", {})
    payment_id = payment_obj.get("id")
    payment_status = payment_obj.get("status")

    if event != "payment.succeeded" or payment_status != "succeeded":
        return {"status": "ignored"}

    # Находим платёж
    result = await db.execute(select(Subscription).where(Subscription.yukassa_payment_id == payment_id))
    sub = result.scalar_one_or_none()
    if not sub or sub.status == "succeeded":
        return {"status": "already_processed"}

    sub.status = "succeeded"
    sub.paid_at = datetime.now(timezone.utc)

    # Обновляем пользователя
    result = await db.execute(select(User).where(User.id == sub.user_id))
    user = result.scalar_one_or_none()
    if user:
        now = datetime.now(timezone.utc)
        # Если подписка ещё активна — продлеваем от текущей даты окончания
        base = user.subscription_expires_at if user.subscription_expires_at and user.subscription_expires_at > now else now
        user.subscription_plan = PLAN_ENUM[sub.plan]
        user.subscription_expires_at = base + timedelta(days=30 * sub.months)
        user.saved_filters_limit = PLAN_FILTERS[sub.plan]

    await db.commit()
    return {"status": "ok"}
