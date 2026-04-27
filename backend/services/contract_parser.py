"""
Парсер юридических условий из текста проекта договора аренды/купли-продажи.

Извлекает структурированные данные:
- Цессия / переуступка (запрещена / разрешена / с уведомлением / с согласия)
- Субаренда (запрещена / разрешена / с условиями)
- Срок аренды
- Штрафные санкции
- Срок начала освоения
- Условия расторжения (краткий перечень)

Используется регулярные выражения. Если конкретный пункт не найден — оставляем None
(значит в этом договоре этого условия нет / не нашли).
"""
import re
from typing import Optional


# ── Цессия / переуступка прав требования ──────────────────────────────────────
CESSION_FORBIDDEN = [
    r"запрещ\w+\s+заключ\w+\s+договор\w*\s+уступк\w+\s+требовани",
    r"запрещ\w+\s+уступк\w+\s+(?:права|требовани)",
    r"уступк\w+\s+(?:права|требовани).{0,30}не\s+(?:допуска\w+|разреш\w+)",
    r"не\s+вправе\s+(?:уступа\w+|передава\w+)\s+(?:свои\s+)?права",
    r"цесси[яи]\s+(?:не\s+допуск|запрещ)",
    r"переуступк\w+\s+(?:не\s+допуск|запрещ|невозможн)",
]
CESSION_ALLOWED_WITH_NOTICE = [
    r"вправе\s+передат\w+\s+свои\s+права\s+и\s+обязанности",
    r"имее\w+\s+право\s+переда\w+\s+(?:свои\s+)?права",
    r"договор\s+перенайм\w+",  # перенайм — это и есть передача прав
    r"(?:письменн\w+\s+)?уведомл\w+\s+Арендодател\w+",
]
CESSION_ALLOWED_WITH_CONSENT = [
    r"с\s+(?:письменн\w+\s+)?(?:согласия|согласовани)\s+Арендодател\w+",
    r"(?:по\s+)?предварительн\w+\s+согласован\w+",
    r"при\s+наличии\s+(?:письменн\w+\s+)?согласия",
]

# ── Субаренда ────────────────────────────────────────────────────────────────
SUBLEASE_FORBIDDEN = [
    r"запрещ\w+\s+(?:передач|сдач)\w+\s+(?:в\s+)?субаренд",
    r"субаренд\w+\s+(?:не\s+допуск|запрещ|не\s+разреш)",
    r"не\s+вправе\s+(?:сдава\w+|передава\w+)\s+участок\s+в\s+субаренд",
]
SUBLEASE_ALLOWED = [
    r"вправе\s+(?:сдава\w+|передава\w+)\s+(?:участок\s+)?в\s+субаренд",
    r"имее\w+\s+право\s+(?:сдава\w+|передава\w+)\s+в\s+субаренд",
    r"разреш\w+\s+(?:передач|сдач)\w+\s+в\s+субаренд",
]
SUBLEASE_WITH_CONSENT = [
    r"субаренд.{0,80}с\s+(?:письменн\w+\s+)?согласия\s+Арендодател",
    r"субаренд.{0,80}при\s+наличии\s+согласия",
]

# ── Срок аренды ──────────────────────────────────────────────────────────────
LEASE_TERM_PATTERNS = [
    r"срок\s+(?:аренды|действия\s+договора)[\s:.,-]+(?:\w+\s+)?(\d{1,3})\s*(?:\(.*?\))?\s*(год|лет|месяц)",
    r"договор\s+заключ\w+\s+на\s+срок\s+(\d{1,3})\s*(год|лет|месяц)",
    r"срок\w*\s*[:.]\s*(\d{1,3})\s*(год|лет|месяц)",
]

# ── Штрафы ───────────────────────────────────────────────────────────────────
PENALTY_PATTERNS = [
    r"(?:пен[яи]|штраф\w*)\s+в\s+размере\s+(\d{1,3}(?:[.,]\d{1,3})?)\s*%",
    r"(\d{1,3}(?:[.,]\d{1,3})?)\s*%\s+(?:за\s+каждый\s+день\s+просрочки|годовых)",
]

