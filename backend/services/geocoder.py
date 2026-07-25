"""
Fallback-геокодирование адреса лота через OpenStreetMap Nominatim.

Зачем: координаты в `Lot.location` ставит только `enrich_with_rosreestr` — по
кадастровому номеру через ПКК. Лоты без КН (почти весь AVITO и часть torgi.gov)
координат не получают вовсе и не видны на карте — покрытие держалось ~6.5%.
Здесь — второй, менее точный источник: прямой геокодинг текстового адреса.

Ограничения Nominatim (публичный инстанс, usage policy):
  - не больше 1 запроса в секунду (паузу держит вызывающая таска);
  - обязателен осмысленный User-Agent с контактом;
  - результат кэшировать на своей стороне (у нас — колонка `geocoded_at`).

Точность заведомо хуже ПКК: адрес земельного участка часто заканчивается на
селе или районе, а не на доме. Поэтому:
  - грубые попадания (страна/регион) отбрасываем по `place_rank`;
  - результат сверяем с `region_name` лота (Nominatim отдаёт `address.state`),
    а если сверить не с чем — с координатами центра субъекта.
Иначе «д. Ивановка» уехала бы в другой конец страны.
"""
import re
from typing import Optional

import httpx

from services.osm_features import haversine_m
from services.region_centers import get_center


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "zemlya-online/1.0 (+https://torgi-zemli.ru; contact@zemlya.online)"

# place_rank Nominatim: страна=4, регион=8, район=12, город=16, село=19,
# улица=26, дом=30. Всё грубее района — это центроид субъекта, на карте он
# выглядит как «лот в чистом поле у областного центра». Такое не сохраняем.
MIN_PLACE_RANK = 12

# Запасная проверка, когда `address.state` сверить не удалось: точка не должна
# быть дальше этого от центра субъекта. Порог грубый — он рассчитан на Якутию
# и Красноярский край (~1500 км от центра до края), а не на точность.
MAX_DISTANCE_FROM_REGION_KM = 1500

# Мусор в адресах torgi.gov/AVITO, который сбивает геокодер: индекс, «участок
# №...», кадастровые номера, «примерно в N м от ориентира» и прочая юридическая
# обвязка описания местоположения.
_NOISE_PATTERNS = [
    r"\b\d{6}\b",                                  # почтовый индекс
    r"\b\d{2}:\d{2}:\d{6,7}:\d+\b",                # кадастровый номер
    r"\bкадастровый\s+номер\b[^,]*",
    r"\b(земельный\s+)?участок\s*(№|N)?\s*[\d/-]*",
    r"\bуч\.?\s*(№|N)?\s*[\d/-]+",
    r"\bпримерно\s+в\s+[\d.,]+\s*(м|км)[^,]*",
    r"\bориентир[^,]*",
    r"\bпочтовый\s+адрес\s+ориентира[^,]*",
    r"\bместоположение\s+установлено[^,]*",
    r"\bрасположен(ный|ного)?\s+за\s+пределами\s+участка[^,]*",
    r"\bкад\.?\s*квартал[^,]*",
]
_NOISE_RE = [re.compile(p, re.IGNORECASE) for p in _NOISE_PATTERNS]

# Типовые обозначения субъекта — режем перед сравнением region_name с
# `address.state`, иначе «Московская область» != «Московская обл.».
_REGION_NOISE_RE = re.compile(
    r"\b(область|обл|край|республика|респ|автономный округ|автономная область|"
    r"ао|округ|город федерального значения|г\.ф\.з)\b\.?",
    re.IGNORECASE,
)


def clean_address(address: str) -> str:
    """Убирает из адреса юридический шум, мешающий геокодеру."""
    s = address or ""
    for rx in _NOISE_RE:
        s = rx.sub(" ", s)
    # схлопываем осиротевшие запятые и пробелы
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"(\s*,\s*)+", ", ", s)
    return s.strip(" ,.-")


