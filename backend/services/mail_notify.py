"""Проверка почтового ящика info@torgi-zemli.ru по IMAP и уведомления в Telegram.

Логика: на каждом прогоне берём UID всех писем INBOX, сравниваем с последним
обработанным (Redis mail:last_uid). По новым письмам шлём владельцу сообщение в
бот. BODY.PEEK — НЕ помечаем письмо прочитанным (статус в ящике у Анны сохраняется).
Первый запуск ставит базовую отметку без спама по уже лежащим письмам.
"""
from __future__ import annotations

import base64
import email
import imaplib
from email.header import decode_header

import httpx

from core.config import settings

_REDIS_KEY = "mail:last_uid"


def _decode(s: str | None) -> str:
    out = ""
    for txt, enc in decode_header(s or ""):
        out += txt.decode(enc or "utf-8", "replace") if isinstance(txt, bytes) else txt
    return out.strip()


def _notify(text: str) -> None:
    try:
        httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": settings.ADMIN_TELEGRAM_CHAT_ID, "text": text,
                  "disable_web_page_preview": "true"},
            timeout=30,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[mail_notify] telegram send failed: {e}")


def check_new_mail() -> int:
    """Проверяет INBOX, уведомляет по каждому новому письму. Возвращает их количество."""
    if not settings.IMAP_USER or not settings.IMAP_PASSWORD_B64:
        return 0
    try:
        pw = base64.b64decode(settings.IMAP_PASSWORD_B64).decode()
    except Exception:  # noqa: BLE001
        print("[mail_notify] не удалось декодировать IMAP_PASSWORD_B64")
        return 0

    from services.telegram_bot import get_redis
    r = get_redis()

    M = imaplib.IMAP4_SSL(settings.IMAP_HOST, 993)
    try:
        M.login(settings.IMAP_USER, pw)
        M.select("INBOX")
        typ, data = M.uid("search", None, "ALL")
        uids = data[0].split() if data and data[0] else []
        if not uids:
            return 0

        last = 0
        try:
            v = r.get(_REDIS_KEY)
            last = int(v) if v else 0
        except Exception:  # noqa: BLE001
            last = 0

        newest = int(uids[-1])
        if last == 0:  # первый запуск — базовая отметка, без спама по старым
            try:
                r.set(_REDIS_KEY, newest)
            except Exception:  # noqa: BLE001
                pass
            return 0

        count = 0
        for u in uids:
            if int(u) <= last:
                continue
            typ, md = M.uid("fetch", u, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if not md or not md[0]:
                continue
            msg = email.message_from_bytes(md[0][1])
            frm = _decode(msg.get("From"))
            subj = _decode(msg.get("Subject")) or "(без темы)"
            _notify(
                f"📧 Новое письмо на {settings.IMAP_USER}\n\n"
                f"👤 От: {frm}\n📌 Тема: {subj}"
            )
            count += 1

        try:
            r.set(_REDIS_KEY, newest)
        except Exception:  # noqa: BLE001
            pass
        return count
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass
