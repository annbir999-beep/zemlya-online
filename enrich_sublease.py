"""
Обогащение существующих лотов полями sublease_allowed / assignment_allowed.
Анализирует сохранённый raw_data — не делает запросов к API.
Запускать: python enrich_sublease.py
"""
import asyncio
from sqlalchemy import update, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from models.lot import Lot

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/sotka"
)

SUBLEASE_KEYWORDS = ["субаренд"]
ASSIGNMENT_KEYWORDS = ["переуступ", "уступк", "цессия", "третьим лицам"]


def detect(raw: dict, title: str, description: str) -> tuple:
    texts = [title or "", description or "", raw.get("lotDescription", "") or ""]
    for attr in (raw.get("noticeAttributes") or []) + (raw.get("attributes") or []):
        val = attr.get("value") or attr.get("characteristicValue") or ""
        if isinstance(val, str):
            texts.append(val)
        texts.append(attr.get("fullName", "") or "")
    combined = " ".join(texts).lower()
    sublease = any(kw in combined for kw in SUBLEASE_KEYWORDS)
    assignment = any(kw in combined for kw in ASSIGNMENT_KEYWORDS)
    return sublease, assignment


async def run():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    updated = 0
    batch_size = 500
    offset = 0

    async with async_session() as session:
        while True:
            q = select(Lot.id, Lot.title, Lot.description, Lot.raw_data).offset(offset).limit(batch_size)
            rows = (await session.execute(q)).all()
            if not rows:
                break

            for row in rows:
                raw = row.raw_data or {}
                sublease, assignment = detect(raw, row.title or "", row.description or "")
                sub_val = sublease if (sublease or assignment) else None
                ass_val = assignment if (sublease or assignment) else None
                await session.execute(
                    update(Lot).where(Lot.id == row.id).values(
                        sublease_allowed=sub_val,
                        assignment_allowed=ass_val,
                    )
                )
                if sublease or assignment:
                    updated += 1

            await session.commit()
            offset += batch_size
            print(f"Обработано: {offset}, найдено: {updated}")

    await engine.dispose()
    print(f"\nГотово. Лотов с упоминаниями: {updated}")


if __name__ == "__main__":
    asyncio.run(run())
