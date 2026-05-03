"""
Извлечение контактов организатора торгов (отдел земельных отношений
муниципалитета) из текста извещения PDF.

PDF API torgi.gov не отдаёт реквизиты структурированно — они лежат в
свободной части извещения. Вытаскиваем регулярками: телефоны, email,
ИНН, физический адрес и ФИО ответственного лица.
"""
import re
from typing import Optional


# +7 / 8 + 10 цифр. Допускаем разделители ()-., пробелы.
_PHONE_RE = re.compile(
    r"(?:\+7|8|7)[\s\-\(]*\d{3}[\s\-\)\.]*\d{3}[\s\-\.]*\d{2}[\s\-\.]*\d{2}"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# ИНН: 10 цифр (юрлицо) или 12 (ИП/физлицо). Берём только рядом со словом «ИНН».
_INN_RE = re.compile(r"ИНН[\s:№]*(\d{10,12})", re.IGNORECASE)
# КПП (только юрлицо)
_KPP_RE = re.compile(r"КПП[\s:№]*(\d{9})", re.IGNORECASE)
# ОГРН (13 цифр)
_OGRN_RE = re.compile(r"ОГРН[\s:№]*(\d{13,15})", re.IGNORECASE)
# ФИО ответственного: «контактное лицо: ИО Фамилия» / «ответственный:» / «исполнитель:»
_CONTACT_PERSON_RE = re.compile(
    r"(?:контактн[ыо][её]\s*лиц[оа]|ответственн[ыоа]?[йяе]|исполнитель)[\s:—\-]*([А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)+)",
    re.IGNORECASE,
)
# «адрес: ...» — берём строку до конца предложения/новой строки
_ADDRESS_RE = re.compile(
    r"(?:почтовый\s*адрес|юридический\s*адрес|адрес\s*организатора|адрес[\s:]*)[\s:—\-]*((?:[^.\n;]{15,200}?)(?:\.|\n|;|$))",
    re.IGNORECASE,
)


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw
    # Приводим +7XXX к виду +7 (XXX) XXX-XX-XX
    if digits[0] == "8" and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) == 11 and digits[0] == "7":
        return f"+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:]}"
    return raw.strip()


def extract_contacts(text: Optional[str]) -> dict:
    """Возвращает словарь с контактами или {} если ничего не найдено."""
    if not text or len(text) < 50:
        return {}

    contacts: dict = {}

    # Телефоны — собираем уникальные и нормализуем
    phones = []
    seen_digits = set()
    for m in _PHONE_RE.finditer(text):
        raw = m.group(0)
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 10 and digits not in seen_digits:
            seen_digits.add(digits)
            phones.append(_normalize_phone(raw))
        if len(phones) >= 5:
            break
    if phones:
        contacts["phones"] = phones

    # Emails
    emails = []
    seen_e = set()
    for m in _EMAIL_RE.finditer(text):
        e = m.group(0).strip().rstrip(".,;")
        # Отсекаем мусор типа .pdf и слишком длинных доменов
        if "@" not in e or len(e) > 80:
            continue
        if e.lower() in seen_e:
            continue
        seen_e.add(e.lower())
        emails.append(e)
        if len(emails) >= 5:
            break
    if emails:
        contacts["emails"] = emails

    # ИНН
    m = _INN_RE.search(text)
    if m:
        contacts["inn"] = m.group(1)

    # КПП
    m = _KPP_RE.search(text)
    if m:
        contacts["kpp"] = m.group(1)

    # ОГРН
    m = _OGRN_RE.search(text)
    if m:
        contacts["ogrn"] = m.group(1)

    # ФИО ответственного
    m = _CONTACT_PERSON_RE.search(text)
    if m:
        contacts["contact_person"] = m.group(1).strip()

    # Адрес
    m = _ADDRESS_RE.search(text)
    if m:
        addr = re.sub(r"\s+", " ", m.group(1)).strip(" .,;-—")
        if 15 < len(addr) < 250:
            contacts["address"] = addr

    return contacts
