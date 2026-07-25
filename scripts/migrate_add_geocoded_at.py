"""
Миграция: добавить колонку geocoded_at в таблицу lots.

Отметка «когда по лоту последний раз ходили в Nominatim» для fallback-
геокодирования (tasks.scrape_tasks.geocode_missing_coords). Нужна, чтобы
неудачные попытки не переспрашивались каждый час: заполнено + location IS NULL
= пробовали и не нашли, вернёмся через 30 дней.

Запуск на сервере:
  docker compose exec backend python /app/scripts/migrate_add_geocoded_at.py

Идемпотентно — повторный запуск безопасен.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from db.database import engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text(
            "ALTER TABLE lots ADD COLUMN IF NOT EXISTS geocoded_at TIMESTAMPTZ"
        ))
        # Частичный индекс под выборку таски: активные без координат, которых
        # ещё не пробовали. Полный индекс по geocoded_at не нужен — лотов с
        # координатами большинство, и они в эту выборку не попадают.
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_lots_geocode_pending "
            "ON lots (geocoded_at) WHERE location IS NULL"
        ))
        print("[migrate] lots.geocoded_at + частичный индекс готовы")

        # lower(status::text) — метки enum'а lotstatus в разных инсталляциях
        # заведены то в нижнем регистре (миграция 0001), то в верхнем
        # (Base.metadata.create_all по именам членов LotStatus).
        stats = await conn.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE lower(status::text) = 'active' AND location IS NULL
                                 AND COALESCE(TRIM(address), '') <> '') AS pending,
                COUNT(*) FILTER (WHERE lower(status::text) = 'active' AND location IS NOT NULL) AS with_coords,
                COUNT(*) FILTER (WHERE lower(status::text) = 'active') AS active
            FROM lots
        """))
        row = stats.first()
        print(f"[migrate] активных: {row[2]}, с координатами: {row[1]}, "
              f"в очереди на геокодинг: {row[0]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
