"""
Scraper script for GitHub Actions.
Connects directly to production DB, no proxy needed.
"""
import asyncio
import os
import sys

# Ensure backend modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from db.database import AsyncSessionLocal, engine, Base
from services.scraper_torgi import TorgiGovScraper


async def run():
    # Create tables if not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        scraper = TorgiGovScraper(db)
        count = await scraper.run()
        await db.commit()
        print(f"Сохранено лотов: {count}")


if __name__ == "__main__":
    asyncio.run(run())
