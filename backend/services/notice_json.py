"""
Парсер подписанного JSON-извещения torgi.gov.

В detail-ответе `/api/public/lotcards/{id}` есть блок `noticeSignedData`
с `fileId` — это .json файл с полными реквизитами организатора:
  bidderOrg / rightHolderOrg: fullName, inn, kpp, ogrn,
                              legalAddress, actualAddress,
                              contPerson, phone, email

Это надёжнее regex-эвристик по тексту PDF: данные структурированы и
официально подписаны организатором.
"""
import json
import re
from typing import Optional


def _normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}"
    if len(digits) == 10:
        return f"+7 ({digits[0:3]}) {digits[3:6]}-{digits[6:8]}-{digits[8:]}"
    return raw.strip() or None


def _split_emails(value: Optional[str]) -> list[str]:
    if not value:
        return []
    parts = re.split(r"[;,\s]+", value)
    out = []
    seen = set()
    for p in parts:
        p = p.strip().rstrip(".,;")
        if "@" in p and 5 < len(p) < 80 and p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out


def _split_phones(value: Optional[str]) -> list[str]:
    if not value:
        return []
    # Делим по запятым/переводам/«доб.»
    parts = re.split(r"[;,\n]|доб\.?\s*\d+", value)
    out = []
    seen = set()
    for p in parts:
        norm = _normalize_phone(p)
        if norm:
            digits = re.sub(r"\D", "", norm)
            if digits not in seen:
                seen.add(digits)
                out.append(norm)
    return out


def parse_notice_json(content: bytes | str) -> dict:
    """Достаёт из JSON-извещения структурированные контакты.
    Возвращает {organizer_name, contacts}, где contacts совместим
    с форматом, который уже хранится в Lot.organizer_contacts.
    """
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="ignore")
    else:
        text = content

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}

    # Приоритет: bidderOrg (организатор торгов) → rightHolderOrg (правообладатель)
    org = data.get("bidderOrg") or {}
    if not org or not org.get("fullName"):
        org = data.get("rightHolderOrg") or {}

    if not org:
        return {}

    name = (org.get("fullName") or "").strip() or None
    contacts: dict = {}

    phones = _split_phones(org.get("phone"))
    if phones:
        contacts["phones"] = phones

    emails = _split_emails(org.get("email"))
    if emails:
        contacts["emails"] = emails

    if org.get("inn"):
        contacts["inn"] = str(org["inn"]).strip()
    if org.get("kpp"):
        contacts["kpp"] = str(org["kpp"]).strip()
    if org.get("ogrn"):
        contacts["ogrn"] = str(org["ogrn"]).strip()

    person = (org.get("contPerson") or "").strip()
    if person and person not in ("-", "—", ""):
        contacts["contact_person"] = person

    addr = (org.get("actualAddress") or org.get("legalAddress") or "").strip()
    if addr and len(addr) > 10:
        contacts["address"] = addr

    return {"organizer_name": name, "contacts": contacts}
