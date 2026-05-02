import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import httpx
from typing import List

from core.config import settings
from models.user import User
from models.alert import Alert
from models.lot import Lot


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
      <a href="https://zemlya.online/dashboard/alerts" style="color:#2563eb;">Управление алертами</a>
    </p>
  </div>
</body>
</html>"""


async def send_email_alert(user: User, alert: Alert, lots: List[Lot]):
    if not settings.SMTP_USER or not user.email:
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌍 {len(lots)} новых участков — «{alert.name}»"
    msg["From"] = settings.SMTP_USER
    msg["To"] = user.email

    html = _build_email_html(user, alert, lots)
    msg.attach(MIMEText(html, "html", "utf-8"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        use_tls=True,
    )


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

    lines.append(f"\n[Открыть все результаты](https://zemlya.online/lots?alert={alert.id})")

    text = "\n".join(lines)
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user.telegram_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
        )
