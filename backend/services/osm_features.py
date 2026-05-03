"""
Поиск природных и инфраструктурных объектов рядом с участком через
OpenStreetMap Overpass API. Бесплатно, без ключа, лимит ~10k запросов/день.

Что ищем в радиусе 3 км от точки лота:
  - water    — озеро / пруд / река / море (natural=water + waterway=*)
  - forest   — лес (landuse=forest, natural=wood)
  - highway  — крупная трасса (motorway/trunk/primary)
  - settlement — ближайший н.п. (place=town/village/hamlet)
  - railway  — ж/д станция (railway=station/halt)

Возвращаем расстояние от точки лота до ближайшего объекта каждого типа
(в метрах) + название/тип. Если объект дальше radius_m — в результате нет.
"""
import math
from typing import Optional

import httpx


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",  # fallback
]
DEFAULT_RADIUS_M = 3000  # 3 км


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """Расстояние между двумя точками в метрах (формула гаверсинуса)."""
    R = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)


def _build_query(lat: float, lng: float, radius_m: int) -> str:
    """Один Overpass-запрос на все интересующие типы. Возвращает center-точки."""
    around = f"around:{radius_m},{lat},{lng}"
    return f"""
[out:json][timeout:25];
(
  node["natural"="water"]({around});
  way["natural"="water"]({around});
  way["waterway"~"^(river|stream|canal)$"]({around});
  way["landuse"="forest"]({around});
  way["natural"="wood"]({around});
  way["highway"~"^(motorway|trunk|primary)$"]({around});
  node["place"~"^(city|town|village|hamlet)$"]({around});
  node["railway"~"^(station|halt)$"]({around});
);
out tags center 200;
"""


def _classify_water(tags: dict) -> tuple[str, str]:
    """Возвращает (kind, label) для водного объекта."""
    name = tags.get("name") or ""
    if tags.get("natural") == "water":
        wt = tags.get("water") or ""
        if wt == "lake":
            return ("lake", name or "Озеро")
        if wt == "pond":
            return ("pond", name or "Пруд")
        if wt == "reservoir":
            return ("reservoir", name or "Водохранилище")
        if wt == "river":
            return ("river", name or "Река")
        return ("water", name or "Водоём")
    if tags.get("waterway") == "river":
        return ("river", name or "Река")
    if tags.get("waterway") == "stream":
        return ("stream", name or "Ручей")
    if tags.get("waterway") == "canal":
        return ("canal", name or "Канал")
    return ("water", name or "Водоём")


async def fetch_nearby_features(
    lat: float,
    lng: float,
    radius_m: int = DEFAULT_RADIUS_M,
    proxy_url: Optional[str] = None,
) -> dict:
    """Возвращает {water, forest, highway, settlement, railway} с расстояниями.
    Каждый ключ может отсутствовать — значит в радиусе ничего не нашлось.
    """
    query = _build_query(lat, lng, radius_m)

    last_err = None
    data = None
    async with httpx.AsyncClient(timeout=40, proxy=proxy_url) as c:
        for url in OVERPASS_URLS:
            try:
                r = await c.post(url, data=query.encode("utf-8"), headers={
                    "User-Agent": "zemlya-online/1.0 (+contact@zemlya.online)",
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                if r.status_code == 200:
                    data = r.json()
                    break
                last_err = f"HTTP {r.status_code} from {url}"
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                continue

    if data is None:
        raise RuntimeError(f"Overpass unavailable: {last_err}")

    # Разбираем элементы
    nearest = {}
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        # У nodes координаты в self, у ways — в .center
        if el["type"] == "node":
            elat, elng = el.get("lat"), el.get("lon")
        else:
            ctr = el.get("center") or {}
            elat, elng = ctr.get("lat"), ctr.get("lon")
        if elat is None or elng is None:
            continue
        dist = haversine_m(lat, lng, elat, elng)

        # Вода
        if tags.get("natural") == "water" or tags.get("waterway") in ("river", "stream", "canal"):
            kind, name = _classify_water(tags)
            cur = nearest.get("water")
            if not cur or dist < cur["distance_m"]:
                nearest["water"] = {"name": name, "kind": kind, "distance_m": dist}
            continue

        # Лес
        if tags.get("landuse") == "forest" or tags.get("natural") == "wood":
            cur = nearest.get("forest")
            if not cur or dist < cur["distance_m"]:
                nearest["forest"] = {"distance_m": dist}
            continue

        # Магистраль
        if tags.get("highway") in ("motorway", "trunk", "primary"):
            cur = nearest.get("highway")
            if not cur or dist < cur["distance_m"]:
                nearest["highway"] = {
                    "kind": tags.get("highway"),
                    "ref": tags.get("ref") or "",
                    "distance_m": dist,
                }
            continue

        # Населённый пункт
        if tags.get("place") in ("city", "town", "village", "hamlet"):
            cur = nearest.get("settlement")
            if not cur or dist < cur["distance_m"]:
                nearest["settlement"] = {
                    "name": tags.get("name") or "",
                    "kind": tags.get("place"),
                    "distance_m": dist,
                }
            continue

        # Ж/д
        if tags.get("railway") in ("station", "halt"):
            cur = nearest.get("railway")
            if not cur or dist < cur["distance_m"]:
                nearest["railway"] = {
                    "name": tags.get("name") or ("Платформа" if tags.get("railway") == "halt" else "Станция"),
                    "distance_m": dist,
                }

    return nearest


# ── Утилиты для вывода в UI ─────────────────────────────────────────────────

WATER_EMOJI = {
    "lake": "🌊", "pond": "🌊", "reservoir": "🌊", "river": "🏞", "stream": "💧", "canal": "💧",
    "water": "🌊",
}


def format_features(features: dict) -> list[str]:
    """Список коротких подписей для UI (карточка лота)."""
    if not features:
        return []
    out = []

    w = features.get("water")
    if w:
        emoji = WATER_EMOJI.get(w.get("kind"), "🌊")
        d = w.get("distance_m", 0)
        d_str = f"{d} м" if d < 1000 else f"{d/1000:.1f} км"
        name = w.get("name") or "водоём"
        out.append(f"{emoji} {name} — {d_str}")

    f = features.get("forest")
    if f:
        d = f.get("distance_m", 0)
        d_str = f"{d} м" if d < 1000 else f"{d/1000:.1f} км"
        out.append(f"🌲 Лес — {d_str}")

    s = features.get("settlement")
    if s:
        d = s.get("distance_m", 0)
        if d < 100:
            out.append(f"🏘 {s.get('name') or 'Посёлок'} (внутри)")
        else:
            d_str = f"{d} м" if d < 1000 else f"{d/1000:.1f} км"
            out.append(f"🏘 {s.get('name') or 'Посёлок'} — {d_str}")

    h = features.get("highway")
    if h:
        d = h.get("distance_m", 0)
        d_str = f"{d} м" if d < 1000 else f"{d/1000:.1f} км"
        ref = h.get("ref") or h.get("kind", "трасса")
        out.append(f"🛣 {ref} — {d_str}")

    r = features.get("railway")
    if r:
        d = r.get("distance_m", 0)
        d_str = f"{d} м" if d < 1000 else f"{d/1000:.1f} км"
        out.append(f"🚆 {r.get('name')} — {d_str}")

    return out
