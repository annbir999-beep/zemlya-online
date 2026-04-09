import anthropic
import json
from datetime import datetime, timezone
from typing import Optional

from core.config import settings


client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

ASSESSMENT_PROMPT = """Ты — эксперт по российскому рынку земельных участков. Проанализируй лот с аукциона и дай инвестиционную оценку.

Данные участка:
{lot_data}

Ответь строго в формате JSON (без markdown, без пояснений вне JSON):
{{
  "score": <целое число от 1 до 10, инвестиционная привлекательность>,
  "price_estimate": {{
    "min": <рублей, нижняя граница рыночной цены>,
    "max": <рублей, верхняя граница>,
    "comment": "<1-2 предложения о методе оценки>"
  }},
  "pros": ["<плюс 1>", "<плюс 2>", "<плюс 3>"],
  "cons": ["<минус 1>", "<минус 2>"],
  "risks": ["<риск 1>", "<риск 2>"],
  "summary": "<3-4 предложения, общий вывод для инвестора>",
  "recommended_use": "<рекомендуемое использование: ИЖС / перепродажа / аренда / сельское хозяйство / коммерция>"
}}"""


def _format_lot_data(lot_dict: dict) -> str:
    lines = []
    field_names = {
        "title": "Название",
        "cadastral_number": "Кадастровый номер",
        "start_price": "Начальная цена",
        "area_sqm": "Площадь (кв.м)",
        "area_ha": "Площадь (га)",
        "land_purpose_raw": "Назначение земли",
        "auction_type": "Тип торгов",
        "region_name": "Регион",
        "address": "Адрес",
        "auction_end_date": "Дата окончания торгов",
        "organizer_name": "Организатор",
        "description": "Описание",
    }
    for key, label in field_names.items():
        value = lot_dict.get(key)
        if value:
            if key == "start_price":
                lines.append(f"{label}: {value:,.0f} руб.")
            elif key == "area_sqm":
                lines.append(f"{label}: {value:,.0f}")
            else:
                lines.append(f"{label}: {value}")

    rosreestr = lot_dict.get("rosreestr_data")
    if rosreestr:
        lines.append(f"Данные Росреестра: {json.dumps(rosreestr, ensure_ascii=False)[:500]}")

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
