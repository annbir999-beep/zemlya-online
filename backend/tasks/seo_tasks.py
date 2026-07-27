"""IndexNow: ежедневная отправка URL региональных SEO-страниц и статей блога.

Даёт Яндексу/Bing сигнал переобойти новые/изменённые страницы за часы, а не
недели. Список URL пересобирается с нуля каждый прогон (дёшево — считаем то
же самое, что sitemap.ts), IndexNow сам игнорирует уже проиндексированные
без изменений.
"""
import asyncio

from worker import celery_app


@celery_app.task
def ping_indexnow():
    asyncio.run(_ping_indexnow())


async def _ping_indexnow():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from core.config import settings
    from services.indexnow import submit_urls
    from api.seo import _region_rows, region_slug
    from models.content import ContentPost

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    SITE = settings.SITE_URL

    async with SessionLocal() as db:
        region_rows = await _region_rows(db)
        posts = (await db.execute(
            select(ContentPost.slug).where(ContentPost.status == "published")
        )).scalars().all()

    await engine.dispose()

    urls = [f"{SITE}/", f"{SITE}/zemelnye-torgi", f"{SITE}/blog"]
    urls += [f"{SITE}/zemelnye-torgi/{region_slug(r.region_name)}" for r in region_rows]
    urls += [f"{SITE}/blog/{slug}" for slug in posts]

    ok = await submit_urls(urls)
    print(f"[indexnow] {'OK' if ok else 'FAILED'} — {len(urls)} URL отправлено")
