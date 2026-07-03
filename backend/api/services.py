"""Заявки на услуги сопровождения торгов (/services).

POST /api/services/lead — публичный (с rate-limit по IP через слоя nginx не
делаем, лимитируем простым капом в час), пишет ServiceLead и шлёт уведомление
Анне в Telegram. Продающие описания пакетов живут на фронте.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone, timedelta

from db.database import get_db
from core.config import settings
from models.lead import ServiceLead
from models.user import User
from api.users import get_current_user_optional

router = APIRouter()

PACKAGE_LABELS = {
    "turnkey": "Участие под ключ",
    "hectare": "ДВ/Арктический гектар",
    "investor": "Инвестору",
    "lot": "Заявка по лоту",
}


class ServiceLeadRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contact: str = Field(min_length=5, max_length=255)  # телефон или @telegram
    package: str = Field(default="turnkey", max_length=40)
    lot_id: Optional[int] = None
    comment: Optional[str] = Field(default=None, max_length=2000)


@router.post("/lead", status_code=201)
async def create_service_lead(
    data: ServiceLeadRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_current_user_optional),
):
    # Простейший анти-спам: не больше 20 заявок в час суммарно (форма публичная).
    hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = (await db.execute(
        select(func.count()).select_from(ServiceLead).where(ServiceLead.created_at >= hour_ago)
    )).scalar() or 0
    if recent > 20:
        raise HTTPException(status_code=429, detail="Слишком много заявок. Напишите нам в Telegram: @torgi_zemli")

    lead = ServiceLead(
        name=data.name.strip(),
        contact=data.contact.strip(),
        package=data.package if data.package in PACKAGE_LABELS else "turnkey",
        lot_id=data.lot_id,
        comment=(data.comment or "").strip()[:2000] or None,
        user_id=user.id if user else None,
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)

    # Уведомление Анне в TG — сразу, лид горячий
    try:
        import httpx
        admin_chat = getattr(settings, "ADMIN_TELEGRAM_CHAT_ID", None) or "574728046"
        if settings.TELEGRAM_BOT_TOKEN:
            pkg = PACKAGE_LABELS.get(lead.package, lead.package)
            lot_line = f"\nЛот: {settings.SITE_URL}/lots/{lead.lot_id}" if lead.lot_id else ""
            user_line = f"\nАккаунт: {user.email}" if user else ""
            text = (
                f"🤝 НОВАЯ ЗАЯВКА НА УСЛУГИ #{lead.id}\n"
                f"Пакет: {pkg}\n"
                f"Имя: {lead.name}\n"
                f"Контакт: {lead.contact}"
                f"{lot_line}{user_line}"
                + (f"\nКомментарий: {lead.comment}" if lead.comment else "")
            )
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": admin_chat, "text": text},
                )
    except Exception as e:
        print(f"[service-lead] tg notify error: {type(e).__name__}: {e}")

    return {"id": lead.id, "status": "ok"}
