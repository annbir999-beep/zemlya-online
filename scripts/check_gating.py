#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Контроль пейволла: что реально уходит анониму из публичного API.

Зачем: 27.07.2026 выяснилось, что каталог и карта ходили в API без токена —
залогиненный платный пользователь получал анонимный срез данных, а премиум-фильтры
молча не работали. Обратная ошибка не менее опасна: премиум-поле утекает анониму.
Этот скрипт ловит вторую половину — то, что видно снаружи без авторизации.

Матрица «кому что открыто» — docs/gating-matrix.md.
Запуск:  python scripts/check_gating.py [--base https://torgi-zemli.ru]
"""
from __future__ import annotations

import argparse
import sys

import httpx

# Поля, которых у анонима быть НЕ должно (режет api/lots.py::_lot_to_item)
PREMIUM_FIELDS = [
    "discount_to_market_pct",      # Pro+
    "nearest_city_name",           # Pro+
    "nearest_city_distance_km",    # Pro+
    "nearest_city_population",     # Pro+
    "pct_price_to_cadastral",      # Инвестор+
    "market_price_sqm",            # Инвестор+
    "sublease_allowed",            # Инвестор+
    "assignment_allowed",          # Инвестор+
    "tor_zone",                    # Инвестор+
]

# Поля, которые анониму видеть МОЖНО (решение по продукту — витрина ценности)
PUBLIC_FIELDS = ["score", "start_price", "area_sqm", "region_name", "cadastral_cost"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://torgi-zemli.ru")
    args = ap.parse_args()
    base = args.base.rstrip("/")

    failures: list[str] = []
    notes: list[str] = []

    with httpx.Client(timeout=30, follow_redirects=True) as c:
        # 1. Публичный список без токена
        # status=active обязателен: без него API отдаёт и завершённые торги,
        # отсортированные по дате окончания — там скор не считается, и проверка
        # публичных полей ложно краснеет.
        r = c.get(f"{base}/api/lots", params={"per_page": 20, "status": "active"})
        if r.status_code != 200:
            print(f"FAIL: GET /api/lots вернул {r.status_code}")
            return 1
        data = r.json()
        items = data.get("items", [])
        if not items:
            print("FAIL: /api/lots не вернул ни одного лота — проверять нечего")
            return 1
        total_plain = data.get("total")

        # 2. Премиум-поля не должны быть заполнены ни у одного лота
        for field in PREMIUM_FIELDS:
            leaked = [i["id"] for i in items if i.get(field) is not None]
            if leaked:
                failures.append(
                    f"утечка премиум-поля «{field}» анониму — лоты {leaked[:5]}"
                )

        # 3. Публичные поля наоборот должны приходить хотя бы у части лотов
        for field in PUBLIC_FIELDS:
            if not any(i.get(field) is not None for i in items):
                notes.append(f"публичное поле «{field}» пустое у всех 20 лотов — проверь данные")

        # 4. Премиум-фильтр анониму должен игнорироваться (а не фильтровать)
        r2 = c.get(
            f"{base}/api/lots",
            params={"per_page": 1, "status": "active", "score_min": 95},
        )
        total_filtered = r2.json().get("total") if r2.status_code == 200 else None
        if total_filtered is not None and total_filtered != total_plain:
            failures.append(
                f"премиум-фильтр score_min сработал у анонима: "
                f"{total_plain} → {total_filtered} (должно быть без изменений)"
            )

        # 5. Экспорт CSV анониму закрыт
        r3 = c.get(f"{base}/api/lots/export", params={"per_page": 1})
        if r3.status_code == 200:
            failures.append("GET /api/lots/export отдал 200 анониму (должен быть 401/403)")

    print(f"Проверено лотов: {len(items)}, всего в выдаче: {total_plain}")
    for n in notes:
        print(f"  ~ {n}")

    if failures:
        print("\nПРОБЛЕМЫ ГЕЙТИНГА:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1

    print("\nOK: анониму премиум-данные не утекают, премиум-фильтры не работают, экспорт закрыт.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
