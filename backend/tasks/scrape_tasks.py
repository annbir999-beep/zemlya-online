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
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.config import settings
    from models.lot import Lot

    # Свежий engine на каждый вызов — иначе asyncpg-соединения из предыдущего
    # event loop ломают Celery worker.
    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        # Лоты с кадастром без кадастровой стоимости или без координат
        result = await db.execute(
            select(Lot)
            .where(
                Lot.cadastral_number.isnot(None),
                Lot.cadastral_number != "",
                (Lot.cadastral_cost.is_(None)) | (Lot.location.is_(None)),
            )
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

    await client.close()
    await engine.dispose()


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


@celery_app.task
def update_lot_scores():
    """Пересчёт скора рентабельности для всех активных лотов."""
    _run(_update_scores())


@celery_app.task
def update_lot_geo_and_comms():
    """Расчёт ближайшего города и парсинг коммуникаций для всех лотов."""
    _run(_update_geo_comms())


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def enrich_lot_pdfs(self, batch_size: int = 100):
    """Скачивание PDF-документов лотов + извлечение текста + парсинг условий договора."""
    try:
        _run(_enrich_lot_pdfs(batch_size))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _enrich_lot_pdfs(batch_size: int):
    import asyncio as _asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.config import settings
    from models.lot import Lot, LotSource, LotStatus
    from services.scraper_torgi import TorgiGovScraper
    from services.pdf_parser import select_best_attachments, download_pdf, extract_text_from_pdf, truncate_for_db
    from services.contract_parser import parse_contract
    from services.communications import parse_communications

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        q = (
            select(Lot)
            .where(
                Lot.source == LotSource.TORGI_GOV,
                Lot.status.in_([LotStatus.ACTIVE, LotStatus.UPCOMING]),
                Lot.pdf_parsed_at.is_(None),
            )
            .limit(batch_size)
        )
        lots = (await db.execute(q)).scalars().all()
        if not lots:
            print("[pdf] Нет лотов для парсинга")
            return

        scraper = TorgiGovScraper(db)
        updated = 0
        try:
            for i, lot in enumerate(lots, 1):
                torgi_id = lot.external_id.removeprefix("torgi_") if lot.external_id else None
                if not torgi_id:
                    continue
                try:
                    det = await scraper.fetch_lot_details(torgi_id)
                    if not det:
                        continue
                    attachments = det.get("attachments") or []
                    selected = select_best_attachments(attachments)
                    if not selected:
                        # Помечаем что обработали (нет PDF — не пытаться больше)
                        lot.pdf_parsed_at = datetime.now(timezone.utc)
                        db.add(lot)
                        continue

                    # Скачиваем и извлекаем текст по типам
                    notice_text = ""
                    tech_text = ""
                    contract_text = ""

                    if "notice" in selected:
                        b = await download_pdf(scraper.client, selected["notice"].get("fileId"))
                        notice_text = extract_text_from_pdf(b) if b else ""
                    if "tech_conditions" in selected:
                        b = await download_pdf(scraper.client, selected["tech_conditions"].get("fileId"))
                        tech_text = extract_text_from_pdf(b) if b else ""
                    if "contract" in selected:
                        b = await download_pdf(scraper.client, selected["contract"].get("fileId"))
                        contract_text = extract_text_from_pdf(b) if b else ""

                    changed = False

                    # Сохраняем извещение как полное описание
                    full_desc_combined = (det.get("lot_description_full") or "") + "\n\n" + notice_text
                    full_desc_combined = full_desc_combined.strip()
                    if full_desc_combined and not lot.full_description:
                        lot.full_description = truncate_for_db(full_desc_combined)
                        changed = True
                    if tech_text and not lot.technical_conditions:
                        lot.technical_conditions = truncate_for_db(tech_text)
                        changed = True
                    if contract_text:
                        terms = parse_contract(contract_text)
                        if terms:
                            lot.contract_terms = terms
                            # Если в договоре нашли явные правила — обновляем поля лота
                            if terms.get("assignment") == "forbidden":
                                lot.assignment_allowed = False
                            elif terms.get("assignment") in ("with_notice", "with_consent", "allowed"):
                                lot.assignment_allowed = True
                            if terms.get("sublease") == "forbidden":
                                lot.sublease_allowed = False
                            elif terms.get("sublease") in ("with_consent", "allowed"):
                                lot.sublease_allowed = True
                            changed = True

                    # Парсим коммуникации из всех текстов вместе
                    combined_for_comms = " ".join([notice_text, tech_text, lot.description or ""])
                    comms = parse_communications(combined_for_comms, lot.title, lot.vri_tg)
                    if comms:
                        existing = lot.communications or {}
                        merged = {**existing, **comms}
                        lot.communications = merged
                        changed = True

                    lot.pdf_parsed_at = datetime.now(timezone.utc)
                    db.add(lot)
                    if changed:
                        updated += 1
                except Exception as e:
                    print(f"[pdf] {torgi_id}: {type(e).__name__}: {str(e)[:80]}")
                if i % 20 == 0:
                    await db.commit()
                    print(f"[pdf] {i}/{len(lots)} обработано, обогащено: {updated}")
                await _asyncio.sleep(1.5)
            await db.commit()
            print(f"[pdf] Готово. Обогащено: {updated}/{len(lots)}")
        finally:
            await scraper.client.aclose()

    await engine.dispose()


async def _update_geo_comms():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.config import settings
    from models.lot import Lot, LotSource
    from services.cities import find_nearest_city
    from services.communications import parse_communications

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        q = select(Lot).where(Lot.source == LotSource.TORGI_GOV)
        lots = (await db.execute(q)).scalars().all()
        from shapely import wkb
        updated_geo = 0
        updated_comms = 0
        for lot in lots:
            # Геолокация → ближайший город
            if lot.location and not lot.nearest_city_name:
                try:
                    point = wkb.loads(bytes(lot.location.data))
                    city = find_nearest_city(point.y, point.x, lot.region_code)
                    if city:
                        lot.nearest_city_name = city["name"]
                        lot.nearest_city_distance_km = city["distance_km"]
                        lot.nearest_city_population = city["population"]
                        updated_geo += 1
                except Exception:
                    pass

            # Коммуникации из описания
            if not lot.communications:
                comms = parse_communications(lot.description, lot.title, lot.vri_tg)
                if comms:
                    lot.communications = comms
                    updated_comms += 1
            db.add(lot)

        await db.commit()
        print(f"[geo-comms] Города: {updated_geo}, коммуникации: {updated_comms}")

    await engine.dispose()


async def _update_scores():
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.config import settings
    from models.lot import Lot, LotSource, LotStatus
    from services.scoring import compute_market_medians, compute_score_and_badges

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        medians = await compute_market_medians(db)
        print(f"[scoring] Медиан по (region, purpose): {len(medians)}")

        # Скорим только торги.гов (на ЦИАН/Авито нет смысла — это сами эталоны)
        q = select(Lot).where(
            Lot.source == LotSource.TORGI_GOV,
            Lot.status.in_([LotStatus.ACTIVE, LotStatus.UPCOMING]),
        )
        lots = (await db.execute(q)).scalars().all()
        now = datetime.now(timezone.utc)

        updated = 0
        for lot in lots:
            market_psqm = medians.get((lot.region_code, lot.land_purpose))
            score, badges, discount = compute_score_and_badges(lot, market_psqm)
            lot.score = score
            lot.market_price_sqm = market_psqm
            lot.discount_to_market_pct = discount
            lot.score_badges = badges
            lot.score_updated_at = now
            db.add(lot)
            updated += 1

        await db.commit()
        print(f"[scoring] Обновлено лотов: {updated}")

    await engine.dispose()


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

    from sqlalchemy import or_
    async with AsyncSessionLocal() as db:
        q = (
            select(Lot)
            .where(
                Lot.source == LotSource.TORGI_GOV,
                Lot.status.in_([LotStatus.ACTIVE, LotStatus.UPCOMING]),
                or_(
                    Lot.auction_start_date.is_(None),
                    Lot.deposit.is_(None),
                    Lot.start_price.is_(None),
                ),
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
                    det = await scraper.fetch_lot_details(torgi_id)
                    if det:
                        changed = False
                        dt = det.get("auction_start_date")
                        if dt and not lot.auction_start_date:
                            lot.auction_start_date = dt
                            lot.auction_end_date = dt
                            changed = True
                        if det.get("deposit") is not None and not lot.deposit:
                            lot.deposit = det["deposit"]
                            changed = True
                        if det.get("price_min") is not None and not lot.start_price:
                            lot.start_price = det["price_min"]
                            changed = True
                        if det.get("address") and not lot.address:
                            lot.address = det["address"]
                            changed = True
                        # Пересчёт задатка в процентах
                        if lot.deposit and lot.start_price and not lot.deposit_pct:
                            lot.deposit_pct = round(lot.deposit / lot.start_price * 100, 2)
                            changed = True
                        if changed:
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
