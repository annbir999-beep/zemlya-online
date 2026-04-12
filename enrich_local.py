"""
Локальный скрипт обогащения данными Росреестра — запускается с ПК через Task Scheduler.
Подключается к базе данных на Timeweb напрямую.
PKK (pkk.rosreestr.ru) блокирует IP дата-центров, поэтому запускаем с домашнего ПК.
"""
import asyncio
import os
import sys

# Путь к backend
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, BACKEND_DIR)

# Настройки
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sotka:Sotka2026db@72.56.245.67:5432/sotka")

import models  # noqa
from db.database import AsyncSessionLocal
from sqlalchemy import select
from models.lot import Lot
from services.rosreestr import RosreestrClient
from services.rubrics import normalize_vri_to_rubric
from services.scraper_torgi import _calc_area_discrepancy


BATCH_SIZE = 500   # лотов за запуск
DELAY = 0.4        # секунд между запросами к PKK


async def fetch_lot_ids() -> list:
    """Получаем список ID лотов без данных Росреестра."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lot.id, Lot.cadastral_number, Lot.area_sqm, Lot.start_price)
            .where(Lot.cadastral_number.isnot(None), Lot.rosreestr_data.is_(None))
            .limit(BATCH_SIZE)
        )
        return result.all()


async def save_lot_data(lot_id: int, data: dict, area_sqm: float, start_price: float):
    """Сохраняем данные одного лота — короткая сессия."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lot).where(Lot.id == lot_id))
        lot = result.scalar_one_or_none()
        if not lot:
            return

        lot.rosreestr_data = data

        if data.get("lat") and data.get("lng") and not lot.location:
            from geoalchemy2.shape import from_shape
            from shapely.geometry import Point
            lot.location = from_shape(Point(data["lng"], data["lat"]), srid=4326)

        if data.get("cadastral_cost"):
            try:
                lot.cadastral_cost = float(data["cadastral_cost"])
                if start_price and lot.cadastral_cost > 0:
                    lot.pct_price_to_cadastral = round(start_price / lot.cadastral_cost * 100, 2)
            except (ValueError, TypeError):
                pass

        if data.get("area_sqm"):
            try:
                lot.area_sqm_kn = float(data["area_sqm"])
            except (ValueError, TypeError):
                pass

        lot.category_kn = data.get("category", "")[:300] if data.get("category") else None
        lot.vri_kn = data.get("vri", "")[:500] if data.get("vri") else None
        lot.rubric_kn = normalize_vri_to_rubric(data.get("vri", "") or "")
        lot.area_discrepancy = _calc_area_discrepancy(area_sqm, lot.area_sqm_kn)

        await db.commit()


async def mark_failed(lot_id: int):
    """Помечаем лот как обработанный (PKK не нашёл)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Lot).where(Lot.id == lot_id))
        lot = result.scalar_one_or_none()
        if lot:
            lot.rosreestr_data = {}
            await db.commit()


async def run():
    print(f"=== Обогащение данными Росреестра (пакет {BATCH_SIZE}) ===")

    rows = await fetch_lot_ids()
    print(f"Найдено лотов для обогащения: {len(rows)}")

    client = RosreestrClient()
    enriched = 0
    failed = 0

    for i, row in enumerate(rows, 1):
        lot_id, cn_raw, area_sqm, start_price = row
        cn = (cn_raw or "").split(",")[0].split(";")[0].strip()
        if not cn:
            continue

        data = await client.get_cadastral_info(cn)
        await asyncio.sleep(DELAY)

        if data:
            await save_lot_data(lot_id, data, area_sqm, start_price)
            enriched += 1
            if enriched % 50 == 0:
                print(f"  [{i}/{len(rows)}] Обогащено: {enriched}")
        else:
            await mark_failed(lot_id)
            failed += 1

    await client.close()
    print(f"=== Готово: обогащено {enriched}, не найдено в PKK: {failed} ===")


if __name__ == "__main__":
    asyncio.run(run())
