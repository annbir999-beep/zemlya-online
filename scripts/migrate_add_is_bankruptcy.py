"""
Миграция: добавить колонку is_bankruptcy в таблицу lots
и проставить флаг для существующих лотов с признаками банкротства
в title/description.

Запуск на сервере:
  docker compose exec backend python /app/scripts/migrate_add_is_bankruptcy.py

Идемпотентно — повторный запуск безопасен.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import text
from db.database import AsyncSessionLocal, engine


BANKRUPTCY_KEYWORDS = [
    "банкрот",
    "конкурсн",
    "арбитражн",
    "несостоятельн",
    "должник",
    "конкурсное производство",
    "арбитражный управляющий",
    "имущество должника",
]


async def main() -> None:
    async with engine.begin() as conn:
        # 1. Добавить колонку (idempotent)
        await conn.execute(text(
            "ALTER TABLE lots ADD COLUMN IF NOT EXISTS is_bankruptcy BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        # 2. Индекс на банкротные (частичный — только TRUE)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_lots_is_bankruptcy ON lots (is_bankruptcy) WHERE is_bankruptcy = TRUE"
        ))
        # 3. Добавить новое значение в enum lotsource (для bankrot.fedresurs.ru)
        # ALTER TYPE ADD VALUE IF NOT EXISTS — PostgreSQL 9.6+
        await conn.execute(text(
            "ALTER TYPE lotsource ADD VALUE IF NOT EXISTS 'bankrot_fedresurs'"
        ))
        print("[migrate] column + index + enum value ready")

    # 3. Пересчёт: проставить флаг для существующих банкротных лотов
    async with AsyncSessionLocal() as db:
        title_clauses = " OR ".join(f"title ILIKE :kw{i}" for i in range(len(BANKRUPTCY_KEYWORDS)))
        desc_clauses = " OR ".join(f"description ILIKE :dkw{i}" for i in range(len(BANKRUPTCY_KEYWORDS)))
        params = {}
        for i, kw in enumerate(BANKRUPTCY_KEYWORDS):
            params[f"kw{i}"] = f"%{kw}%"
            params[f"dkw{i}"] = f"%{kw}%"

        sql = text(f"""
            UPDATE lots
            SET is_bankruptcy = TRUE
            WHERE is_bankruptcy = FALSE
              AND ({title_clauses} OR {desc_clauses})
        """)
        result = await db.execute(sql, params)
        await db.commit()
        print(f"[migrate] flagged {result.rowcount} existing lots as bankruptcy")

        # Финальная статистика
        stats = await db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE is_bankruptcy = TRUE) AS bankrupt,
                COUNT(*) AS total
            FROM lots
        """))
        row = stats.first()
        print(f"[migrate] total bankrupt lots in DB: {row[0]} / {row[1]}")


if __name__ == "__main__":
    asyncio.run(main())
