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
# Расширено 2026-05-12: были слишком узкие патерны, ловили только 13 из 4024
# распарсенных договоров. Добавлены формулировки ст. 22 ЗК РФ и распространённые
# обороты «передача прав и обязанностей третьим лицам».
CESSION_FORBIDDEN = [
    r"запрещ\w+\s+заключ\w+\s+договор\w*\s+уступк\w+\s+требовани",
    r"запрещ\w+\s+уступк\w+\s+(?:права|требовани)",
    r"уступк\w+\s+(?:права|требовани).{0,30}не\s+(?:допуска\w+|разреш\w+)",
    r"не\s+вправе\s+(?:уступа\w+|передава\w+)\s+(?:свои\s+)?права",
    r"цесси[яи]\s+(?:не\s+допуск|запрещ)",
    r"переуступк\w+\s+(?:не\s+допуск|запрещ|невозможн)",
    # Распространённое: «Арендатор не имеет права передавать свои права»
    r"не\s+имеет\s+права\s+передава\w*\s+(?:свои\s+)?(?:права|обязанност)",
    r"не\s+подлежат\s+передач\w+\s+третьим\s+лицам",
    # Без явных слов «уступка», но смысл запретительный
    r"передача\s+прав.{0,80}не\s+(?:допуска\w*|разреш\w*)",
    r"передача\s+прав\s+и\s+обязанност\w+.{0,80}запрещ\w*",
]
CESSION_ALLOWED_WITH_NOTICE = [
    r"вправе\s+передат\w+\s+свои\s+права\s+и\s+обязанности",
    r"имее\w+\s+право\s+переда\w+\s+(?:свои\s+)?права",
    r"договор\s+перенайм\w+",  # перенайм — это и есть передача прав
    # ст. 22 ЗК РФ: «арендатор вправе ... уведомив собственника»
    r"уведомив\s+(?:об\s+этом\s+)?(?:собственник|арендодател)",
    r"в\s+уведомительн\w+\s+порядк\w+",
    # «без согласия арендодателя» = по умолчанию разрешено
    r"без\s+согласия\s+арендодател.{0,60}(?:передат\w+|уступит\w+|сдат\w+)",
]
CESSION_ALLOWED_WITH_CONSENT = [
    # Только формулировки, прямо привязанные к передаче прав / цессии / субаренде —
    # иначе ловим любое «с согласия арендодателя» из других пунктов договора.
    r"(?:передач|уступк|переуступк|перенайм)\w*.{0,80}с\s+(?:письменн\w+\s+)?(?:согласия|согласовани)\s+Арендодател",
    r"(?:передач|уступк|переуступк|перенайм)\w*.{0,80}при\s+наличии\s+(?:письменн\w+\s+)?согласия",
    r"с\s+(?:письменн\w+\s+)?согласия\s+Арендодател.{0,80}(?:передат\w+|уступит\w+|переуступит\w+)",
]

# ── Субаренда ────────────────────────────────────────────────────────────────
SUBLEASE_FORBIDDEN = [
    r"запрещ\w+\s+(?:передач|сдач)\w+\s+(?:в\s+)?субаренд",
    r"субаренд\w+\s+(?:не\s+допуск|запрещ|не\s+разреш)",
    r"не\s+вправе\s+(?:сдава\w+|передава\w+)\s+участок\s+в\s+субаренд",
    r"не\s+имеет\s+права\s+(?:сдава\w+|передава\w+).{0,30}в\s+субаренд",
    r"не\s+подлежит\s+(?:передач|сдач)\w+\s+в\s+субаренд",
]
SUBLEASE_ALLOWED = [
    r"вправе\s+(?:сдава\w+|передава\w+)\s+(?:участок\s+)?в\s+субаренд",
    r"имее\w+\s+право\s+(?:сдава\w+|передава\w+)\s+в\s+субаренд",
    r"разреш\w+\s+(?:передач|сдач)\w+\s+в\s+субаренд",
    r"без\s+согласия\s+арендодател.{0,60}субаренд",
    r"арендатор\s+вправе.{0,40}субаренд",
]
SUBLEASE_WITH_CONSENT = [
    r"субаренд.{0,80}с\s+(?:письменн\w+\s+)?согласия\s+Арендодател",
    r"субаренд.{0,80}при\s+наличии\s+(?:письменн\w+\s+)?согласия",
    r"с\s+(?:письменн\w+\s+)?согласия\s+арендодател.{0,40}субаренд",
    r"передач\w*\s+в\s+субаренд.{0,40}только\s+с\s+согласия",
]

