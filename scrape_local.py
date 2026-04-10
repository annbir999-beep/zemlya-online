"""
Локальный скрипт парсинга torgi.gov — запускается с ПК через Task Scheduler.
Подключается к базе данных на Timeweb напрямую.
"""
import asyncio
import os
import sys

# Путь к backend
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "backend")
sys.path.insert(0, BACKEND_DIR)

# Настройки
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sotka:Sotka2026db@72.56.245.67:5432/sotka")
os.environ.setdefault("TORGI_GOV_DELAY", "0.5")

import models  # noqa — загружает все модели чтобы SQLAlchemy смог построить связи
from db.database import AsyncSessionLocal, engine, Base
from services.scraper_torgi import TorgiGovScraper


async def run():
    print("=== Запуск парсера torgi.gov ===")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        scraper = TorgiGovScraper(db)
        count = await scraper.run()
        await db.commit()
        print(f"=== Сохранено лотов: {count} ===")


if __name__ == "__main__":
    asyncio.run(run())
