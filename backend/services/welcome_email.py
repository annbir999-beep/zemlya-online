"""Welcome-email при регистрации нового пользователя.

Решает M3-задачу: помочь новому юзеру понять, что делать дальше.
Внутри: благодарность, ссылка на бесплатный AI-аудит, краткий tour
по 3-м основным фичам, ссылка в Telegram-бот.
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings
from models.user import User


SITE = "https://xn--e1adnd0h.online"


def _build_html(user: User) -> str:
    name = user.name or user.email.split("@")[0]
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#1f2937">

<div style="background:linear-gradient(135deg,#16a34a,#0d9488);padding:28px;border-radius:14px 14px 0 0;color:white">
  <h1 style="margin:0;font-size:26px;font-weight:800">🌍 Добро пожаловать в Земля.ОНЛАЙН!</h1>
  <p style="margin:8px 0 0;opacity:0.9;font-size:15px">
    Спасибо за регистрацию, {name}. Мы помогаем находить выгодные земельные участки на торгах с torgi.gov.
  </p>
</div>

<div style="background:#f9fafb;padding:24px;border-radius:0 0 14px 14px">
  <div style="background:white;border:2px solid #16a34a;border-radius:12px;padding:18px;margin-bottom:18px">
    <div style="font-size:14px;color:#16a34a;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
      🎁 Подарок при регистрации
    </div>
    <div style="font-size:18px;font-weight:700;margin-bottom:6px">Ваш первый AI-аудит — бесплатно</div>
    <div style="font-size:14px;color:#4b5563;margin-bottom:14px;line-height:1.5">
      Вставьте ссылку на любой лот с torgi.gov — наш AI выдаст полный разбор:
      ВРИ, обременения, ЗОУИТ, реальная цена, риски договора. Обычно 490 ₽,
      для вас — бесплатно.
    </div>
    <a href="{SITE}/audit-lot" style="display:inline-block;padding:12px 24px;background:#16a34a;color:white;text-decoration:none;border-radius:8px;font-weight:700">
      Получить аудит →
    </a>
  </div>

  <h2 style="font-size:18px;font-weight:700;margin:24px 0 12px">С чего начать</h2>
  <ol style="padding-left:22px;line-height:1.7;font-size:14px;color:#374151">
    <li><b>Откройте карту</b> — увидите 3 600+ активных земельных лотов по всей РФ.<br>
      <a href="{SITE}/" style="color:#0d9488">{SITE}</a>
    </li>
    <li><b>Настройте фильтр</b> — регион, цена, площадь, ВРИ. Сохраните, и мы будем присылать
      уведомления о новых лотах в email и Telegram.
    </li>
    <li><b>Подключите Telegram-бот</b> @ZemlyaOnlineBot — тогда уведомления приходят мгновенно.
      Привязка — в кабинете.<br>
      <a href="{SITE}/dashboard" style="color:#0d9488">{SITE}/dashboard</a>
    </li>
  </ol>

  <h2 style="font-size:18px;font-weight:700;margin:24px 0 12px">Полезное</h2>
  <ul style="padding-left:22px;line-height:1.7;font-size:14px;color:#374151">
    <li><a href="{SITE}/blog/dokumentaciya-lota-torgi-gov" style="color:#0d9488">Как читать документацию лота</a></li>
    <li><a href="{SITE}/blog/statya-39-18-zk-rf-praktika" style="color:#0d9488">Ст. 39.18 ЗК РФ — получить землю без торгов</a></li>
    <li><a href="{SITE}/blog/oshibki-pri-vykupe-kfh" style="color:#0d9488">5 ошибок при выкупе земель К(Ф)Х</a></li>
  </ul>

  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p style="font-size:12px;color:#9ca3af;text-align:center;margin:0;line-height:1.5">
    Возникли вопросы? Напишите в Telegram <a href="https://t.me/anna_zemlya" style="color:#0d9488">@anna_zemlya</a>
    или ответьте на это письмо.<br>
    Чтобы отписаться от рассылок — отключите email-уведомления в кабинете.
  </p>
</div>

</body></html>"""


async def send_welcome_email(user: User) -> None:
    if not settings.SMTP_USER or not user.email:
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "🌍 Добро пожаловать в Земля.ОНЛАЙН — ваш первый AI-аудит бесплатно"
    msg["From"] = settings.SMTP_USER
    msg["To"] = user.email
    msg.attach(MIMEText(_build_html(user), "html", "utf-8"))
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
        print(f"[welcome] smtp error: {type(e).__name__}: {e}")
