"""Drip-серия писем для не-платящих пользователей.

День 0 — welcome (отправляется сразу при регистрации, см. welcome_email.py)
День 3 — напоминание про бесплатный аудит + кейс на 1 минуту
День 7 — кейс «как сэкономили 200к» + промокод TG200 (-200₽)
День 14 — последний шанс + промокод FIRST50 (-50% на разовый аудит)

Каждый шаг шлётся только если:
  · пользователь не сделал ни одной успешной покупки
  · прошло >= N дней с регистрации
  · last_drip_step < N (т.е. этот шаг ещё не отправлен)
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import settings
from models.user import User


SITE = "https://xn--e1adnd0h.online"


def _wrap(name: str, headline: str, body_html: str, cta_text: str, cta_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#1f2937">
  <div style="background:linear-gradient(135deg,#16a34a,#0d9488);padding:24px;border-radius:14px 14px 0 0;color:white">
    <h1 style="margin:0;font-size:22px">{headline}</h1>
  </div>
  <div style="background:#f9fafb;padding:24px;border-radius:0 0 14px 14px">
    <p style="margin:0 0 16px;font-size:14px">Привет, <b>{name}</b>!</p>
    {body_html}
    <div style="text-align:center;margin:28px 0">
      <a href="{cta_url}" style="display:inline-block;padding:12px 28px;background:#16a34a;color:white;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">
        {cta_text}
      </a>
    </div>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
    <p style="font-size:11px;color:#9ca3af;text-align:center;margin:0;line-height:1.5">
      Получили это письмо потому что зарегистрировались на земля.online.<br>
      <a href="{SITE}/dashboard" style="color:#9ca3af">Управление подписками</a>
    </p>
  </div>
</body></html>"""


def _day3_html(name: str) -> str:
    body = """
    <p>Видим, что вы зарегистрировались, но ещё не пробовали наш бесплатный AI-аудит лота. У вас на счёте — <b>1 бесплатный разбор любого участка с torgi.gov</b>.</p>
    <p>Что AI делает за 5 минут:</p>
    <ul style="line-height:1.6;font-size:14px">
      <li>🏛 Анализирует ВРИ, обременения, ЗОУИТ — со ссылками на нормы ЗК РФ</li>
      <li>📜 Разбирает проект договора аренды на скрытые риски</li>
      <li>💰 Сравнивает цену с медианой ЦИАН + Авито по региону</li>
      <li>📄 Готовит PDF-отчёт для скачивания</li>
    </ul>
    <p style="font-size:14px">Просто откройте любой лот на torgi.gov, скопируйте ссылку и вставьте её в форму:</p>
    """
    return _wrap(
        name,
        "🔍 Не упустите бесплатный AI-аудит",
        body,
        "Получить бесплатный аудит →",
        f"{SITE}/audit-lot",
    )


def _day7_html(name: str) -> str:
    body = """
    <p>Земля с торгов часто имеет скрытые ловушки — и обнаруживаются они через несколько месяцев после покупки.</p>
    <p style="background:white;border-left:3px solid #16a34a;padding:12px 14px;border-radius:4px;font-size:14px;margin:16px 0">
      <b>Кейс: Подмосковье, ноябрь 2025.</b><br>
      Покупатель внёс задаток 600 000 ₽ на участок ИЖС в 35 км от Москвы.
      AI-аудит показал: в проекте договора <b>прямо запрещена переуступка</b>,
      хотя по ст. 22 п.5 ЗК РФ обычно разрешается. Покупатель планировал
      выход через перепродажу через 2 года — стратегия рассыпалась бы.
      Заявку отозвали в день торгов, задаток вернули. Сэкономлено: 12 млн ₽
      потенциальных вложений в неликвид.
    </p>
    <p style="font-size:14px">490 ₽ за один разбор окупаются мгновенно, если ловят хотя бы один такой риск.</p>
    <p style="background:#fef3c7;padding:12px 14px;border-radius:8px;font-size:14px;margin:16px 0">
      <b>Промокод <code style="background:white;padding:2px 6px;border-radius:3px">TG200</code></b> — скидка 200 ₽ на разовый аудит. Действует 7 дней.
    </p>
    """
    return _wrap(
        name,
        "💎 Один аудит окупает себя в 100 раз",
        body,
        "Купить аудит со скидкой →",
        f"{SITE}/audit-lot",
    )


def _day14_html(name: str) -> str:
    body = """
    <p>Последнее напоминание, чтобы не пропустить ничего интересного.</p>
    <p style="font-size:14px">У нас на платформе сейчас <b>3600+ активных лотов</b> по всей России. Многие из них —
    с дисконтом 40-80% к рынку. Без AI-разбора попасть в выгодный лот сложно: документация на 30+ страниц.</p>
    <p style="background:#fef3c7;padding:14px 16px;border-radius:10px;margin:16px 0">
      <b>Финальный промокод <code style="background:white;padding:3px 8px;border-radius:3px;font-size:15px">FIRST50</code></b> —
      скидка <b>50%</b> на любой разовый AI-аудит. Только для вас, действует 5 дней.
    </p>
    <p style="font-size:14px">Если планируете покупать 5+ лотов в месяц — обратите внимание на тариф
    <a href="{site}/pricing" style="color:#0d9488"><b>Pro за 2 900 ₽/мес</b></a>:
    30 аудитов, контакты администраций, экспорт Excel.</p>
    """.replace("{site}", SITE)
    return _wrap(
        name,
        "⏰ Последний шанс: −50% на AI-аудит",
        body,
        "Воспользоваться скидкой 50% →",
        f"{SITE}/audit-lot",
    )


DRIP_STEPS = {
    3: ("🔍 Не упустите бесплатный AI-аудит — Земля.ОНЛАЙН", _day3_html),
    7: ("💎 Один аудит окупает себя в 100 раз — Земля.ОНЛАЙН", _day7_html),
    14: ("⏰ Последний шанс: −50% на AI-аудит — Земля.ОНЛАЙН", _day14_html),
}


async def send_drip_email(user: User, step: int) -> bool:
    if not settings.SMTP_USER or not user.email:
        return False
    if step not in DRIP_STEPS:
        return False
    subject, html_fn = DRIP_STEPS[step]
    name = user.name or user.email.split("@")[0]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = user.email
    msg.attach(MIMEText(html_fn(name), "html", "utf-8"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            use_tls=True,
        )
        return True
    except Exception as e:
        print(f"[drip] smtp error step={step} email={user.email}: {type(e).__name__}: {e}")
        return False
