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


async def test_torgi_connection():
    """Тестирует доступность torgi.gov перед основным парсингом."""
    import httpx
    from core.config import settings

    proxy_host = getattr(settings, "PROXY_HOST", None)
    proxy_user = getattr(settings, "PROXY_USER", None)
    proxy_pass = getattr(settings, "PROXY_PASS", None)
    proxy_url = (
        f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}"
        if proxy_host
        else None
    )
    print(f"[test] Прокси: {proxy_host or 'не настроен'}")

    url = "https://torgi.gov.ru/new/public/lots/api/v1/lots"
    params = {"lotStatus": "PUBLISHED", "category": "ZU", "page": 0, "size": 1}
    print(f"[test] Проверяем доступность {url} ...")
    try:
        async with httpx.AsyncClient(timeout=30.0, proxy=proxy_url) as client:
            resp = await client.get(url, params=params)
            print(f"[test] HTTP статус: {resp.status_code}")
            data = resp.json()
            total = data.get("totalElements", "?")
            print(f"[test] Всего лотов на API: {total}")
    except Exception as e:
        print(f"[test] ОШИБКА: {type(e).__name__}: {e}")


async def run():
    # Test connectivity first
    await test_torgi_connection()

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
