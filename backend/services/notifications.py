from typing import List

import httpx

from core.config import settings
from models.user import User
from models.alert import Alert
from models.lot import Lot
from services.telegram_bot import _tg_client


async def _send_via_resend(
    *, to: str, subject: str, html: str,
    attachments: list | None = None, headers: dict | None = None,
) -> None:
    """Отправка письма через Resend HTTP API.

    Используется вместо aiosmtplib, потому что VPS Timeweb блокирует
    исходящие SMTP-порты (25/465/587). Resend ходит по HTTPS — не блокируется.

    attachments — список {"filename": str, "content": base64-строка} для вложений.
    headers — доп. SMTP-заголовки (напр. List-Unsubscribe для доставляемости).
    """
    if not settings.RESEND_API_KEY:
        print("[email] RESEND_API_KEY пуст — письмо не отправлено")
        return

    payload = {
        "from": settings.RESEND_FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    if attachments:
        payload["attachments"] = attachments
    if headers:
        payload["headers"] = headers

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 300:
        # Не бросаем исключение — оно поймается выше и не сломает основной поток.
        # Просто логируем для диагностики.
        print(f"[email] Resend HTTP {resp.status_code}: {resp.text[:300]}")
        # И всё-таки бросаем, чтобы caller знал
        raise RuntimeError(f"Resend returned {resp.status_code}: {resp.text[:200]}")


def _format_price(price: float) -> str:
    if not price:
        return "—"
    return f"{price:,.0f} ₽".replace(",", " ")


def _format_area(sqm: float) -> str:
    if not sqm:
        return "—"
    if sqm >= 10000:
        return f"{sqm / 10000:.2f} га"
    return f"{sqm:,.0f} кв.м"


def _build_email_html(user: User, alert: Alert, lots: List[Lot]) -> str:
    lots_html = ""
    for lot in lots[:10]:
        url = lot.lot_url or "#"
        title = lot.title or "Земельный участок"
        price = _format_price(lot.start_price)
        area = _format_area(lot.area_sqm)
        region = lot.region_name or ""
        deadline = lot.auction_end_date.strftime("%d.%m.%Y") if lot.auction_end_date else "—"

        lots_html += f"""
        <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px;">
          <h3 style="margin:0 0 8px;font-size:15px;color:#1a1a1a;">
            <a href="{url}" style="color:#2563eb;text-decoration:none;">{title[:80]}</a>
          </h3>
          <table style="width:100%;font-size:13px;color:#555;">
            <tr>
              <td>💰 Начальная цена:</td><td><b>{price}</b></td>
              <td>📐 Площадь:</td><td><b>{area}</b></td>
            </tr>
            <tr>
              <td>📍 Регион:</td><td>{region}</td>
              <td>⏰ Торги до:</td><td>{deadline}</td>
            </tr>
          </table>
          <a href="{url}" style="display:inline-block;margin-top:10px;padding:6px 14px;background:#2563eb;color:#fff;border-radius:6px;font-size:13px;text-decoration:none;">
            Открыть лот →
          </a>
        </div>"""

    count_extra = len(lots) - 10
    more_html = f"<p style='color:#888;font-size:13px;'>...и ещё {count_extra} лот(ов)</p>" if count_extra > 0 else ""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333;">
  <div style="background:#2563eb;padding:20px;border-radius:8px 8px 0 0;">
    <h1 style="color:#fff;margin:0;font-size:22px;">🌍 Земля.ПРО</h1>
    <p style="color:#bfdbfe;margin:4px 0 0;">Новые участки по вашему фильтру</p>
  </div>
  <div style="background:#f9fafb;padding:20px;border-radius:0 0 8px 8px;">
    <p>Привет, <b>{user.name or user.email}</b>!</p>
    <p>По фильтру <b>«{alert.name}»</b> появилось <b>{len(lots)}</b> новых участков:</p>
    {lots_html}
    {more_html}
    <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0;">
    <p style="font-size:12px;color:#999;">
      Вы получаете это письмо, потому что настроили алерт на Земля.ПРО.<br>
      <a href="{settings.SITE_URL}/dashboard/alerts" style="color:#2563eb;">Управление алертами</a>
    </p>
  </div>
</body>
</html>"""


async def send_email_alert(user: User, alert: Alert, lots: List[Lot]):
    if not user.email:
        return
    html = _build_email_html(user, alert, lots)
    await _send_via_resend(
        to=user.email,
        subject=f"🌍 {len(lots)} новых участков — «{alert.name}»",
        html=html,
    )


PLAN_LABELS_RU = {
    "audit_lot": "AI-аудит лота",
    "predd": "preDD аудит договора",
    "pro": "Pro",
    "buro": "Бюро",
    "buro_plus": "Бюро+",
}


def _format_expires(dt) -> str:
    if not dt:
        return "—"
    try:
        return dt.strftime("%d.%m.%Y")
    except Exception:
        return "—"


async def send_payment_email(user: User, plan: str, amount: float, *,
                             months: int = 0, free_audits_total: int = 0,
                             expires_at=None) -> None:
    """Письмо пользователю после успешной оплаты."""
    if not settings.SMTP_USER or not user.email:
        return

    plan_label = PLAN_LABELS_RU.get(plan, plan)
    is_one_time = plan in ("audit_lot", "predd")

    if is_one_time:
        subject = f"✅ Оплата получена — {plan_label}"
        cta_url = f"{settings.SITE_URL}/audit-lot"
        cta_text = "Перейти к аудиту →"
        body_inner = f"""
            <p>Спасибо за оплату <b>{plan_label}</b> на сумму <b>{_format_price(amount)}</b>.</p>
            <p>На вашем счету сейчас <b>{free_audits_total}</b> разовых аудитов.</p>
            <p>Перейдите по кнопке ниже, вставьте ссылку на лот с torgi.gov — и получите PDF-отчёт.</p>
        """
    else:
        subject = f"✅ Подписка «{plan_label}» активирована"
        cta_url = f"{settings.SITE_URL}/dashboard"
        cta_text = "Открыть кабинет →"
        body_inner = f"""
            <p>Подписка <b>«{plan_label}»</b> активна на <b>{months}</b> мес.</p>
            <p>Действует до <b>{_format_expires(expires_at)}</b>.</p>
            <p>В личном кабинете доступны все возможности тарифа: сохранённые фильтры, AI-аудит лотов, региональная аналитика.</p>
        """

    html = f"""<!DOCTYPE html>
    <html><body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f7f7f7;padding:20px;">
    <div style="max-width:560px;margin:0 auto;background:white;border-radius:10px;padding:28px;">
      <h2 style="margin:0 0 8px;color:#16a34a;">✅ Оплата прошла успешно</h2>
      {body_inner}
      <p style="margin-top:24px;">
        <a href="{cta_url}" style="display:inline-block;padding:10px 22px;background:#0d9488;color:white;border-radius:8px;text-decoration:none;font-weight:600;">{cta_text}</a>
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
      <p style="font-size:12px;color:#888;">Земля.ОНЛАЙН — агрегатор земельных аукционов РФ.<br>
      Вопросы: anna@земля.online · <a href="https://t.me/ZemlyaOnlineBot">@ZemlyaOnlineBot</a></p>
    </div></body></html>"""

    try:
        await _send_via_resend(to=user.email, subject=subject, html=html)
    except Exception as e:
        print(f"[payment-email] send failed for user {user.id}: {type(e).__name__}: {e}")


async def send_payment_telegram(user: User, plan: str, amount: float, *,
                                months: int = 0, free_audits_total: int = 0,
                                expires_at=None) -> None:
    """Telegram-уведомление пользователю после успешной оплаты."""
    if not settings.TELEGRAM_BOT_TOKEN or not user.telegram_id:
        return

    plan_label = PLAN_LABELS_RU.get(plan, plan)
    is_one_time = plan in ("audit_lot", "predd")

    if is_one_time:
        text = (
            f"✅ *Оплата получена* — {plan_label}\n"
            f"Сумма: *{_format_price(amount)}*\n"
            f"На счету: *{free_audits_total}* разовых аудитов\n\n"
            f"[Перейти к аудиту →]({settings.SITE_URL}/audit-lot)"
        )
    else:
        text = (
            f"✅ *Подписка «{plan_label}» активна*\n"
            f"Срок: {months} мес. (до {_format_expires(expires_at)})\n\n"
            f"[Открыть кабинет →]({settings.SITE_URL}/dashboard)"
        )

    try:
        async with _tg_client(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user.telegram_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
            )
    except Exception as e:
        print(f"[payment-tg] send failed for user {user.id}: {type(e).__name__}: {e}")


async def send_telegram_alert(user: User, alert: Alert, lots: List[Lot]):
    if not settings.TELEGRAM_BOT_TOKEN or not user.telegram_id:
        return

    lines = [f"🌍 *Новые участки по фильтру «{alert.name}»* — {len(lots)} шт.\n"]
    for lot in lots[:5]:
        price = _format_price(lot.start_price)
        area = _format_area(lot.area_sqm)
        url = lot.lot_url or ""
        title = (lot.title or "Участок")[:60]
        lines.append(f"• [{title}]({url})\n  💰 {price} | 📐 {area}")

    if len(lots) > 5:
        lines.append(f"\n_...и ещё {len(lots) - 5} лотов_")

    lines.append(f"\n[Открыть все результаты]({settings.SITE_URL}/lots?alert={alert.id})")

    text = "\n".join(lines)
    async with _tg_client(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user.telegram_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
        )
