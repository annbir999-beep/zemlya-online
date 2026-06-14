"""Drip-серия воронки A для лидов (подписались на чеклист, ещё не зарегистрированы).

5 касаний по дням с момента захвата:
  0 — чеклист (PDF во вложении) + что внутри платформы
  1 — как работает AI-скоринг и оценка ликвидности
  3 — кейс с цифрами (реальный риск, пойманный аудитом)
  5 — промокод на первый AI-аудит
  8 — оффер: зарегистрируйся, первый аудит бесплатно

Письма шлются через Resend (SMTP на VPS заблокирован). Цель всей серии —
довести лида до регистрации (CTA ведут на /register?ref-источник).
"""
from __future__ import annotations

import base64

from core.config import settings
from services.lead_magnet import get_checklist_pdf
from services.notifications import _send_via_resend

SITE = settings.SITE_URL


def _wrap(headline: str, body_html: str, cta_text: str, cta_url: str, unsub_url: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;color:#1f2937">
  <div style="background:linear-gradient(135deg,#16a34a,#0d9488);padding:24px;border-radius:14px 14px 0 0;color:white">
    <h1 style="margin:0;font-size:21px">{headline}</h1>
  </div>
  <div style="background:#f9fafb;padding:24px;border-radius:0 0 14px 14px">
    {body_html}
    <div style="text-align:center;margin:26px 0">
      <a href="{cta_url}" style="display:inline-block;padding:12px 28px;background:#16a34a;color:white;text-decoration:none;border-radius:10px;font-weight:700;font-size:15px">{cta_text}</a>
    </div>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
    <p style="font-size:11px;color:#9ca3af;text-align:center;margin:0;line-height:1.5">
      Вы получили это письмо, потому что скачали чеклист на torgi-zemli.ru.<br>
      <a href="{unsub_url}" style="color:#9ca3af">Отписаться</a>
    </p>
  </div>
</body></html>"""


def _day0(unsub: str) -> str:
    body = """
    <p style="font-size:14px">Спасибо! Ваш <b>чеклист «12 проверок участка перед торгами»</b> — во вложении к этому письму (PDF).</p>
    <p style="font-size:14px">Пройдите эти 12 пунктов по каждому лоту до внесения задатка — большинство дорогих ошибок на торгах это пропущенный пункт из списка.</p>
    <p style="font-size:14px">А чтобы не проверять вручную 30 страниц документации — наш AI делает все 12 проверок за 5 минут и отдаёт PDF-отчёт. Первый разбор после регистрации — бесплатно.</p>
    """
    return _wrap("Ваш чеклист готов", body, "Открыть платформу →", SITE, unsub)


def _day1(unsub: str) -> str:
    body = """
    <p style="font-size:14px">Вчера вы получили чеклист. Сегодня — коротко о том, как мы автоматизируем самую муторную часть: оценку ликвидности.</p>
    <ul style="line-height:1.6;font-size:14px">
      <li>📊 <b>Скоринг 0-100</b> — по дисконту к рынку, удалённости от города и его населению</li>
      <li>🗺 <b>Карта</b> с 3 600+ активными лотами по всей РФ</li>
      <li>🔍 <b>Фильтры</b> по ВРИ, цене, площади, переуступке (ст. 22 ЗК) и банкротным лотам</li>
    </ul>
    <p style="font-size:14px">Откройте карту и отсортируйте лоты по скору — лучшие окажутся сверху.</p>
    """
    return _wrap("Как найти выгодный лот за минуту", body, "Открыть карту →", SITE, unsub)


def _day3(unsub: str) -> str:
    body = """
    <p style="background:white;border-left:3px solid #16a34a;padding:12px 14px;border-radius:4px;font-size:14px;margin:0 0 16px">
      <b>Кейс: Подмосковье.</b> Покупатель внёс задаток 600 000 ₽ на участок ИЖС в 35 км от Москвы.
      AI-аудит показал: в проекте договора <b>прямо запрещена переуступка</b>, хотя по ст. 22 п.5 ЗК РФ
      при аренде 5+ лет она обычно разрешена. Стратегия выхода через перепродажу прав рассыпалась бы.
      Заявку отозвали, задаток вернули.
    </p>
    <p style="font-size:14px">Пункт 7 вашего чеклиста — ровно про это. AI проверяет его автоматически по тексту договора.</p>
    """
    return _wrap("Один пункт чеклиста спас 600 000 ₽", body, "Проверить свой лот →", f"{SITE}/audit-lot", unsub)


def _day5(unsub: str) -> str:
    body = """
    <p style="font-size:14px">Готовы проверить реальный лот? Дарим скидку на первый AI-аудит.</p>
    <p style="background:#fef3c7;padding:14px 16px;border-radius:10px;font-size:14px;margin:16px 0">
      Промокод <code style="background:white;padding:3px 8px;border-radius:3px;font-size:15px">TG_FRIEND-25</code> —
      <b>−25%</b> на разовый AI-аудит (490 → 367 ₽). Действует до конца лета.
    </p>
    <p style="font-size:14px">Полный разбор: ВРИ, обременения, ЗОУИТ, риски договора, цена против рынка — и PDF-отчёт на руки.</p>
    """
    return _wrap("Скидка на первый разбор лота", body, "Применить промокод →", f"{SITE}/audit-lot", unsub)


def _day8(unsub: str) -> str:
    body = """
    <p style="font-size:14px">Последнее письмо серии. Если планируете участвовать в торгах — зарегистрируйтесь:
    <b>первый AI-аудит бесплатно</b>, плюс сохранённые фильтры и уведомления о новых лотах в Telegram.</p>
    <p style="font-size:14px">Покупаете 5+ лотов в месяц? Тариф <a href="{site}/pricing" style="color:#0d9488"><b>Pro за 2 900 ₽/мес</b></a> —
    30 аудитов, контакты администраций, экспорт в Excel.</p>
    """.replace("{site}", SITE)
    return _wrap("Первый аудит — бесплатно при регистрации", body, "Зарегистрироваться →", f"{SITE}/register", unsub)


# шаг -> (тема, функция-html)
LEAD_STEPS = {
    0: ("Ваш чеклист «12 проверок участка перед торгами»", _day0),
    1: ("Как найти выгодный лот за минуту — Земля.ОНЛАЙН", _day1),
    3: ("Один пункт чеклиста спас 600 000 ₽ — Земля.ОНЛАЙН", _day3),
    5: ("Скидка −25% на первый AI-аудит лота — Земля.ОНЛАЙН", _day5),
    8: ("Первый аудит бесплатно при регистрации — Земля.ОНЛАЙН", _day8),
}


async def send_lead_email(email: str, token: str, step: int) -> bool:
    """Шлёт письмо drip-серии лида. День 0 — с PDF-чеклистом во вложении."""
    if step not in LEAD_STEPS:
        return False
    subject, html_fn = LEAD_STEPS[step]
    unsub_url = f"{SITE}/api/leads/unsubscribe?token={token}"
    html = html_fn(unsub_url)

    attachments = None
    if step == 0:
        pdf_b64 = base64.b64encode(get_checklist_pdf()).decode()
        attachments = [{"filename": "Chek-list-12-proverok-uchastka.pdf", "content": pdf_b64}]

    # List-Unsubscribe — Gmail/Mail показывают кнопку «Отписаться» и поднимают
    # инбокс-репутацию рассылки. One-Click по RFC 8058.
    headers = {
        "List-Unsubscribe": f"<{unsub_url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    try:
        await _send_via_resend(to=email, subject=subject, html=html, attachments=attachments, headers=headers)
        return True
    except Exception as e:
        print(f"[lead-drip] send error step={step} email={email}: {type(e).__name__}: {e}")
        return False
