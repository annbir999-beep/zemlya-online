import anthropic
import json
from datetime import datetime, timezone
from typing import Optional

from core.config import settings


_base_url = getattr(settings, "ANTHROPIC_BASE_URL", None)
client = anthropic.AsyncAnthropic(
    api_key=settings.ANTHROPIC_API_KEY,
    base_url=_base_url if _base_url else None,
)

ASSESSMENT_PROMPT = """Ты — эксперт по российскому рынку земельных участков и инвестициям в землю. Проанализируй конкретный лот с аукциона и предложи КОНКРЕТНУЮ стратегию заработка.

Доступные стратегии в РФ (выбери наиболее подходящую под этот лот):
1. Флип — купил с торгов дешевле → продал на ЦИАН/Авито рыночно
2. Аренда → постройка дома → льготный выкуп (ст. 39.20 ЗК — % от КС зависит от региона)
3. Сельхоз: 3 года добросовестной аренды → выкуп без дома (ст. 10 ФЗ-101)
4. Размежевание: купил большой → разделил → продал по частям
5. Коммерция / промка → бизнес или сдача в аренду
6. Огород (13.1) → смена ВРИ через ПЗЗ → стройка → выкуп
7. Удержание: купил → ждёшь рост рынка → продаёшь через 5-10 лет
8. Аренда с переуступкой прав

Данные участка:
{lot_data}

Ответь строго в формате JSON (без markdown, без пояснений вне JSON):
{{
  "score": <целое 1-10, инвестпривлекательность>,
  "best_strategy": "<номер 1-8 + название>",
  "strategy_plan": [
    "<шаг 1: купить за X руб>",
    "<шаг 2: что сделать с участком>",
    "<шаг 3: ...>",
    "<шаг 4: продать или сдать>"
  ],
  "investment_required": <рублей всего на покупку + освоение>,
  "expected_revenue": <рублей через сколько-то лет>,
  "payback_years": <число>,
  "price_estimate": {{
    "min": <рублей, рыночная цена сейчас>,
    "max": <рублей>,
    "comment": "<1-2 предложения о методе оценки>"
  }},
  "pros": ["<плюс 1>", "<плюс 2>", "<плюс 3>"],
  "cons": ["<минус 1>", "<минус 2>"],
  "risks": ["<риск 1>", "<риск 2>"],
  "summary": "<3-4 предложения с конкретными цифрами для инвестора>",
  "recommended_use": "<краткое: ИЖС/перепродажа/аренда/с-х/коммерция>"
}}"""


def _format_lot_data(lot_dict: dict) -> str:
    lines = []
    field_names = {
        "title": "Название",
        "cadastral_number": "Кадастровый номер",
        "start_price": "Начальная цена",
        "deposit": "Задаток",
        "cadastral_cost": "Кадастровая стоимость",
        "pct_price_to_cadastral": "% НЦ/КС",
        "area_sqm": "Площадь (кв.м)",
        "area_ha": "Площадь (га)",
        "land_purpose_raw": "Назначение земли",
        "vri_tg": "ВРИ",
        "category_tg": "Категория",
        "auction_type": "Тип торгов",
        "deal_type": "Вид сделки",
        "resale_type": "Переуступка",
        "region_name": "Регион",
        "address": "Адрес",
        "submission_end": "Срок подачи заявок",
        "organizer_name": "Организатор",
        "description": "Описание",
        # Новые поля
        "score": "Скор рентабельности (наша система, 0-100)",
        "discount_to_market_pct": "Дисконт к рынку (медиана ЦИАН+Авито)",
        "market_price_sqm": "Медианная рыночная цена за м² в регионе",
        "nearest_city_name": "Ближайший город",
        "nearest_city_distance_km": "Расстояние до города (км)",
        "nearest_city_population": "Население города",
    }
    for key, label in field_names.items():
        value = lot_dict.get(key)
        if value is None or value == "":
            continue
        if key in ("start_price", "deposit", "cadastral_cost", "market_price_sqm"):
            lines.append(f"{label}: {value:,.0f} руб.")
        elif key in ("pct_price_to_cadastral", "discount_to_market_pct"):
            lines.append(f"{label}: {value:.1f}%")
        elif key == "area_sqm":
            lines.append(f"{label}: {value:,.0f}")
        else:
            lines.append(f"{label}: {value}")

    # Коммуникации
    comms = lot_dict.get("communications") or {}
    if comms:
        comms_str = []
        if comms.get("electricity") is True: comms_str.append("электричество ✓")
        if comms.get("electricity") is False: comms_str.append("электричество ✗")
        if comms.get("gas") is True: comms_str.append("газ ✓")
        if comms.get("water") is True: comms_str.append("вода ✓")
        if comms.get("road") == "asphalt": comms_str.append("асфальт ✓")
        if comms.get("road") == "none": comms_str.append("нет дороги ✗")
        if comms_str:
            lines.append(f"Коммуникации: {', '.join(comms_str)}")

    # Бейджи
    badges = lot_dict.get("score_badges") or []
    if badges:
        lines.append(f"Авто-бейджи: {', '.join(badges)}")

    rosreestr = lot_dict.get("rosreestr_data")
    if rosreestr:
        lines.append(f"Данные Росреестра: {json.dumps(rosreestr, ensure_ascii=False)[:500]}")

    # Условия проекта договора (из PDF)
    contract = lot_dict.get("contract_terms") or {}
    if contract:
        try:
            from services.contract_parser import format_for_display
            for line in format_for_display(contract):
                lines.append(f"  • {line}")
        except Exception:
            lines.append(f"Условия договора: {json.dumps(contract, ensure_ascii=False)[:300]}")

    # Полное описание из извещения (PDF) — даём первые 2000 символов
    full_desc = lot_dict.get("full_description")
    if full_desc:
        lines.append(f"\nПолное описание (из извещения):\n{full_desc[:2000]}")

    return "\n".join(lines)


async def assess_lot(lot_dict: dict) -> dict:
    """Отправляет данные участка в Claude и возвращает структурированную оценку."""
    lot_data_str = _format_lot_data(lot_dict)
    prompt = ASSESSMENT_PROMPT.format(lot_data=lot_data_str)

    message = await client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Убираем возможный markdown-блок ```json ... ```
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    result = json.loads(raw)
    result["assessed_at"] = datetime.now(timezone.utc).isoformat()
    return result
