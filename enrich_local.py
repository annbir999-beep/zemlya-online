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


async def run():
    print(f"=== Обогащение данными Росреестра (пакет {BATCH_SIZE}) ===")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Lot)
            .where(Lot.cadastral_number.isnot(None), Lot.rosreestr_data.is_(None))
            .limit(BATCH_SIZE)
        )
        lots = result.scalars().all()
        print(f"Найдено лотов для обогащения: {len(lots)}")

        client = RosreestrClient()
        enriched = 0
        failed = 0

        for i, lot in enumerate(lots, 1):
            cn_raw = lot.cadastral_number or ""
            cn = cn_raw.split(",")[0].split(";")[0].strip()
            if not cn:
                continue

            data = await client.get_cadastral_info(cn)
            await asyncio.sleep(DELAY)

            if data:
                lot.rosreestr_data = data

                # Координаты
                if not lot.location and data.get("lat") and data.get("lng"):
                    from geoalchemy2.shape import from_shape
                    from shapely.geometry import Point
                    lot.location = from_shape(Point(data["lng"], data["lat"]), srid=4326)

                # Кадастровая стоимость
                if data.get("cadastral_cost"):
                    try:
                        lot.cadastral_cost = float(data["cadastral_cost"])
                        if lot.start_price and lot.cadastral_cost > 0:
                            lot.pct_price_to_cadastral = round(lot.start_price / lot.cadastral_cost * 100, 2)
                    except (ValueError, TypeError):
                        pass

                # Площадь [КН]
                if data.get("area_sqm"):
                    try:
                        lot.area_sqm_kn = float(data["area_sqm"])
                    except (ValueError, TypeError):
                        pass

                lot.category_kn = data.get("category", "")[:300] if data.get("category") else None
                lot.vri_kn = data.get("vri", "")[:500] if data.get("vri") else None
                lot.rubric_kn = normalize_vri_to_rubric(data.get("vri", "") or "")
                lot.area_discrepancy = _calc_area_discrepancy(lot.area_sqm, lot.area_sqm_kn)

                enriched += 1
                if enriched % 50 == 0:
                    await db.commit()
                    print(f"  [{i}/{len(lots)}] Обогащено: {enriched}")
            else:
                lot.rosreestr_data = {}  # помечаем — не повторять
                failed += 1

        await db.commit()
        await client.close()
        print(f"=== Готово: обогащено {enriched}, не найдено в PKK: {failed} ===")


if __name__ == "__main__":
    asyncio.run(run())
