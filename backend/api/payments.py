from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
from typing import Optional
import yookassa

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
    # Инвестор — активный частный инвестор (закрывает разрыв Pro→Бюро)
    ("investor", 1): 6900,
    ("investor", 3): 18600,     # ~10% скидка
    ("investor", 12): 66000,    # ~20% скидка
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
    "investor": 10,
    "buro": 15,
    "buro_plus": 30,
}

# Сколько AI-аудитов начисляется при оплате (× кол-во месяцев). Тарифы без
# лимита (Бюро/Бюро+/Enterprise) сюда не входят — у них безлимит в api/ai.py.
PLAN_MONTHLY_AUDITS = {
    "pro": 30,
    "investor": 100,
}

# Маппинг публичных id → enum в БД (значение enum value сохраняется legacy)
PLAN_ENUM = {
    "pro": SubscriptionPlan.PRO,
    "investor": SubscriptionPlan.INVESTOR,
    "buro": SubscriptionPlan.BURO,
    "buro_plus": SubscriptionPlan.BURO_PLUS,
}


class CreatePaymentRequest(BaseModel):
    plan: str          # pro | buro | buro_plus | audit_lot | predd
    months: int = 1    # 1 | 3 | 12 (для разовых = 0)
    return_url: Optional[str] = None  # дефолт подставляется при создании платежа: settings.SITE_URL + "/dashboard"
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
                    "1 AI-аудит в подарок при регистрации",
                    "Базовые фильтры (премиум-аналитика — с тарифа Pro)",
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
                "id": "investor",
                "name": "Инвестор",
                "tagline": "Для активного частного инвестора",
                "prices": {"1": 6900, "3": 18600, "12": 66000},
                "filters_limit": 10,
                "popular": True,
                "audience": "physical",
                "features": [
                    "10 сохранённых фильтров",
                    "100 AI-аудитов лотов в месяц",
                    "preDD аудит договора аренды — 1 в месяц",
                    "Мониторинг района на карте: алерты по полигону",
                    "Приоритетный Telegram-бот",
                    "Алерты о снижении цены повторных торгов",
                    "Контакты администрации, калькулятор окупаемости",
                    "Экспорт в Excel/CSV, сравнение участков",
                ],
            },
            {
                "id": "buro",
                "name": "Бюро",
                "tagline": "Для риелторов и малых девелоперов",
                "prices": {"1": 29000, "3": 78000, "12": 290000},
                "filters_limit": 15,
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

    # Payment API ЮКассы — стандартный путь для SaaS-подписок и разовых платежей.
    # POST /v3/payments создаёт payment, возвращает confirmation.confirmation_url —
    # туда редиректим клиента. После оплаты ЮКасса шлёт payment.succeeded webhook
    # с теми же metadata, по которым находим pending Subscription и активируем.
    import base64, secrets as _s, httpx as _httpx

    auth = base64.b64encode(
        f"{settings.YUKASSA_SHOP_ID}:{settings.YUKASSA_SECRET_KEY}".encode()
    ).decode()

    # Receipt обязателен при фискализации 54-ФЗ (ИП Бирюкова — есть «Чеки от ЮКассы»).
    # Без receipt Payment API возвращает 400.
    # vat_code=1 = «Без НДС» (УСН), payment_subject=service для разовых и подписок.
    receipt_customer = {}
    if user.email:
        receipt_customer["email"] = user.email
    elif getattr(user, "phone", None):
        receipt_customer["phone"] = user.phone

    payment_payload = {
        "amount": {"value": f"{price:.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": data.return_url or f"{settings.SITE_URL}/dashboard",
        },
        "capture": True,
        "description": descr[:128],  # ЮКасса лимитит 128 символов
        "metadata": {
            "user_id": str(user.id),
            "plan": data.plan,
            "months": str(months),
            "lot_id": str(data.lot_id or ""),
        },
        "receipt": {
            "customer": receipt_customer or {"email": "noreply@xn--e1adnd0h.online"},
            "items": [{
                "description": descr[:128],
                "quantity": "1.00",
                "amount": {"value": f"{price:.2f}", "currency": "RUB"},
                "vat_code": 1,
                "payment_mode": "full_payment",
                "payment_subject": "service",
            }],
        },
    }

    try:
        async with _httpx.AsyncClient(timeout=20) as _c:
            resp = await _c.post(
                "https://api.yookassa.ru/v3/payments",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Idempotence-Key": _s.token_hex(16),
                    "Content-Type": "application/json",
                },
                json=payment_payload,
            )
        if resp.status_code != 200:
            print(f"[payments] yookassa payment error {resp.status_code}: {resp.text[:300]}")
            raise HTTPException(
                status_code=503,
                detail="Платёжная система временно недоступна. Напишите @ZemlyaOnlineBot или anna_zemlya в Telegram — оформим оплату вручную.",
            )
        payment = resp.json()
    except HTTPException:
        raise
    except Exception as e:
        print(f"[payments] yookassa http error: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=503,
            detail="Платёжная система временно недоступна. Напишите @ZemlyaOnlineBot или anna_zemlya в Telegram — оформим оплату вручную.",
        )

    payment_id = payment.get("id")
    pay_url = (payment.get("confirmation") or {}).get("confirmation_url")

    # Сохраняем pending-платёж — yukassa_payment_id совпадает с id из webhook
    # (Payment API: id создаваемого payment == id в payment.succeeded событии).
    sub = Subscription(
        user_id=user.id,
        plan=data.plan,
        amount=price,
        months=months,
        yukassa_payment_id=payment_id,
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
        "payment_id": payment_id,
        "confirmation_url": pay_url,
    }


