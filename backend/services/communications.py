"""
Парсинг наличия коммуникаций из текста описания/адреса лота.

Возвращает структурированный словарь:
{
    "electricity": True/False/None,  # электричество
    "gas": True/False/None,           # газ
    "water": True/False/None,         # водоснабжение
    "sewage": True/False/None,        # канализация
    "road": "asphalt"/"gravel"/None,  # дорога
    "internet": True/False/None,      # интернет
}
None означает что в тексте упоминания нет (неизвестно).
"""
import re
from typing import Optional


# ── Регулярки для каждого типа коммуникаций ──────────────────────────────────

ELECTRICITY_YES = [
    r"\bэлектр\w*\s*(?:есть|подведен|подвед|имеется)",
    r"подключен\w+\s*к?\s*электр",
    r"электр\w+\s*(?:в наличии|по границе|до участка)",
    r"\bЛЭП\b\s*(?:рядом|по границе|у участка|в наличии)",
    r"свет\s*(?:есть|подведен|подключ)",
    r"возможност\w+\s*подключения\s*(?:к\s*)?электр",
    r"технические условия.*электр",
]
ELECTRICITY_NO = [
    r"электр\w+\s*(?:нет|отсутств)",
    r"без\s*электр",
    r"свет\s*отсутств",
]

GAS_YES = [
    r"\bгаз\w*\s*(?:есть|подведен|подвед|имеется|по границе)",
    r"подключен\w+\s*к?\s*газ",
    r"\bгазифицир",
    r"возможност\w+\s*газификац",
]
GAS_NO = [
    r"газ\w+\s*(?:нет|отсутств)",
    r"без\s*газ",
]

WATER_YES = [
    r"\bвод\w+\s*(?:есть|подведен|центральн|водопровод)",
    r"\bцентральн\w+\s*вод",
    r"\bводопровод",
    r"\bскважин\w+\s*(?:есть|имеется|пробурен)",
    r"\bколодец",
]
WATER_NO = [
    r"\bвод\w+\s*(?:нет|отсутств)",
    r"без\s*водопровод",
    r"без\s*вод",
]

SEWAGE_YES = [
    r"\bканализац\w+\s*(?:есть|центральн|подведен)",
    r"\bцентральн\w+\s*канализац",
    r"\bсептик\b",
    r"\bвыгребн\w+\s*ям",
]
SEWAGE_NO = [
    r"канализац\w+\s*(?:нет|отсутств)",
]

ROAD_ASPHALT = [
    r"\bасфальт\w*",
    r"\bтвёрд\w+\s*покрыт",
    r"\bгрунтовк\w*\s*(?:до|подъезд)",  # not asphalt but accessible
]
ROAD_GRAVEL = [
    r"\bгрунтов\w+\s*дорог",
    r"\bотсыпк\w+",
]
ROAD_NONE = [
    r"\bбездорожь",
    r"подъезд\w*\s*отсутств",
    r"без\s*подъезд",
]

INTERNET_YES = [
    r"\bинтернет\w*",
    r"\bвай.?фай",
    r"\bоптоволокн",
    r"\bGSM\b",
    r"\b4G\b",
]


def _has_match(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def parse_communications(description: Optional[str], title: Optional[str] = None,
                         vri: Optional[str] = None) -> dict:
    """
    Парсит описание лота, возвращает структуру с найденными коммуникациями.
    """
    text_parts = [description or "", title or "", vri or ""]
    text = " ".join(text_parts).lower()

    if not text.strip():
        return {}

    result: dict = {}

    # Электричество
    if _has_match(text, ELECTRICITY_NO):
        result["electricity"] = False
    elif _has_match(text, ELECTRICITY_YES):
        result["electricity"] = True

    # Газ
    if _has_match(text, GAS_NO):
        result["gas"] = False
    elif _has_match(text, GAS_YES):
        result["gas"] = True

    # Вода
    if _has_match(text, WATER_NO):
        result["water"] = False
    elif _has_match(text, WATER_YES):
        result["water"] = True

    # Канализация
    if _has_match(text, SEWAGE_NO):
        result["sewage"] = False
    elif _has_match(text, SEWAGE_YES):
        result["sewage"] = True

    # Дорога
    if _has_match(text, ROAD_NONE):
        result["road"] = "none"
    elif _has_match(text, ROAD_ASPHALT):
        result["road"] = "asphalt"
    elif _has_match(text, ROAD_GRAVEL):
        result["road"] = "gravel"

    # Интернет
    if _has_match(text, INTERNET_YES):
        result["internet"] = True

    return result


def communications_score_bonus(comms: dict) -> int:
    """Бонус к скору лота за наличие коммуникаций (max +10)."""
    if not comms:
        return 0
    bonus = 0
    if comms.get("electricity") is True:
        bonus += 3
    if comms.get("gas") is True:
        bonus += 3
    if comms.get("water") is True:
        bonus += 2
    if comms.get("sewage") is True:
        bonus += 1
    road = comms.get("road")
    if road == "asphalt":
        bonus += 1
    elif road == "none":
        bonus -= 3  # без дороги — серьёзный минус
    if comms.get("internet") is True:
        bonus += 1
    return bonus