def build_query(
    address: Optional[str],
    region_name: Optional[str] = None,
    district: Optional[str] = None,
) -> str:
    """Собирает строку запроса: адрес + район + регион, без дублей.

    Регион и район добавляем, только если их ещё нет в адресе — иначе
    «Тверская обл., Тверская область» роняет релевантность выдачи.
    """
    addr = clean_address(address or "")
    parts = [addr] if addr else []
    haystack = addr.lower()

    for extra in (district, region_name):
        if not extra:
            continue
        key = _REGION_NOISE_RE.sub("", extra).strip().lower()
        # район/регион уже упомянут в адресе (в любой форме сокращения) — пропускаем
        if key and key[:6] in haystack:
            continue
        parts.append(extra.strip())
        haystack = f"{haystack} {extra.lower()}"

    return ", ".join(p for p in parts if p)


def _normalize_region(name: Optional[str]) -> str:
    """«Московская обл.» / «Московская область» → «московская»."""
    if not name:
        return ""
    s = _REGION_NOISE_RE.sub(" ", name)
    s = re.sub(r"[^\w\s-]", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip().lower()


def regions_match(nominatim_state: Optional[str], lot_region: Optional[str]) -> Optional[bool]:
    """True/False — сверка удалась; None — сверить не с чем (нет одной из строк)."""
    a = _normalize_region(nominatim_state)
    b = _normalize_region(lot_region)
    if not a or not b:
        return None
    return a in b or b in a


def _is_acceptable(
    item: dict,
    region_name: Optional[str],
    region_code: Optional[str],
) -> tuple[bool, str]:
    """Проверяет один результат Nominatim. Возвращает (ок, причина отказа)."""
    addr = item.get("address") or {}
    if (addr.get("country_code") or "").lower() != "ru":
        return False, "не Россия"

    try:
        rank = int(item.get("place_rank"))
    except (TypeError, ValueError):
        rank = MIN_PLACE_RANK  # ранга нет — не придираемся, дальше сверим регион
    if rank < MIN_PLACE_RANK:
        return False, f"слишком грубо (place_rank={rank})"

    try:
        lat = float(item["lat"])
        lng = float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return False, "нет координат"

    # Основная сверка — название субъекта из выдачи против region_name лота.
    match = regions_match(addr.get("state") or addr.get("region"), region_name)
    if match is False:
        return False, f"регион не совпал ({addr.get('state')} != {region_name})"

    # Сверить по имени не вышло — страхуемся расстоянием до центра субъекта.
    if match is None:
        center = get_center(region_code)
        if center:
            dist_km = haversine_m(center[0], center[1], lat, lng) / 1000
            if dist_km > MAX_DISTANCE_FROM_REGION_KM:
                return False, f"{dist_km:.0f} км от центра региона"

    return True, ""


async def geocode_lot_address(
    address: Optional[str],
    region_name: Optional[str] = None,
    district: Optional[str] = None,
    region_code: Optional[str] = None,
    proxy_url: Optional[str] = None,
    timeout: int = 20,
) -> Optional[dict]:
    """Геокодирует адрес лота. Возвращает dict или None, если не вышло.

    Результат: {lat, lng, display_name, place_rank, osm_type}.
    None — адрес пустой, Nominatim ничего не нашёл, либо все кандидаты не
    прошли проверку на регион/точность.
    """
    query = build_query(address, region_name, district)
    if len(query) < 8:  # «с. Ивановка» — минимум, ниже которого искать бессмысленно
        return None

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,          # берём несколько — первый кандидат часто грубее
        "countrycodes": "ru",
        "addressdetails": 1,
        "accept-language": "ru",
    }

    async with httpx.AsyncClient(timeout=timeout, proxy=proxy_url) as c:
        r = await c.get(NOMINATIM_URL, params=params, headers={"User-Agent": USER_AGENT})
        if r.status_code != 200:
            raise RuntimeError(f"Nominatim HTTP {r.status_code}")
        items = r.json()

    if not isinstance(items, list):
        return None

    for item in items:
        ok, _reason = _is_acceptable(item, region_name, region_code)
        if not ok:
            continue
        return {
            "lat": float(item["lat"]),
            "lng": float(item["lon"]),
            "display_name": item.get("display_name") or "",
            "place_rank": item.get("place_rank"),
            "osm_type": item.get("osm_type") or "",
        }

    return None