@router.post("/webhook")
async def yukassa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """ЮКасса отправляет сюда уведомления об оплате.

    Телу запроса не доверяем: по payment_id из уведомления перепроверяем
    платёж прямым GET к API ЮКассы (рекомендуемый ими паттерн) и дальше
    работаем только с подтверждённым объектом.
    """
    data = await request.json()

    event = data.get("event")
    payment_id = (data.get("object") or {}).get("id")

    if event != "payment.succeeded" or not payment_id:
        return {"status": "ignored"}

    # Верификация: запрашиваем платёж у ЮКассы по id из уведомления
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.yookassa.ru/v3/payments/{payment_id}",
                auth=(settings.YUKASSA_SHOP_ID, settings.YUKASSA_SECRET_KEY),
            )
    except httpx.HTTPError as e:
        # 500 → ЮКасса повторит доставку уведомления позже
        raise HTTPException(status_code=500, detail=f"yookassa verify failed: {type(e).__name__}")

    if resp.status_code == 404:
        # Платёж с таким id у нас в магазине не существует — поддельное уведомление
        print(f"[payment-webhook] unknown payment_id {payment_id} — ignored")
        return {"status": "ignored"}
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"yookassa verify HTTP {resp.status_code}")

    # Дальше используем только подтверждённые данные из API
    payment_obj = resp.json()
    payment_status = payment_obj.get("status")

    if payment_status != "succeeded":
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

    from services.notifications import send_payment_email, send_payment_telegram

    # Разовые продукты — даём пользователю 1 аудит/preDD
    if sub.plan in ("audit_lot", "predd"):
        result_user = await db.execute(select(User).where(User.id == sub.user_id))
        u = result_user.scalar_one_or_none()
        if u:
            u.free_audits_left = (u.free_audits_left or 0) + 1
            # Бонус рефереру за первую покупку приглашённого
            await _credit_referrer_first_purchase(db, u, sub.id)
        await db.commit()
        if u:
            try:
                await send_payment_email(u, sub.plan, float(sub.amount or 0), free_audits_total=u.free_audits_left or 0)
                await send_payment_telegram(u, sub.plan, float(sub.amount or 0), free_audits_total=u.free_audits_left or 0)
            except Exception as e:
                print(f"[payment-webhook] notify error: {type(e).__name__}: {e}")
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
        # Pro/Инвестор: пополнение разовых AI-аудитов (N/мес × кол-во месяцев).
        # Бюро/Бюро+/Enterprise — без лимита (UNLIMITED_PLANS в api/ai.py), пополнение не нужно.
        monthly_audits = PLAN_MONTHLY_AUDITS.get(sub.plan)
        if monthly_audits:
            user.free_audits_left = (user.free_audits_left or 0) + monthly_audits * (sub.months or 1)
        # Бонус рефереру при первой успешной покупке
        await _credit_referrer_first_purchase(db, user, sub.id)

    await db.commit()
    if user:
        try:
            await send_payment_email(
                user, sub.plan, float(sub.amount or 0),
                months=sub.months or 1,
                expires_at=user.subscription_expires_at,
            )
            await send_payment_telegram(
                user, sub.plan, float(sub.amount or 0),
                months=sub.months or 1,
                expires_at=user.subscription_expires_at,
            )
        except Exception as e:
            print(f"[payment-webhook] notify error: {type(e).__name__}: {e}")
    return {"status": "ok"}


async def _credit_referrer_first_purchase(db, user, current_sub_id: int):
    """Если у пользователя есть referred_by и эта покупка — первая успешная,
    начислить пригласившему +1 бесплатный аудит."""
    if not user.referred_by:
        return
    # Проверяем что это первая успешная покупка пользователя
    prior_q = await db.execute(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status == "succeeded",
            Subscription.id != current_sub_id,
        ).limit(1)
    )
    if prior_q.scalar_one_or_none():
        return  # уже была покупка ранее, бонус не повторяем
    referrer_q = await db.execute(select(User).where(User.id == user.referred_by))
    referrer = referrer_q.scalar_one_or_none()
    if referrer:
        referrer.free_audits_left = (referrer.free_audits_left or 0) + 1


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
    from services.notifications import _send_via_resend

    body_html = (
        f"<h2>Новая заявка Enterprise — Земля.ОНЛАЙН</h2>"
        f"<p><b>Имя:</b> {data.name}<br>"
        f"<b>Компания:</b> {data.company}<br>"
        f"<b>Email:</b> {data.email}<br>"
        f"<b>Телефон:</b> {data.phone or '—'}<br>"
        f"<b>Сотрудников:</b> {data.estimated_users or '—'}</p>"
        f"<p><b>Комментарий:</b><br>{(data.comment or '—').replace(chr(10), '<br>')}</p>"
    )

    owner_inbox = "annbir999@gmail.com"  # куда падают заявки
    try:
        await _send_via_resend(
            to=owner_inbox,
            subject=f"💼 Enterprise-заявка от {data.company}",
            html=body_html,
        )
    except Exception as e:
        print(f"[enterprise-request] email error: {type(e).__name__}: {e}")

    return {"ok": True, "message": "Заявка принята, свяжемся в течение 24 часов"}
