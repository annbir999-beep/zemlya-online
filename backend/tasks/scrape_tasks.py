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
    from services.pdf_parser import select_best_attachments, download_file, extract_text, truncate_for_db
    from services.contact_extractor import extract_contacts
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
                        att = selected["notice"]
                        b = await download_file(scraper.client, att.get("fileId"))
                        notice_text = extract_text(b, att.get("fileName", "")) if b else ""
                    if "tech_conditions" in selected:
                        att = selected["tech_conditions"]
                        b = await download_file(scraper.client, att.get("fileId"))
                        tech_text = extract_text(b, att.get("fileName", "")) if b else ""
                    if "contract" in selected:
                        att = selected["contract"]
                        b = await download_file(scraper.client, att.get("fileId"))
                        contract_text = extract_text(b, att.get("fileName", "")) if b else ""

                    changed = False

                    # Сохраняем извещение как полное описание
                    full_desc_combined = (det.get("lot_description_full") or "") + "\n\n" + notice_text
                    full_desc_combined = full_desc_combined.strip()
                    if full_desc_combined and not lot.full_description:
                        lot.full_description = truncate_for_db(full_desc_combined)
                        changed = True
                    # Контакты организатора — извлекаем из любых текстовых частей
                    contacts_source = "\n".join(filter(None, [notice_text, tech_text, contract_text]))
                    if contacts_source:
                        contacts = extract_contacts(contacts_source)
                        if contacts and not lot.organizer_contacts:
                            lot.organizer_contacts = contacts
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


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def enrich_organizer_from_notice(self, batch_size: int = 200):
    """Дёргает noticeSignedData (JSON-извещение) и складывает в Lot:
    точное название организатора + структурированные контакты.
    Идёт по лотам с пустым organizer_contacts ИЛИ пустым organizer_name.
    """
    try:
        _run(_enrich_organizer_from_notice(batch_size))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _enrich_organizer_from_notice(batch_size: int):
    import asyncio as _asyncio
    from sqlalchemy import select, or_, and_
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.lot import Lot, LotStatus, LotSource
    from services.scraper_torgi import TorgiGovScraper
    from services.notice_json import parse_notice_json

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        scraper = TorgiGovScraper(db)
        try:
            # JSON-извещение надёжнее regex-эвристик из PDF, поэтому переобогащаем
            # ВСЕ ACTIVE-лоты, у которых ещё нет ИНН в organizer_contacts
            # (регекс ИНН не вытаскивает в большинстве случаев — это маркер).
            from sqlalchemy import text as _text
            result = await db.execute(
                select(Lot)
                .where(
                    and_(
                        Lot.source == LotSource.TORGI_GOV,
                        Lot.status == LotStatus.ACTIVE,
                        or_(
                            Lot.organizer_contacts.is_(None),
                            _text("(organizer_contacts->>'inn') IS NULL"),
                            Lot.organizer_name.is_(None),
                            Lot.organizer_name == "",
                        ),
                    )
                )
                .order_by(Lot.score.desc().nulls_last())
                .limit(batch_size)
            )
            lots = result.scalars().all()

            updated = 0
            for i, lot in enumerate(lots, 1):
                # external_id = "torgi_<id>" — отрезаем префикс
                eid = (lot.external_id or "").removeprefix("torgi_")
                if not eid:
                    continue
                try:
                    # Детальный запрос — оттуда возьмём fileId
                    det = await scraper.client.get(
                        f"https://torgi.gov.ru/new/api/public/lotcards/{eid}"
                    )
                    det.raise_for_status()
                    nsd = (det.json().get("noticeSignedData") or {})
                    fid = nsd.get("fileId")
                    if not fid:
                        continue
                    fr = await scraper.client.get(
                        f"https://torgi.gov.ru/new/file-store/v1/{fid}"
                    )
                    if fr.status_code != 200:
                        continue
                    parsed = parse_notice_json(fr.content)
                    if not parsed:
                        continue
                    name = parsed.get("organizer_name")
                    contacts = parsed.get("contacts") or {}
                    if name and not lot.organizer_name:
                        lot.organizer_name = name[:500]
                    if contacts:
                        # Полная замена: JSON надёжнее regex-эвристик из PDF
                        lot.organizer_contacts = contacts
                        updated += 1
                except Exception as e:
                    print(f"[notice-json] lot={lot.id} error: {type(e).__name__}: {e}")

                if i % 25 == 0:
                    await db.commit()
                    print(f"[notice-json] {i}/{len(lots)} обработано, обогащено: {updated}")
                await _asyncio.sleep(0.4)
            await db.commit()
            print(f"[notice-json] Готово. Обогащено: {updated}/{len(lots)}")
        finally:
            await scraper.client.aclose()
    await engine.dispose()


