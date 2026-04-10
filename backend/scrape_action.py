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

    proxy_host = getattr(settings, "PROXY_HOST", None) or ""
    proxy_user = getattr(settings, "PROXY_USER", None) or ""
    proxy_pass = getattr(settings, "PROXY_PASS", None) or ""

    url = "https://torgi.gov.ru/new/public/lots/api/v1/lots"
    params = {"lotStatus": "PUBLISHED", "category": "ZU", "page": 0, "size": 1}

    # Сначала пробуем без прокси (GitHub Actions может иметь доступ напрямую)
    print(f"[test] Попытка 1: без прокси ...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, params=params)
            print(f"[test] Без прокси — HTTP статус: {resp.status_code}")
            data = resp.json()
            print(f"[test] Всего лотов: {data.get('totalElements', '?')}")
            return  # Успех — дальше не идём
    except Exception as e:
        print(f"[test] Без прокси — ОШИБКА: {type(e).__name__}: {e}")

    # Пробуем через SOCKS5
    if proxy_host:
        proxy_url = f"socks5://{proxy_user}:{proxy_pass}@{proxy_host}"
        print(f"[test] Попытка 2: через SOCKS5 прокси {proxy_host} ...")
        try:
            async with httpx.AsyncClient(timeout=60.0, proxy=proxy_url) as client:
                resp = await client.get(url, params=params)
                print(f"[test] Через SOCKS5 — HTTP статус: {resp.status_code}")
                data = resp.json()
                print(f"[test] Всего лотов: {data.get('totalElements', '?')}")
                return
        except Exception as e:
            print(f"[test] Через SOCKS5 — ОШИБКА: {type(e).__name__}: {e}")

        # Пробуем через HTTPS прокси
        proxy_url_https = f"http://{proxy_user}:{proxy_pass}@{proxy_host}"
        print(f"[test] Попытка 3: через HTTPS прокси {proxy_host} ...")
        try:
            async with httpx.AsyncClient(timeout=60.0, proxy=proxy_url_https) as client:
                resp = await client.get(url, params=params)
                print(f"[test] Через HTTPS — HTTP статус: {resp.status_code}")
                data = resp.json()
                print(f"[test] Всего лотов: {data.get('totalElements', '?')}")
                return
        except Exception as e:
            print(f"[test] Через HTTPS — ОШИБКА: {type(e).__name__}: {e}")

    print("[test] Все попытки неудачны.")


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
