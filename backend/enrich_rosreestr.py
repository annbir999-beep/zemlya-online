"""
Обогащение лотов данными Росреестра (НСПД).
Запускать с домашнего ПК — сервер блокируется nspd.gov.ru.

Подключается напрямую к PostgreSQL на сервере.
Обрабатывает лоты без координат или без данных КН.

Запуск:
    pip install httpx sqlalchemy asyncpg geoalchemy2 shapely
    python enrich_rosreestr.py
"""
import asyncio
import sys
import os

# Подключение через SSH-туннель (см. инструкцию ниже)
DATABASE_URL = "postgresql+asyncpg://sotka:Sotka2026db@localhost:5433/sotka?ssl=disable"

# Задержка между запросами (сек) — не перегружать НСПД
DELAY = 1.0
# Лимит за один запуск
BATCH_SIZE = 500


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, or_, and_

    # Импортируем модели и клиент относительно этого файла
    sys.path.insert(0, os.path.dirname(__file__))
    from models.lot import Lot, LotSource
    from services.rosreestr import RosreestrClient

    engine = create_async_engine(DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    client = RosreestrClient()

    async with Session() as db:
        # Лоты torgi.gov с кадастровым номером, но без данных КН или координат
        q = (
            select(Lot)
            .where(
                Lot.source == LotSource.TORGI_GOV,
                Lot.cadastral_number.isnot(None),
                Lot.cadastral_number != "",
                or_(
                    Lot.location.is_(None),
                    Lot.area_sqm_kn.is_(None),
                    Lot.category_kn.is_(None),
                )
            )
            .limit(BATCH_SIZE)
        )
        lots = (await db.execute(q)).scalars().all()
        print(f"Найдено лотов для обогащения: {len(lots)}")

        updated = 0
        for i, lot in enumerate(lots):
            print(f"[{i+1}/{len(lots)}] {lot.cadastral_number} ...", end=" ")
            try:
                info = await client.get_cadastral_info(lot.cadastral_number)
                if not info:
                    print("нет данных")
                    await asyncio.sleep(DELAY)
                    continue

                changed = False

                if info.get("area_sqm") and not lot.area_sqm_kn:
                    lot.area_sqm_kn = float(info["area_sqm"])
                    changed = True

                if info.get("category") and not lot.category_kn:
                    lot.category_kn = str(info["category"])[:500]
                    changed = True

                if info.get("vri") and not lot.vri_kn:
                    lot.vri_kn = str(info["vri"])[:500]
                    changed = True

                if info.get("cadastral_cost") and not lot.cadastral_cost:
                    try:
                        lot.cadastral_cost = float(info["cadastral_cost"])
                        changed = True
                    except (ValueError, TypeError):
                        pass

                if info.get("address") and not lot.address:
                    lot.address = str(info["address"])[:500]
                    changed = True

                # Координаты
                lat = info.get("lat")
                lng = info.get("lng")
                if lat and lng and not lot.location:
                    try:
                        from geoalchemy2.shape import from_shape
                        from shapely.geometry import Point
                        lot.location = from_shape(Point(lng, lat), srid=4326)
                        changed = True
                    except Exception as e:
                        print(f"(координаты ошибка: {e})", end=" ")

                if changed:
                    db.add(lot)
                    updated += 1
                    print(f"✓ обновлён (lat={lat}, area_kn={info.get('area_sqm')})")
                else:
                    print("без изменений")

                # Коммит каждые 50 лотов
                if updated % 50 == 0 and updated > 0:
                    await db.commit()
                    print(f"  → Промежуточный коммит ({updated} лотов)")

            except Exception as e:
                print(f"ОШИБКА: {e}")

            await asyncio.sleep(DELAY)

        await db.commit()
        print(f"\nГотово. Обновлено: {updated} из {len(lots)} лотов.")

    await client.close()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
