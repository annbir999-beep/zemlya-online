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

# Тарифы по roadmap M1-M19: (плановый id, кол-во месяцев) -> цена в рублях.
# Внутренние коды совпадают с enum-value в БД (personal/expert/landlord),
# но публичные id в API — современные (pro/buro/buro_plus).
PLAN_PRICES = {
    # Pro — частный инвестор (бывший Personal)
    ("pro", 1): 2900,
    ("pro", 3): 7800,           # ~10% скидка
    ("pro", 12): 27800,         # ~20% скидка
    # Бюро — SMB (бывший Expert)
    ("buro", 1): 29000,
    ("buro", 3): 78000,         # ~10% скидка
    ("buro", 12): 290000,       # ~17% скидка
    # Бюро+ — растущие SMB (бывший Landlord)
    ("buro_plus", 1): 49000,
    ("buro_plus", 3): 132000,   # ~10% скидка
    ("buro_plus", 12): 470000,  # ~20% скидка
    # Разовые продукты (без подписки)
    ("audit_lot", 0): 490,      # AI-аудит одного лота — main M3 hook
    ("predd", 0): 8000,         # preDD аудит договора аренды
}

PLAN_FILTERS = {
    "pro": 5,
    "buro": 15,
    "buro_plus": 30,
}

# Маппинг публичных id → enum в БД (значение enum value сохраняется legacy)
PLAN_ENUM = {
    "pro": SubscriptionPlan.PRO,
    "buro": SubscriptionPlan.BURO,
    "buro_plus": SubscriptionPlan.BURO_PLUS,
}


class CreatePaymentRequest(BaseModel):
    plan: str          # pro | buro | buro_plus | audit_lot | predd
    months: int = 1    # 1 | 3 | 12 (для разовых = 0)
    return_url: Optional[str] = "https://xn--e1adnd0h.online/dashboard"
    lot_id: Optional[int] = None   # для разового AI-аудита: какой лот покупаем
    promo_code: Optional[str] = None  # промокод (FIRST50, EARLY и т.п.)


class PromoValidateRequest(BaseModel):
    code: str
    plan: Optional[str] = None  # план для проверки plan_filter промокода


@router.get("/plans")
async def get_plans():
    """Тарифы по roadmap M1-M19: B2B-фокус с физ-сегментом как воронкой.

    Free / Pro / Бюро / Бюро+ — подписка. Enterprise — по запросу.
    Разовые продукты: AI-аудит лота 490 ₽, preDD договора 8000 ₽.
    """
    return {
        "plans": [
            {
                "id": "free",
                "name": "Демо",
                "tagline": "Знакомство с платформой",
                "price": 0,
                "months": None,
                "filters_limit": 1,
                "audience": "physical",
                "features": [
                    "Карта и каталог 3 600+ активных лотов",
                    "1 сохранённый фильтр",
                    "5 AI-аудитов лотов в месяц",
                    "Базовая аналитика рынка",
                    "Telegram-бот: уведомления по 1 фильтру",
                ],
            },
            {
                "id": "audit_lot",
                "name": "Аудит лота",
                "tagline": "Один глубокий разбор по ссылке",
                "price": 490,
                "months": 0,
                "one_time": True,
                "audience": "physical",
                "features": [
                    "Полный AI-разбор лота: ВРИ, обременения, ЗОУИТ",
                    "Анализ договора аренды + проект договора",
                    "Сравнение с рынком (медиана ЦИАН/Авито)",
                    "Региональные особенности (выкуп, КФХ, ст. 39.18)",
                    "PDF-отчёт для скачивания",
                ],
            },
            {
                "id": "pro",
                "name": "Pro",
                "tagline": "Для частного инвестора",
                "prices": {"1": 2900, "3": 7800, "12": 27800},
                "filters_limit": 5,
                "audience": "physical",
                "features": [
                    "5 сохранённых фильтров",
                    "30 AI-аудитов лотов в месяц",
                    "Контакты администрации (отдел земельных отношений)",
                    "Калькулятор окупаемости (ROI каркасника)",
                    "PDF-отчёты по лотам",
                    "Сравнение участков, история просмотров",
                    "Экспорт в Excel/CSV",
                    "Email + Telegram уведомления",
                ],
            },
            {
                "id": "buro",
                "name": "Бюро",
                "tagline": "Для риелторов и малых девелоперов",
                "prices": {"1": 29000, "3": 78000, "12": 290000},
                "filters_limit": 15,
                "popular": True,
                "audience": "smb",
                "features": [
                    "15 сохранённых фильтров",
                    "AI-аудит без лимита",
                    "preDD аудит договора аренды — 3 в месяц",
                    "Все региональные модули",
                    "Приоритетный Telegram-бот",
                    "Алерты о снижении цены повторных торгов",
                    "Витрина «🤖 ИИ-разборы» (готовые ночные вердикты)",
                    "Расширенная аналитика по регионам",
                    "Поддержка в рабочие часы",
                ],
            },
            {
                "id": "buro_plus",
                "name": "Бюро+",
                "tagline": "Для растущих SMB",
                "prices": {"1": 49000, "3": 132000, "12": 470000},
                "filters_limit": 30,
                "audience": "smb",
                "features": [
                    "Всё из тарифа Бюро",
                    "30 сохранённых фильтров",
                    "preDD аудит договоров — без лимита",
                    "ТОР-модуль (12 ТОР + СПВ): аналитика и алерты",
                    "Приоритетная поддержка",
                    "Бета-функции до релиза",
                    "Один обучающий созвон по платформе",
                ],
            },
            {
                "id": "enterprise",
                "name": "Enterprise",
                "tagline": "Девелоперы федерального уровня, юрфирмы, фонды",
                "price_from": 120000,
                "audience": "enterprise",
                "contact_only": True,
                "features": [
                    "Персональный SLA: отклик 4ч, аптайм 99.5%",
                    "REST API + ключ + rate limit 1000/час",
                    "Customer Success менеджер",
                    "preDD-модуль с RAG по pravo.gov.ru",
                    "Compliance-пакет для DD: РКН, ФСТЭК К3",
                    "Персональные дашборды и отчёты",
                    "NDA + рамочный договор с приложениями",
                    "Годовой контракт, аванс 50%",
                    "Цена от 120 000 ₽/мес — обсуждается индивидуально",
                ],
            },
        ],
        "extras": [
            {
                "id": "predd",
                "name": "Аудит договора (preDD)",
                "price": 8000,
                "description": "Аудит договора аренды или проекта договора: 11 проверок, OCR приложений, сводный отчёт",
            },
        ],
    }


