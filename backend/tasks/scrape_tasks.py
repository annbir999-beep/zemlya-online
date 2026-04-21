import asyncio
from worker import celery_app
from services.scraper_torgi import TorgiGovScraper
from services.scraper_avito import AvitoScraper
from services.scraper_cian import CianScraper
from services.scraper_domclick import DomclickScraper
from services.rosreestr import RosreestrClient


def _run(coro):
    """Каждая задача получает свежий event loop — избегаем 'attached to a different loop'."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def scrape_torgi_gov(self):
    """Основной парсинг torgi.gov — земельные аукционы"""
    try:
        _run(_scrape_torgi())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _scrape_torgi():
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        scraper = TorgiGovScraper(db)
        saved = await scraper.run()
        print(f"[torgi.gov] Сохранено/обновлено лотов: {saved}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def scrape_avito(self, region_codes: list = None, pages_per_region: int = 3):
    """Парсинг Авито — земельные участки для сравнения рыночных цен"""
    try:
        _run(_scrape_avito(region_codes, pages_per_region))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _scrape_avito(region_codes: list = None, pages_per_region: int = 3):
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        scraper = AvitoScraper(db)
        saved = await scraper.run(region_codes=region_codes, pages_per_region=pages_per_region)
        print(f"[avito] Сохранено/обновлено лотов: {saved}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def enrich_with_rosreestr(self):
    """Обогащаем участки данными из Росреестра (кадастровые данные)"""
    try:
        _run(_enrich_rosreestr())
    except Exception as exc:
        raise self.retry(exc=exc)


async def _enrich_rosreestr():
    import asyncio
    from db.database import AsyncSessionLocal
    from sqlalchemy import select
    from models.lot import Lot

    async with AsyncSessionLocal() as db:
        # Берём лоты без данных Росреестра с кадастровым номером
        result = await db.execute(
            select(Lot)
            .where(Lot.cadastral_number.isnot(None), Lot.rosreestr_data.is_(None))
            .limit(500)
        )
        lots = result.scalars().all()
        client = RosreestrClient()
        enriched = 0
        failed = 0
        for lot in lots:
            # Берём первый кадастровый номер (может быть несколько через запятую/пробел)
            cn_raw = lot.cadastral_number or ""
            cn = cn_raw.split(",")[0].split(";")[0].strip()
            if not cn:
                continue

            data = await client.get_cadastral_info(cn)
            await asyncio.sleep(0.35)  # не перегружаем PKK

            if data:
                from services.rubrics import normalize_vri_to_rubric
                from models.lot import AreaDiscrepancy

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

                # [КН] поля
                if data.get("area_sqm"):
                    try:
                        lot.area_sqm_kn = float(data["area_sqm"])
                    except (ValueError, TypeError):
                        pass

                lot.category_kn = str(data["category"])[:300] if data.get("category") is not None else None
                lot.vri_kn = str(data["vri"])[:500] if data.get("vri") is not None else None
                lot.rubric_kn = normalize_vri_to_rubric(data.get("vri", "") or "")

                # Расхождение площади TG vs КН
                from services.scraper_torgi import _calc_area_discrepancy
                lot.area_discrepancy = _calc_area_discrepancy(lot.area_sqm, lot.area_sqm_kn)

                enriched += 1
            else:
                # Помечаем что запрашивали (пустой dict) — не будем повторять
                lot.rosreestr_data = {}
                failed += 1

        await db.commit()
        print(f"[Росреестр] Обогащено: {enriched}, не найдено в PKK: {failed}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def scrape_cian(self, region_codes: list = None, pages_per_region: int = 3):
    """Парсинг ЦИАН — земельные участки для сравнения рыночных цен"""
    try:
        _run(_scrape_cian(region_codes, pages_per_region))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _scrape_cian(region_codes: list = None, pages_per_region: int = 3):
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        scraper = CianScraper(db)
        saved = await scraper.run(region_codes=region_codes, pages_per_region=pages_per_region)
        print(f"[cian] Сохранено/обновлено лотов: {saved}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=600)
def scrape_domclick(self, region_codes: list = None, pages_per_region: int = 3):
    """Парсинг Домклик — земельные участки для сравнения рыночных цен"""
    try:
        _run(_scrape_domclick(region_codes, pages_per_region))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _scrape_domclick(region_codes: list = None, pages_per_region: int = 3):
    from db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        scraper = DomclickScraper(db)
        saved = await scraper.run(region_codes=region_codes, pages_per_region=pages_per_region)
        print(f"[domclick] Сохранено/обновлено лотов: {saved}")


@celery_app.task
def update_lot_statuses():
    """Переводим завершённые аукционы в статус completed"""
    _run(_update_statuses())


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def enrich_torgi_details(self, batch_size: int = 300):
    """Подтягиваем дату проведения торгов из детального API torgi.gov."""
    try:
        _run(_enrich_torgi_details(batch_size))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _enrich_torgi_details(batch_size: int):
    import asyncio as _asyncio
    from db.database import AsyncSessionLocal
    from sqlalchemy import select
    from models.lot import Lot, LotSource, LotStatus

    async with AsyncSessionLocal() as db:
        q = (
            select(Lot)
            .where(
                Lot.source == LotSource.TORGI_GOV,
                Lot.auction_start_date.is_(None),
                Lot.status.in_([LotStatus.ACTIVE, LotStatus.UPCOMING]),
            )
            .limit(batch_size)
        )
        lots = (await db.execute(q)).scalars().all()
        if not lots:
            print("[torgi-details] Нет лотов для обогащения")
            return

        scraper = TorgiGovScraper(db)
        updated = 0
        try:
            for i, lot in enumerate(lots, 1):
                torgi_id = lot.external_id.removeprefix("torgi_") if lot.external_id else None
                if not torgi_id:
                    continue
                try:
                    dt = await scraper.fetch_auction_date(torgi_id)
                    if dt:
                        lot.auction_start_date = dt
                        lot.auction_end_date = dt
                        db.add(lot)
                        updated += 1
                except Exception as e:
                    print(f"[torgi-details] {torgi_id}: {type(e).__name__}")
                if i % 50 == 0:
                    await db.commit()
                    print(f"[torgi-details] {i}/{len(lots)} обработано, обновлено: {updated}")
                await _asyncio.sleep(1.0)
            await db.commit()
            print(f"[torgi-details] Готово. Обновлено: {updated}/{len(lots)}")
        finally:
            await scraper.client.aclose()


async def _update_statuses():
    from db.database import AsyncSessionLocal
    from sqlalchemy import update
    from models.lot import Lot, LotStatus
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        r1 = await db.execute(
            update(Lot)
            .where(
                Lot.status.in_([LotStatus.ACTIVE, LotStatus.UPCOMING]),
                Lot.submission_end.isnot(None),
                Lot.submission_end < now,
            )
            .values(status=LotStatus.COMPLETED)
        )
        r2 = await db.execute(
            update(Lot)
            .where(
                Lot.status == LotStatus.UPCOMING,
                Lot.submission_start.isnot(None),
                Lot.submission_start <= now,
                (Lot.submission_end.is_(None)) | (Lot.submission_end >= now),
            )
            .values(status=LotStatus.ACTIVE)
        )
        await db.commit()
        print(f"[statuses] → COMPLETED: {r1.rowcount}, → ACTIVE: {r2.rowcount}")
