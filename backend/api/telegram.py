"""
Telegram webhook + endpoints для привязки аккаунта.

POST /api/telegram/webhook       — принимает обновления от Telegram
POST /api/telegram/link-code     — генерирует одноразовый код для привязки (auth)
DELETE /api/telegram/unlink      — отвязывает текущий Telegram от аккаунта (auth)
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.users import get_current_user
from core.config import settings
from db.database import get_db
from models.user import User
from services.telegram_bot import (
    LINK_CODE_TTL,
    SITE_URL,
    issue_link_code,
    process_update,
)


router = APIRouter()


class LinkCodeResponse(BaseModel):
    code: str
    bot_username: str
    deep_link: str
    expires_in: int


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    # Проверка подписи: Telegram пришлёт заголовок только если мы установили secret_token
    if settings.TELEGRAM_WEBHOOK_SECRET:
        if x_telegram_bot_api_secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Bad secret token")

    update = await request.json()
    await process_update(db, update)
    return {"ok": True}


@router.post("/link-code", response_model=LinkCodeResponse)
async def create_link_code(user: User = Depends(get_current_user)):
    if not settings.TELEGRAM_BOT_USERNAME:
        raise HTTPException(
            status_code=503,
            detail="Telegram bot не настроен. Обратитесь к администратору.",
        )
    code = await issue_link_code(user.id)
    bot_username = settings.TELEGRAM_BOT_USERNAME.lstrip("@")
    return LinkCodeResponse(
        code=code,
        bot_username=bot_username,
        deep_link=f"https://t.me/{bot_username}?start={code}",
        expires_in=LINK_CODE_TTL,
    )


@router.delete("/unlink")
async def unlink_telegram(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user.telegram_id = None
    user.notification_telegram = False
    await db.commit()
    return {"ok": True}


@router.get("/status")
async def telegram_status(user: User = Depends(get_current_user)):
    return {
        "linked": bool(user.telegram_id),
        "telegram_id": user.telegram_id,
        "notifications_enabled": user.notification_telegram,
        "bot_username": settings.TELEGRAM_BOT_USERNAME.lstrip("@") if settings.TELEGRAM_BOT_USERNAME else None,
        "site_url": SITE_URL,
    }
