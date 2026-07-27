"""Извлечение суммы задатка из текста извещения.

Зачем отдельный парсер: в API torgi.gov суммы задатка НЕТ вообще. В карточке
лота (`/lotcards/{id}`) в атрибутах лежат только текстовые отсылки
(`DA_depositTimeAndRules_EA(ZK)` = «п. 8 Извещения о проведении аукциона»),
а само число — внутри PDF извещения. Старый код читал `data.get("deposit")`,
такого ключа в ответе не существует, поэтому задаток стоял у 5% лотов
(630 из 12 777 на 27.07.2026), хотя слово «задаток» есть в тексте у 6 451.

Разбираем `Lot.full_description` — текст извещения, который уже выкачивает
и складывает `enrich_lot_pdfs`.
"""
from __future__ import annotations

import re
from typing import Optional

# «390 899,00» / «14 700.00» / «1 234 567» — с любыми пробелами-разделителями
_NUM = r"(\d[\d   ]{0,14}(?:[.,]\d{1,2})?)"

# Прямая сумма: «Задаток 390 899,00 (…) рублей», «Сумма задатка: … – 14 700,00 руб.»
_DIRECT = [
    re.compile(rf"задат\w*\s*[:—–-]?\s*(?:в\s+размере\s+)?{_NUM}\s*(?:\(|руб)", re.I),
    re.compile(rf"размер\s+задатка\s*[:—–-]?\s*{_NUM}\s*(?:\(|руб)", re.I),
    # «Сумма задатка: 100 % от начальной цены предмета торгов – 14 700,00 руб.»
    re.compile(rf"задат\w*[^.\n]{{0,80}}?[—–-]\s*{_NUM}\s*руб", re.I),
]

# Процент от начальной цены: «Задаток 20 % от начальной цены»
# ВНИМАНИЕ: основа «задатк» НЕ покрывает именительный падеж «задаток»
# (там между «т» и «к» стоит «о») — нужен именно \w* после «задат».
_PERCENT = re.compile(
    r"задат\w*[^.\n]{0,40}?(\d{1,3}(?:[.,]\d{1,2})?)\s*%\s*от\s+начальн\w*\s+цен",
    re.I,
)


def _to_float(raw: str) -> Optional[float]:
    cleaned = raw.replace(" ", "").replace(" ", "").replace(" ", "")
    # Последняя запятая/точка с 1-2 цифрами после — десятичный разделитель
    cleaned = re.sub(r"[.,](\d{1,2})$", r".\1", cleaned)
    cleaned = re.sub(r"[.,](?=\d{3})", "", cleaned)
    try:
        val = float(cleaned)
    except ValueError:
        return None
    return val if val > 0 else None


def parse_deposit(text: Optional[str], start_price: Optional[float] = None) -> Optional[float]:
    """Сумма задатка в рублях или None.

    start_price нужен для формулировок «задаток N % от начальной цены» и для
    отсева мусора: задаток больше начальной цены — почти наверняка ошибка
    разбора (зацепили саму цену), кроме честного случая «задаток 100%».
    """
    if not text:
        return None

    candidates: list[float] = []

    for rx in _DIRECT:
        m = rx.search(text)
        if m:
            val = _to_float(m.group(1))
            if val:
                candidates.append(val)

    m = _PERCENT.search(text)
    if m and start_price:
        pct = _to_float(m.group(1))
        if pct and 0 < pct <= 100:
            candidates.append(round(start_price * pct / 100, 2))

    if not candidates:
        return None

    # Здравый смысл: задаток не бывает больше начальной цены. Ровно 100% —
    # частый и честный случай, поэтому граница нестрогая, но без запаса:
    # с допуском в 1% пролезали явные промахи (цена 47 000 → «задаток» 47 400).
    if start_price and start_price > 0:
        sane = [c for c in candidates if c <= start_price]
        if sane:
            candidates = sane
        else:
            return None

    # Копеечные значения (< 100 ₽) почти всегда обрывок номера пункта, не сумма
    candidates = [c for c in candidates if c >= 100]
    return candidates[0] if candidates else None
