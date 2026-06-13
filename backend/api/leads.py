"""API воронки A — лид-магнит «Чеклист: 12 проверок участка».

  · POST /api/leads/checklist       — захват email, отправка PDF, вход в drip
  · GET  /api/leads/checklist.pdf   — прямое скачивание чеклиста (публично)
  · GET  /api/leads/unsubscribe     — отписка лида от серии по токену
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ratelimit import limiter
from db.database import get_db
from models.lead import Lead
from services.lead_magnet import get_checklist_pdf

router = APIRouter()


class ChecklistRequest(BaseModel):
    email: EmailStr
    utm_source: str | None = None
    utm_campaign: str | None = None


@router.post("/checklist")
@limiter.limit("5/minute;30/hour")
async def request_checklist(
    request: Request,
    data: ChecklistRequest,
    db: AsyncSession = Depends(get_db),
):
    """Захватывает email, шлёт PDF-чеклист письмом, ставит лида в drip-серию."""
    email = data.email.lower().strip()
    lead = (await db.execute(select(Lead).where(Lead.email == email))).scalar_one_or_none()

    if lead is None:
        lead = Lead(
            email=email,
            source=(data.utm_source or "direct")[:80],
            campaign=(data.utm_campaign or None),
            token=secrets.token_urlsafe(24),
            unsubscribed=False,
        )
        db.add(lead)
        await db.flush()
    elif not lead.token:
        lead.token = secrets.token_urlsafe(24)

    # Снимаем отписку при повторном осознанном запросе чеклиста
    lead.unsubscribed = False

    # Отправляем день-0 (PDF во вложении) если ещё не слали
    from services.lead_emails import send_lead_email
    sent = await send_lead_email(lead.email, lead.token, 0)
    if sent:
        lead.pdf_sent = True
        lead.last_drip_step = 0
        lead.last_drip_at = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True, "email_sent": sent, "download_url": "/api/leads/checklist.pdf"}


@router.get("/checklist.pdf")
async def download_checklist():
    """Прямое скачивание PDF (для мгновенной выдачи на лендинге)."""
    pdf = get_checklist_pdf()
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="Chek-list-12-proverok-uchastka.pdf"'},
    )


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(token: str, db: AsyncSession = Depends(get_db)):
    lead = (await db.execute(select(Lead).where(Lead.token == token))).scalar_one_or_none()
    if lead:
        lead.unsubscribed = True
        await db.commit()
    return HTMLResponse(
        "<html><head><meta charset='utf-8'><title>Отписка</title></head>"
        "<body style='font-family:sans-serif;text-align:center;padding:60px;color:#1f2937'>"
        "<h2>Вы отписались от рассылки</h2>"
        "<p>Больше писем серии не придёт. Спасибо, что были с нами.</p>"
        "<p><a href='https://torgi-zemli.ru' style='color:#0d9488'>На сайт</a></p>"
        "</body></html>"
    )