# ── Срок начала освоения ─────────────────────────────────────────────────────
DEVELOPMENT_DEADLINE = [
    r"приступит\w+\s+к\s+(?:использовани|освоени|строительств)\w+\s+в\s+течени\w+\s+(\d{1,2})\s*(год|лет|месяц)",
    r"срок\s+(?:начала\s+)?(?:освоени|использовани|строительств)\w+[\s:.,-]+(\d{1,2})\s*(год|лет|месяц)",
    r"в\s+течени\w+\s+(\d{1,2})\s*(год|лет|месяц).{0,30}приступит",
]

# ── Расторжение ──────────────────────────────────────────────────────────────
TERMINATION_KEYWORDS = [
    "односторонн", "досрочн", "расторжени", "прекращени",
    "невнесени", "нецелев", "не использу", "ненадлежащ",
]


def _has(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _find_first_int(text: str, patterns: list[str]) -> Optional[int]:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            num = int(m.group(1))
            unit = (m.group(2) or "").lower() if m.lastindex and m.lastindex >= 2 else "год"
            # Нормализуем — если месяцы, преобразуем в годы (округление вниз)
            if "месяц" in unit:
                num = num // 12 if num >= 12 else 0
            return num
        except (ValueError, IndexError):
            continue
    return None


def _find_first_float(text: str, patterns: list[str]) -> Optional[float]:
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            return float(m.group(1).replace(",", "."))
        except (ValueError, IndexError):
            continue
    return None


def parse_contract(text: str) -> dict:
    """
    Парсит текст проекта договора, возвращает структурированный dict.
    """
    if not text or len(text) < 200:
        return {}

    result: dict = {}

    # ── Цессия / переуступка ──
    if _has(text, CESSION_FORBIDDEN):
        result["assignment"] = "forbidden"
    elif _has(text, CESSION_ALLOWED_WITH_CONSENT):
        result["assignment"] = "with_consent"
    elif _has(text, CESSION_ALLOWED_WITH_NOTICE):
        result["assignment"] = "with_notice"

    # ── Субаренда ──
    if _has(text, SUBLEASE_FORBIDDEN):
        result["sublease"] = "forbidden"
    elif _has(text, SUBLEASE_WITH_CONSENT):
        result["sublease"] = "with_consent"
    elif _has(text, SUBLEASE_ALLOWED):
        result["sublease"] = "allowed"

    # ── Срок аренды (в годах) ──
    term_years = _find_first_int(text, LEASE_TERM_PATTERNS)
    if term_years and 1 <= term_years <= 99:
        result["lease_term_years"] = term_years

    # ── Штрафы (% за день просрочки или годовых) ──
    penalty = _find_first_float(text, PENALTY_PATTERNS)
    if penalty and 0 < penalty <= 50:
        result["penalty_pct"] = penalty

    # ── Срок начала освоения ──
    dev_term = _find_first_int(text, DEVELOPMENT_DEADLINE)
    if dev_term and 0 <= dev_term <= 20:
        result["development_deadline_years"] = dev_term

    # ── Условия расторжения (количество упоминаний) ──
    termination_count = sum(1 for kw in TERMINATION_KEYWORDS if kw in text.lower())
    if termination_count >= 2:
        result["has_strict_termination"] = True

    return result


# ── Текстовое представление для AI/UI ────────────────────────────────────────
ASSIGNMENT_LABELS = {
    "forbidden": "Цессия запрещена",
    "with_notice": "Можно с уведомлением арендодателя",
    "with_consent": "Только с письменным согласием арендодателя",
    "allowed": "Цессия разрешена без условий",
}
SUBLEASE_LABELS = {
    "forbidden": "Субаренда запрещена",
    "with_consent": "Субаренда — только с согласия арендодателя",
    "allowed": "Субаренда разрешена",
}


def format_for_display(contract: dict) -> list[str]:
    """Превращает структурированный dict в список строк для отображения в UI."""
    lines = []
    if a := contract.get("assignment"):
        lines.append(f"Переуступка/цессия: {ASSIGNMENT_LABELS.get(a, a)}")
    if s := contract.get("sublease"):
        lines.append(f"Субаренда: {SUBLEASE_LABELS.get(s, s)}")
    if t := contract.get("lease_term_years"):
        lines.append(f"Срок аренды: {t} лет")
    if p := contract.get("penalty_pct"):
        lines.append(f"Штрафные пени: {p}% (за день просрочки)")
    if d := contract.get("development_deadline_years"):
        lines.append(f"Начать освоение в течение: {d} лет с момента договора")
    if contract.get("has_strict_termination"):
        lines.append("⚠️ В договоре строгие условия расторжения за нарушения")
    return lines