@celery_app.task
def extract_contacts_from_existing(batch_size: int = 500):
    """Одноразовая задача — пройтись по лотам с full_description, но без
    organizer_contacts, и извлечь контакты регексами. Запускать вручную."""
    _run(_extract_contacts_existing(batch_size))


async def _extract_contacts_existing(batch_size: int):
    from sqlalchemy import select, and_
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from core.config import settings
    from models.lot import Lot
    from services.contact_extractor import extract_contacts

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        result = await db.execute(
            select(Lot)
            .where(
                and_(
                    Lot.full_description.isnot(None),
                    Lot.organizer_contacts.is_(None),
                )
            )
            .limit(batch_size)
        )
        lots = result.scalars().all()
        updated = 0
        for lot in lots:
            text_blob = "\n".join(filter(None, [lot.full_description, lot.technical_conditions]))
            contacts = extract_contacts(text_blob)
            if contacts:
                lot.organizer_contacts = contacts
                updated += 1
        await db.commit()
        print(f"[contacts] обработано {len(lots)}, найдены контакты у {updated}")

    await engine.dispose()


@celery_app.task(bind=True, max_retries=1, default_retry_delay=600)
def enrich_nearby_features(self, batch_size: int = 100):
    """Обогащает лоты данными из OSM Overpass API: водоёмы / лес / трассы / н.п. / ж/д."""
    try:
        _run(_enrich_nearby_features(batch_size))
    except Exception as exc:
        raise self.retry(exc=exc)


async def _enrich_nearby_features(batch_size: int):
    """Берёт лоты с координатами и без nearby_features (или старше 30 дней),
    дёргает OSM Overpass и сохраняет признаки + расстояния.

    Координаты лежат в Geography column `location` (PostGIS POINT) — берём
    через ST_Y/ST_X (lat = Y, lng = X в SRID 4326).
    """
    import asyncio as _asyncio
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, or_, and_, func
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from core.config import settings
    from models.lot import Lot, LotStatus
    from services.osm_features import fetch_nearby_features

    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=0)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    async with SessionLocal() as db:
        # Берём id, lat, lng (через ST_Y/ST_X) — модель Lot не имеет атрибутов lat/lng
        result = await db.execute(
            select(
                Lot.id,
                func.ST_Y(Lot.location).label("lat"),
                func.ST_X(Lot.location).label("lng"),
            )
            .where(
                and_(
                    Lot.status == LotStatus.ACTIVE,
                    Lot.location.isnot(None),
                    or_(Lot.nearby_features_at.is_(None), Lot.nearby_features_at < cutoff),
                )
            )
            .order_by(Lot.score.desc().nulls_last())
            .limit(batch_size)
        )
        rows = result.all()

        updated = 0
        for i, r in enumerate(rows, 1):
            try:
                features = await fetch_nearby_features(r.lat, r.lng)
                # Обновляем через UPDATE — у нас нет полного объекта Lot
                from sqlalchemy import update
                await db.execute(
                    update(Lot)
                    .where(Lot.id == r.id)
                    .values(
                        nearby_features=features or {},
                        nearby_features_at=datetime.now(timezone.utc),
                    )
                )
                if features:
                    updated += 1
                if i % 20 == 0:
                    await db.commit()
                    print(f"[nearby] {i}/{len(rows)} обработано, найдено: {updated}")
            except Exception as e:
                print(f"[nearby] lot={r.id} error: {type(e).__name__}: {e}")
            # Уважаем лимит Overpass — пауза между запросами
            await _asyncio.sleep(2.5)

        await db.commit()
        print(f"[nearby] Готово. Обогащено: {updated}/{len(rows)}")

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
    """Закрываем только лоты не виденные на torgi.gov больше 14 дней (исчезли из поиска).
    Для активных лотов статус ставит сам скрапер из API torgi.gov на каждом прогоне."""
    from db.database import AsyncSessionLocal
    from sqlalchemy import update
    from models.lot import Lot, LotStatus, LotSource
    from datetime import datetime, timezone, timedelta

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=14)
    async with AsyncSessionLocal() as db:
        # Лот пропал из выдачи torgi.gov более 14 дней назад → закрыт
        r1 = await db.execute(
            update(Lot)
            .where(
                Lot.source == LotSource.TORGI_GOV,
                Lot.status == LotStatus.ACTIVE,
                Lot.updated_at < cutoff,
            )
            .values(status=LotStatus.COMPLETED)
        )
        r2_rowcount = 0  # не пытаемся переводить из UPCOMING — это делает API
        await db.commit()
        print(f"[statuses] закрыто 'забытых' (>14д без обновления): {r1.rowcount}")