@router.post("/create")
async def create_payment(
    data: CreatePaymentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Разовые продукты — months=0, period не применяется
    is_one_time = data.plan in ("audit_lot", "predd")
    months = 0 if is_one_time else data.months

    price = PLAN_PRICES.get((data.plan, months))
    if not price:
        raise HTTPException(status_code=400, detail="Неверный тариф или период")

    # Применение промокода (опционально)
    promo_obj = None
    promo_discount = 0
    if data.promo_code:
        from models.promo import PromoCode
        from sqlalchemy import func as _func
        code_norm = data.promo_code.strip().upper()
        promo_q = await db.execute(
            select(PromoCode).where(_func.upper(PromoCode.code) == code_norm)
        )
        promo_obj = promo_q.scalar_one_or_none()
        if not promo_obj or not promo_obj.is_active:
            raise HTTPException(status_code=400, detail="Промокод не найден или отключён")
        if promo_obj.valid_until and promo_obj.valid_until < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Промокод истёк")
        if promo_obj.max_uses is not None and (promo_obj.used_count or 0) >= promo_obj.max_uses:
            raise HTTPException(status_code=400, detail="Промокод закончился")
        if promo_obj.plan_filter and promo_obj.plan_filter != data.plan:
            raise HTTPException(status_code=400, detail=f"Промокод действует только для тарифа «{promo_obj.plan_filter}»")
        if promo_obj.new_users_only:
            from models.alert import Subscription as _Sub
            paid_q = await db.execute(
                select(_func.count()).select_from(_Sub).where(
                    _Sub.user_id == user.id, _Sub.status == "succeeded"
                )
            )
            if (paid_q.scalar() or 0) > 0:
                raise HTTPException(status_code=400, detail="Промокод только для новых пользователей")

        if promo_obj.discount_pct:
            promo_discount = int(price * promo_obj.discount_pct / 100)
        elif promo_obj.discount_fixed:
            promo_discount = min(promo_obj.discount_fixed, price - 1)
        price = max(1, price - promo_discount)  # минимум 1 ₽ — ЮКасса не принимает 0

    if is_one_time:
        descr = "AI-аудит лота — Земля.ОНЛАЙН" if data.plan == "audit_lot" else "preDD аудит договора — Земля.ОНЛАЙН"
        if data.plan == "audit_lot" and data.lot_id:
            descr = f"AI-аудит лота #{data.lot_id} — Земля.ОНЛАЙН"
    else:
        plan_label = {"pro": "Pro", "buro": "Бюро", "buro_plus": "Бюро+"}.get(data.plan, data.plan)
        descr = f"Подписка «{plan_label}» на {months} мес. — Земля.ОНЛАЙН"

    # Если ЮКасса не настроена — даём понятное сообщение, не падаем
    if not settings.YUKASSA_SHOP_ID or not settings.YUKASSA_SECRET_KEY \
            or "test" in settings.YUKASSA_SECRET_KEY.lower() \
            or "your_" in settings.YUKASSA_SECRET_KEY.lower():
        raise HTTPException(
            status_code=503,
            detail="Платёжная система настраивается. Напишите @ZemlyaOnlineBot или anna_zemlya в Telegram — оформим оплату по реквизитам ИП.",
        )

    # Используем Invoice API ЮКассы — он работает сразу для нового магазина,
    # в отличие от Payment API, который требует активации платёжной формы
    # менеджером. Invoice генерирует ссылку yookassa.ru/my/i/..., клиент
    # переходит и оплачивает картой/СБП. После оплаты ЮКасса шлёт нам
    # стандартный payment.succeeded webhook с теми же metadata.
    import base64, secrets as _s, httpx as _httpx
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td

    auth = base64.b64encode(
        f"{settings.YUKASSA_SHOP_ID}:{settings.YUKASSA_SECRET_KEY}".encode()
    ).decode()
    expires = (_dt.now(_tz.utc) + _td(days=3)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    invoice_payload = {
        "payment_data": {
            "amount": {"value": f"{price:.2f}", "currency": "RUB"},
            "description": descr[:128],  # ЮКасса лимитит 128 символов
            "capture": True,
            "metadata": {
                "user_id": str(user.id),
                "plan": data.plan,
                "months": str(months),
                "lot_id": str(data.lot_id or ""),
            },
        },
        "cart": [
            {
                "description": descr[:128],
                "price": {"value": f"{price:.2f}", "currency": "RUB"},
                "quantity": "1.00",
            }
        ],
        "delivery_method_data": {"type": "self"},
        "expires_at": expires,
        "description": descr[:128],
    }

    try:
        async with _httpx.AsyncClient(timeout=20) as _c:
            resp = await _c.post(
                "https://api.yookassa.ru/v3/invoices",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Idempotence-Key": _s.token_hex(16),
                    "Content-Type": "application/json",
                },
                json=invoice_payload,
            )
        if resp.status_code != 200:
            print(f"[payments] yookassa invoice error {resp.status_code}: {resp.text[:300]}")
            raise HTTPException(
                status_code=503,
                detail="Платёжная система временно недоступна. Напишите @ZemlyaOnlineBot или anna_zemlya в Telegram — оформим оплату вручную.",
            )
        invoice = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[payments] yookassa http error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Платёжная система временно недоступна. Напишите @ZemlyaOnlineBot или anna_zemlya в Telegram — оформим оплату вручную.",
        )

    invoice_id = invoice.get("id")
    pay_url = (invoice.get("delivery_method") or {}).get("url")

    # Сохраняем pending-платёж — yukassa_payment_id хранит invoice_id;
    # после оплаты webhook получит payment.succeeded с metadata, по
    # которым мы найдём этот pending Subscription и активируем подписку.
    sub = Subscription(
        user_id=user.id,
        plan=data.plan,
        amount=price,
        months=months,
        yukassa_payment_id=invoice_id,
        status="pending",
    )
    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    # Зафиксировать использование промокода (даже если оплата пока pending)
    if promo_obj:
        from models.promo import PromoUsage
        promo_obj.used_count = (promo_obj.used_count or 0) + 1
        db.add(PromoUsage(
            promo_code_id=promo_obj.id,
            user_id=user.id,
            subscription_id=sub.id,
            discount_applied=promo_discount,
        ))
        await db.commit()

    return {
        "payment_id": invoice_id,
        "confirmation_url": pay_url,
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

    # Платёж по Invoice API имеет свой payment_id, не совпадающий с invoice_id.
    # Subscription создаётся с invoice_id, поэтому ищем сначала по metadata
    # (user_id + plan), затем — fallback на payment_id для прямых платежей.
    md = payment_obj.get("metadata") or {}
    md_user_id = md.get("user_id")
    md_plan = md.get("plan")

    sub = None
    if md_user_id and md_plan:
        result = await db.execute(
            select(Subscription)
            .where(
                Subscription.user_id == int(md_user_id),
                Subscription.plan == md_plan,
                Subscription.status == "pending",
            )
            .order_by(Subscription.id.desc())
            .limit(1)
        )
        sub = result.scalar_one_or_none()

    # fallback: прямой поиск по yookassa id (если metadata пуст)
    if not sub:
        result = await db.execute(select(Subscription).where(Subscription.yukassa_payment_id == payment_id))
        sub = result.scalar_one_or_none()

    if not sub or sub.status == "succeeded":
        return {"status": "already_processed"}

    sub.status = "succeeded"
    sub.paid_at = datetime.now(timezone.utc)

    # Разовые продукты — даём пользователю 1 аудит/preDD
    if sub.plan in ("audit_lot", "predd"):
        result_user = await db.execute(select(User).where(User.id == sub.user_id))
        u = result_user.scalar_one_or_none()
        if u:
            u.free_audits_left = (u.free_audits_left or 0) + 1
        await db.commit()
        return {"status": "ok", "type": "one_time"}

    # Подписочный тариф — обновляем пользователя
    result = await db.execute(select(User).where(User.id == sub.user_id))
    user = result.scalar_one_or_none()
    if user and sub.plan in PLAN_ENUM:
        now = datetime.now(timezone.utc)
        base = user.subscription_expires_at if user.subscription_expires_at and user.subscription_expires_at > now else now
        user.subscription_plan = PLAN_ENUM[sub.plan]
        user.subscription_expires_at = base + timedelta(days=30 * sub.months)
        user.saved_filters_limit = PLAN_FILTERS.get(sub.plan, user.saved_filters_limit)

    await db.commit()
    return {"status": "ok"}


# ── Промокоды: проверка перед оплатой ──────────────────────────────────────────

@router.post("/promo/validate")
async def validate_promo(
    data: PromoValidateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Проверяет промокод и возвращает применимую скидку без создания платежа."""
    from models.promo import PromoCode
    from sqlalchemy import func as _func

    code_norm = (data.code or "").strip().upper()
    if not code_norm:
        raise HTTPException(status_code=400, detail="Введите промокод")

    promo_q = await db.execute(
        select(PromoCode).where(_func.upper(PromoCode.code) == code_norm)
    )
    promo = promo_q.scalar_one_or_none()
    if not promo or not promo.is_active:
        raise HTTPException(status_code=404, detail="Промокод не найден")
    if promo.valid_until and promo.valid_until < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Промокод истёк")
    if promo.max_uses is not None and (promo.used_count or 0) >= promo.max_uses:
        raise HTTPException(status_code=400, detail="Промокод закончился")
    if promo.plan_filter and data.plan and promo.plan_filter != data.plan:
        raise HTTPException(
            status_code=400,
            detail=f"Промокод действует только для тарифа «{promo.plan_filter}»",
        )

    return {
        "valid": True,
        "code": promo.code,
        "discount_pct": promo.discount_pct,
        "discount_fixed": promo.discount_fixed,
        "plan_filter": promo.plan_filter,
        "description": promo.description,
    }


# ── Enterprise contact form (без оплаты — просто заявка) ───────────────────────

class EnterpriseRequest(BaseModel):
    name: str
    company: str
    email: str
    phone: Optional[str] = None
    estimated_users: Optional[int] = None
    comment: Optional[str] = None


@router.post("/enterprise/request")
async def submit_enterprise_request(
    data: EnterpriseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Заявка на Enterprise-тариф. Шлёт email на ящик владельца + сохраняет в БД.

    На M3 это просто email-уведомление; в M13 здесь будет CRM с воронкой.
    """
    import aiosmtplib
    from email.mime.text import MIMEText

    body = (
        f"Новая заявка Enterprise — Земля.ОНЛАЙН\n\n"
        f"Имя: {data.name}\n"
        f"Компания: {data.company}\n"
        f"Email: {data.email}\n"
        f"Телефон: {data.phone or '—'}\n"
        f"Сотрудников: {data.estimated_users or '—'}\n\n"
        f"Комментарий:\n{data.comment or '—'}\n"
    )

    if settings.SMTP_USER:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = f"💼 Enterprise-заявка от {data.company}"
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.SMTP_USER  # себе на ящик
        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=True,
            )
        except Exception as e:
            print(f"[enterprise-request] email error: {type(e).__name__}: {e}")

    return {"ok": True, "message": "Заявка принята, свяжемся в течение 24 часов"}