# ── Срок аренды ──────────────────────────────────────────────────────────────
LEASE_TERM_PATTERNS = [
    r"срок\s+(?:аренды|действия\s+договора)[\s:.,-]+(?:\w+\s+)?(\d{1,3})\s*(?:\([^)]*\)\s*)?(год|года|лет|месяц)",
    r"договор\s+заключ\w+\s+на\s+срок\s+(\d{1,3})\s*(?:\([^)]*\)\s*)?(год|года|лет|месяц)",
    r"срок\w*\s*[:.]\s*(\d{1,3})\s*(год|года|лет|месяц)",
    # Расширено 11.07.2026 — формулировки из lotName/lotDescription карточки
    # («…договора аренды … сроком на 20 лет», «на срок 49 (сорок девять) лет»).
    # Применяется в enrich только к арендным лотам, поэтому «на срок N лет» здесь
    # почти всегда именно срок аренды.
    r"(?:на\s+срок|сроком(?:\s+на)?)\s+(\d{1,3})\s*(?:\([^)]*\)\s*)?(год|года|лет|месяц)",
    r"аренд\w+[^.]{0,40}?\bна\s+(\d{1,3})\s*(?:\([^)]*\)\s*)?(год|года|лет)\b",
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


# ── Срок аренды из структурных атрибутов torgi.gov ────────────────────────────
# Ключевое звено фикса переуступки: срок аренды в карточке ЗК-аукциона лежит
# отдельными ЧИСЛОВЫМИ полями attributes (DA_contractYears / DA_contractMonths /
# DA_contractDays; суффикс кода зависит от формы торгов — матчим по префиксу).
# Regex по PDF ловит срок лишь у ~2.5% лотов, из-за чего эвристика ст.22 голодала;
# структурные поля дают срок у ~63% арендных лотов.
_TERM_ATTR_PREFIXES = {
    "years": "DA_contractYears",
    "months": "DA_contractMonths",
    "days": "DA_contractDays",
}


def extract_lease_term_years(raw: dict) -> Optional[float]:
    """Срок аренды в годах из числовых attributes карточки torgi.gov.

    Складывает годы + месяцы/12 + дни/365. None — если ни одного числового поля
    срока нет (не арендный ЗК-аукцион или срок не заполнен)."""
    if not isinstance(raw, dict):
        return None
    parts = {"years": 0.0, "months": 0.0, "days": 0.0}
    found = False
    for attr in (raw.get("attributes") or []) + (raw.get("noticeAttributes") or []):
        if not isinstance(attr, dict):
            continue
        code = attr.get("code") or ""
        val = attr.get("value")
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        for key, prefix in _TERM_ATTR_PREFIXES.items():
            if code.startswith(prefix):
                parts[key] = float(val)
                found = True
                break
    if not found:
        return None
    total = parts["years"] + parts["months"] / 12 + parts["days"] / 365
    return round(total, 2) if total > 0 else None


# ст. 22 ЗК РФ — переуступка прав и субаренда участка, арендованного у государства:
#   п.9: срок аренды > 5 лет → в уведомительном порядке, БЕЗ согласия арендодателя
#        (если договором прямо не предусмотрено иное);
#   п.5: срок аренды ≤ 5 лет → только с согласия арендодателя.
# Явное условие договора всегда приоритетнее эвристики закона.
ZK_ST22_LONG_TERM_YEARS = 5


def derive_resale_sublease(lease_term_years: Optional[float],
                           contract: Optional[dict]) -> dict:
    """Договор + дефолт ст. 22 ЗК РФ → два чётких флага (без градации).

    Возвращает:
      assignment_allowed / sublease_allowed — переуступка/субаренда:
        True  — ВОЗМОЖНА: свободно (уведомит. порядок ст.22 при сроке >5 лет /
                прямо в договоре) ЛИБО по согласованию с арендодателем (срок ≤5
                лет / договор требует согласия — «можно договориться»);
        False — прямой запрет договора;
        None  — неизвестно (срок и условие не определены);
      resale_basis: источник/режим вывода —
        свободно: "zk_st22_p9" (>5 лет) | "contract_notice";
        по согласованию: "zk_st22_p5" (≤5 лет) | "contract_consent";
        запрет: "contract_forbidden".

    Договор приоритетнее закона. «Свободно» и «по согласованию» ОБА дают флаг
    True (оба — в списки); отличить их можно по resale_basis (см. RESALE_CONSENT_BASES).
    """
    contract = contract or {}
    a = contract.get("assignment")   # forbidden | with_consent | with_notice | None
    s = contract.get("sublease")     # forbidden | with_consent | with_notice | allowed | None
    out = {"assignment_allowed": None, "sublease_allowed": None, "resale_basis": None}
    long_term = lease_term_years is not None and lease_term_years > ZK_ST22_LONG_TERM_YEARS
    short_term = lease_term_years is not None and 0 < lease_term_years <= ZK_ST22_LONG_TERM_YEARS

    # ── Переуступка (цессия права аренды) ──
    if a == "forbidden":
        out.update(assignment_allowed=False, resale_basis="contract_forbidden")
    elif a == "with_notice":
        out.update(assignment_allowed=True, resale_basis="contract_notice")
    elif a == "with_consent":
        out.update(assignment_allowed=True, resale_basis="contract_consent")
    elif long_term:
        out.update(assignment_allowed=True, resale_basis="zk_st22_p9")
    elif short_term:
        out.update(assignment_allowed=True, resale_basis="zk_st22_p5")

    # ── Субаренда ── (симметрично: возможна свободно или по согласованию)
    if s == "forbidden":
        out["sublease_allowed"] = False
    elif s in ("allowed", "with_notice", "with_consent"):
        out["sublease_allowed"] = True
    elif long_term or short_term:
        out["sublease_allowed"] = True

    return out


# Режимы resale_basis, означающие «переуступка/субаренда по согласованию с
# арендодателем» (можно договориться) — в отличие от свободной (уведомительной).
RESALE_CONSENT_BASES = ("zk_st22_p5", "contract_consent")
RESALE_FREE_BASES = ("zk_st22_p9", "contract_notice")


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
