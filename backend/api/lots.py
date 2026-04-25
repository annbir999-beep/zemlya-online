from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, case
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
import math

from db.database import get_db
from models.lot import Lot, LotStatus, LandPurpose, AuctionType, LotSource, AuctionForm, DealType, AreaDiscrepancy, ResaleType
from services.rubrics import get_all_rubrics, get_rubrics_by_section, get_sections

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class LotListItem(BaseModel):
    id: int
    external_id: str
    title: Optional[str]
    cadastral_number: Optional[str]
    notice_number: Optional[str]
    start_price: Optional[float]
    cadastral_cost: Optional[float]
    pct_price_to_cadastral: Optional[float]
    deposit: Optional[float]
    deposit_pct: Optional[float]
    area_sqm: Optional[float]
    area_ha: Optional[float]
    area_sqm_kn: Optional[float]
    area_discrepancy: Optional[str]
    land_purpose: Optional[str]
    rubric_tg: Optional[int]
    rubric_kn: Optional[int]
    vri_tg: Optional[str]
    vri_kn: Optional[str]
    category_tg: Optional[str]
    category_kn: Optional[str]
    auction_type: Optional[str]
    auction_form: Optional[str]
    deal_type: Optional[str]
    etp: Optional[str]
    resale_type: Optional[str]
    sublease_allowed: Optional[bool]
    assignment_allowed: Optional[bool]
    status: str
    region_code: Optional[str]
    region_name: Optional[str]
    address: Optional[str]
    auction_end_date: Optional[str]
    submission_start: Optional[str]
    submission_end: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    source: str
    lot_url: Optional[str]
    # Скоринг
    score: Optional[int] = None
    market_price_sqm: Optional[float] = None
    discount_to_market_pct: Optional[float] = None
    score_badges: Optional[List[str]] = None

    class Config:
        from_attributes = True


class LotDetail(LotListItem):
    description: Optional[str]
    final_price: Optional[float]
    price_per_sqm: Optional[float]
    organizer_name: Optional[str]
    auction_start_date: Optional[str]
    rosreestr_data: Optional[dict]
    ai_assessment: Optional[dict]


class LotsResponse(BaseModel):
    items: List[LotListItem]
    total: int
    page: int
    pages: int


# ── Filter builder ────────────────────────────────────────────────────────────

def build_filters(
    status: Optional[str] = None,
    region_codes: Optional[List[str]] = None,
    # Цена
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    # Кадастровая стоимость
    cadastral_cost_min: Optional[float] = None,
    cadastral_cost_max: Optional[float] = None,
    # % НЦ / КС
    pct_cadastral_min: Optional[float] = None,
    pct_cadastral_max: Optional[float] = None,
    # Задаток руб
    deposit_min: Optional[float] = None,
    deposit_max: Optional[float] = None,
    # Задаток %
    deposit_pct_min: Optional[float] = None,
    deposit_pct_max: Optional[float] = None,
    # Площадь [TG]
    area_min: Optional[float] = None,
    area_max: Optional[float] = None,
    # Площадь [КН]
    area_kn_min: Optional[float] = None,
    area_kn_max: Optional[float] = None,
    # Расхождение площади
    area_discrepancy: Optional[str] = None,
    # Назначение
    land_purposes: Optional[List[str]] = None,
    # Рубрики [TG]
    rubric_tg: Optional[List[int]] = None,
    # Рубрики [КН]
    rubric_kn: Optional[List[int]] = None,
    # Тип/форма/вид
    auction_types: Optional[List[str]] = None,
    auction_forms: Optional[List[str]] = None,
    deal_types: Optional[List[str]] = None,
    category_tg: Optional[List[str]] = None,
    vri_tg: Optional[List[str]] = None,
    section_tg: Optional[List[str]] = None,
    # ЭТП
    etp: Optional[List[str]] = None,
    # Переуступка
    resale_types: Optional[List[str]] = None,
    # Субаренда / переуступка (из текста)
    sublease_allowed: Optional[bool] = None,
    assignment_allowed: Optional[bool] = None,
    # Прочее
    sources: Optional[List[str]] = None,
    cadastral: Optional[str] = None,
    notice_number: Optional[str] = None,
    # Даты подачи заявок
    submission_start_from: Optional[date] = None,
    submission_start_to: Optional[date] = None,
    submission_end_from: Optional[date] = None,
    submission_end_to: Optional[date] = None,
    # Геопоиск
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: Optional[float] = None,
    # Наличие координат
    has_coords: Optional[List[str]] = None,
) -> list:
    conditions = []

    if status:
        conditions.append(Lot.status == status)
    if region_codes:
        conditions.append(Lot.region_code.in_(region_codes))

    # Цена
    if price_min is not None:
        conditions.append(Lot.start_price >= price_min)
    if price_max is not None:
        conditions.append(Lot.start_price <= price_max)

    # Кадастровая стоимость
    if cadastral_cost_min is not None:
        conditions.append(Lot.cadastral_cost >= cadastral_cost_min)
    if cadastral_cost_max is not None:
        conditions.append(Lot.cadastral_cost <= cadastral_cost_max)

    # % НЦ/КС
    if pct_cadastral_min is not None:
        conditions.append(Lot.pct_price_to_cadastral >= pct_cadastral_min)
    if pct_cadastral_max is not None:
        conditions.append(Lot.pct_price_to_cadastral <= pct_cadastral_max)

    # Задаток руб
    if deposit_min is not None:
        conditions.append(Lot.deposit >= deposit_min)
    if deposit_max is not None:
        conditions.append(Lot.deposit <= deposit_max)

    # Задаток %
    if deposit_pct_min is not None:
        conditions.append(Lot.deposit_pct >= deposit_pct_min)
    if deposit_pct_max is not None:
        conditions.append(Lot.deposit_pct <= deposit_pct_max)

    # Площадь [TG]
    if area_min is not None:
        conditions.append(Lot.area_sqm >= area_min)
    if area_max is not None:
        conditions.append(Lot.area_sqm <= area_max)

    # Площадь [КН]
    if area_kn_min is not None:
        conditions.append(Lot.area_sqm_kn >= area_kn_min)
    if area_kn_max is not None:
        conditions.append(Lot.area_sqm_kn <= area_kn_max)

    # Расхождение площади
    if area_discrepancy:
        conditions.append(Lot.area_discrepancy == area_discrepancy)

    # Назначение
    if land_purposes:
        conditions.append(Lot.land_purpose.in_(land_purposes))

    # Рубрики [TG]
    if rubric_tg:
        conditions.append(Lot.rubric_tg.in_(rubric_tg))

    # Рубрики [КН]
    if rubric_kn:
        conditions.append(Lot.rubric_kn.in_(rubric_kn))

    # Тип/форма/вид торгов
    if auction_types:
        conditions.append(Lot.auction_type.in_(auction_types))
    if auction_forms:
        conditions.append(Lot.auction_form.in_(auction_forms))
    if deal_types:
        conditions.append(Lot.deal_type.in_(deal_types))
    if category_tg:
        conditions.append(Lot.category_tg.in_(category_tg))
    if vri_tg:
        conditions.append(Lot.vri_tg.in_(vri_tg))
    if section_tg:
        conditions.append(Lot.section_tg.in_(section_tg))

    # ЭТП
    if etp:
        conditions.append(Lot.etp.in_(etp))

    # Переуступка
    if resale_types:
        conditions.append(Lot.resale_type.in_(resale_types))

    # Субаренда / переуступка из текста
    if sublease_allowed is not None:
        conditions.append(Lot.sublease_allowed == sublease_allowed)
    if assignment_allowed is not None:
        conditions.append(Lot.assignment_allowed == assignment_allowed)

    # Источник
    if sources:
        conditions.append(Lot.source.in_(sources))

    # Кадастровый номер
    if cadastral:
        conditions.append(Lot.cadastral_number.ilike(f"%{cadastral}%"))

    # Номер извещения
    if notice_number:
        conditions.append(Lot.notice_number.ilike(f"%{notice_number}%"))

    # Даты подачи заявок
    if submission_start_from:
        conditions.append(Lot.submission_start >= submission_start_from)
    if submission_start_to:
        conditions.append(Lot.submission_start <= submission_start_to)
    if submission_end_from:
        conditions.append(Lot.submission_end >= submission_end_from)
    if submission_end_to:
        conditions.append(Lot.submission_end <= submission_end_to)

    # Геопоиск
    if lat is not None and lng is not None and radius_km is not None:
        point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
        conditions.append(ST_DWithin(Lot.location, point, radius_km * 1000))

    # Наличие координат
    if has_coords:
        if "with_coords" in has_coords and "no_coords" not in has_coords:
            conditions.append(Lot.location.isnot(None))
        elif "no_coords" in has_coords and "with_coords" not in has_coords:
            conditions.append(Lot.location.is_(None))

    return conditions


def _lot_to_item(lot: Lot) -> LotListItem:
    lat_val = lng_val = None
    if lot.location:
        try:
            from shapely import wkb
            point = wkb.loads(bytes(lot.location.data))
            lat_val = point.y
            lng_val = point.x
        except Exception:
            pass

    return LotListItem(
        id=lot.id,
        external_id=lot.external_id,
        title=lot.title,
        cadastral_number=lot.cadastral_number,
        notice_number=lot.notice_number,
        start_price=lot.start_price,
        cadastral_cost=lot.cadastral_cost,
        pct_price_to_cadastral=lot.pct_price_to_cadastral,
        deposit=lot.deposit,
        deposit_pct=lot.deposit_pct,
        area_sqm=lot.area_sqm,
        area_ha=lot.area_ha,
        area_sqm_kn=lot.area_sqm_kn,
        area_discrepancy=lot.area_discrepancy.value if lot.area_discrepancy else None,
        land_purpose=lot.land_purpose.value if lot.land_purpose else None,
        rubric_tg=lot.rubric_tg,
        rubric_kn=lot.rubric_kn,
        vri_tg=lot.vri_tg,
        vri_kn=lot.vri_kn,
        category_tg=lot.category_tg,
        category_kn=lot.category_kn,
        auction_type=lot.auction_type.value if lot.auction_type else None,
        auction_form=lot.auction_form.value if lot.auction_form else None,
        deal_type=lot.deal_type.value if lot.deal_type else None,
        etp=lot.etp,
        resale_type=lot.resale_type.value if lot.resale_type else None,
        sublease_allowed=lot.sublease_allowed,
        assignment_allowed=lot.assignment_allowed,
        status=lot.status.value,
        region_code=lot.region_code,
        region_name=lot.region_name,
        address=lot.address,
        auction_end_date=lot.auction_end_date.isoformat() if lot.auction_end_date else None,
        submission_start=lot.submission_start.isoformat() if lot.submission_start else None,
        submission_end=lot.submission_end.isoformat() if lot.submission_end else None,
        lat=lat_val,
        lng=lng_val,
        source=lot.source.value,
        lot_url=lot.lot_url,
        score=lot.score,
        market_price_sqm=lot.market_price_sqm,
        discount_to_market_pct=lot.discount_to_market_pct,
        score_badges=lot.score_badges if isinstance(lot.score_badges, list) else None,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=LotsResponse)
async def get_lots(
    # Статус
    status: Optional[str] = Query(None),
    # Регион
    region: Optional[List[str]] = Query(None, alias="region"),
    # Цена
    price_min: Optional[float] = Query(None, ge=0),
    price_max: Optional[float] = Query(None, ge=0),
    # Кадастровая стоимость
    cadastral_cost_min: Optional[float] = Query(None, ge=0),
    cadastral_cost_max: Optional[float] = Query(None, ge=0),
    # % НЦ / КС
    pct_cadastral_min: Optional[float] = Query(None, ge=0),
    pct_cadastral_max: Optional[float] = Query(None, ge=0),
    # Задаток
    deposit_min: Optional[float] = Query(None, ge=0),
    deposit_max: Optional[float] = Query(None, ge=0),
    deposit_pct_min: Optional[float] = Query(None, ge=0),
    deposit_pct_max: Optional[float] = Query(None, ge=0),
    # Площадь [TG]
    area_min: Optional[float] = Query(None, ge=0),
    area_max: Optional[float] = Query(None, ge=0),
    # Площадь [КН]
    area_kn_min: Optional[float] = Query(None, ge=0),
    area_kn_max: Optional[float] = Query(None, ge=0),
    # Расхождение площади
    area_discrepancy: Optional[str] = Query(None),
    # Назначение
    purpose: Optional[List[str]] = Query(None, alias="purpose"),
    # Рубрики
    rubric_tg: Optional[List[int]] = Query(None, alias="rubric_tg"),
    rubric_kn: Optional[List[int]] = Query(None, alias="rubric_kn"),
    # Тип/форма/вид
    auction_type: Optional[List[str]] = Query(None, alias="auction_type"),
    auction_form: Optional[List[str]] = Query(None, alias="auction_form"),
    deal_type: Optional[List[str]] = Query(None, alias="deal_type"),
    category_tg: Optional[List[str]] = Query(None, alias="category_tg"),
    vri_tg: Optional[List[str]] = Query(None, alias="vri_tg"),
    section_tg: Optional[List[str]] = Query(None, alias="section_tg"),
    # ЭТП
    etp: Optional[List[str]] = Query(None, alias="etp"),
    # Переуступка
    resale_type: Optional[List[str]] = Query(None, alias="resale_type"),
    # Субаренда / переуступка из текста
    sublease_allowed: Optional[bool] = Query(None),
    assignment_allowed: Optional[bool] = Query(None),
    # Источник
    source: Optional[List[str]] = Query(None, alias="source"),
    # Поиск
    cadastral: Optional[str] = Query(None),
    notice_number: Optional[str] = Query(None),
    # Даты подачи заявок
    submission_start_from: Optional[date] = Query(None),
    submission_start_to: Optional[date] = Query(None),
    submission_end_from: Optional[date] = Query(None),
    submission_end_to: Optional[date] = Query(None),
    # Геопоиск
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_km: Optional[float] = Query(None, le=500),
    has_coords: Optional[List[str]] = Query(None, alias="has_coords"),
    # Сортировка
    sort_by: str = Query("auction_end_date"),
    sort_order: str = Query("asc"),
    # Пагинация
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    conditions = build_filters(
        status=status, region_codes=region,
        price_min=price_min, price_max=price_max,
        cadastral_cost_min=cadastral_cost_min, cadastral_cost_max=cadastral_cost_max,
        pct_cadastral_min=pct_cadastral_min, pct_cadastral_max=pct_cadastral_max,
        deposit_min=deposit_min, deposit_max=deposit_max,
        deposit_pct_min=deposit_pct_min, deposit_pct_max=deposit_pct_max,
        area_min=area_min, area_max=area_max,
        area_kn_min=area_kn_min, area_kn_max=area_kn_max,
        area_discrepancy=area_discrepancy,
        land_purposes=purpose, rubric_tg=rubric_tg, rubric_kn=rubric_kn,
        auction_types=auction_type, auction_forms=auction_form, deal_types=deal_type,
        category_tg=category_tg, vri_tg=vri_tg, section_tg=section_tg,
        etp=etp, resale_types=resale_type,
        sublease_allowed=sublease_allowed, assignment_allowed=assignment_allowed,
        sources=source if source else ["torgi_gov"], cadastral=cadastral, notice_number=notice_number,
        submission_start_from=submission_start_from, submission_start_to=submission_start_to,
        submission_end_from=submission_end_from, submission_end_to=submission_end_to,
        lat=lat, lng=lng, radius_km=radius_km,
        has_coords=has_coords,
    )

    sort_columns = {
        "price": Lot.start_price,
        "area": Lot.area_sqm,
        "auction_end_date": Lot.auction_end_date,
        "published_at": Lot.published_at,
        "pct_cadastral": Lot.pct_price_to_cadastral,
        "deposit_pct": Lot.deposit_pct,
        "submission_end": Lot.submission_end,
        "score": Lot.score,
        "discount_to_market": Lot.discount_to_market_pct,
    }
    if sort_by == "resale_priority":
        # Приоритет: yes=1, with_notice=2, with_approval=3, no=4, NULL=5
        order_expr = case(
            (Lot.resale_type == "yes", 1),
            (Lot.resale_type == "with_notice", 2),
            (Lot.resale_type == "with_approval", 3),
            (Lot.resale_type == "no", 4),
            else_=5,
        ).asc()
    else:
        sort_col = sort_columns.get(sort_by, Lot.auction_end_date)
        order_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    count_q = select(func.count()).select_from(Lot).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar()

    offset = (page - 1) * per_page
    q = select(Lot).where(and_(*conditions)).order_by(order_expr).offset(offset).limit(per_page)
    lots = (await db.execute(q)).scalars().all()

    return LotsResponse(
        items=[_lot_to_item(l) for l in lots],
        total=total,
        page=page,
        pages=math.ceil(total / per_page) if total else 0,
    )


@router.get("/map")
async def get_lots_for_map(
    status: Optional[str] = Query("active"),
    region: Optional[List[str]] = Query(None, alias="region"),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    cadastral_cost_min: Optional[float] = Query(None),
    cadastral_cost_max: Optional[float] = Query(None),
    pct_cadastral_min: Optional[float] = Query(None),
    pct_cadastral_max: Optional[float] = Query(None),
    deposit_min: Optional[float] = Query(None),
    deposit_max: Optional[float] = Query(None),
    area_min: Optional[float] = Query(None),
    area_max: Optional[float] = Query(None),
    area_kn_min: Optional[float] = Query(None),
    area_kn_max: Optional[float] = Query(None),
    purpose: Optional[List[str]] = Query(None, alias="purpose"),
    rubric_tg: Optional[List[int]] = Query(None, alias="rubric_tg"),
    rubric_kn: Optional[List[int]] = Query(None, alias="rubric_kn"),
    auction_type: Optional[List[str]] = Query(None, alias="auction_type"),
    auction_form: Optional[List[str]] = Query(None, alias="auction_form"),
    deal_type: Optional[List[str]] = Query(None, alias="deal_type"),
    section_tg: Optional[List[str]] = Query(None, alias="section_tg"),
    etp: Optional[List[str]] = Query(None, alias="etp"),
    resale_type: Optional[List[str]] = Query(None, alias="resale_type"),
    sublease_allowed: Optional[bool] = Query(None),
    assignment_allowed: Optional[bool] = Query(None),
    source: Optional[List[str]] = Query(None, alias="source"),
    cadastral: Optional[str] = Query(None),
    submission_end_from: Optional[date] = Query(None),
    submission_end_to: Optional[date] = Query(None),
    has_coords: Optional[List[str]] = Query(None, alias="has_coords"),
    db: AsyncSession = Depends(get_db),
):
    conditions = build_filters(
        status=status, region_codes=region,
        price_min=price_min, price_max=price_max,
        cadastral_cost_min=cadastral_cost_min, cadastral_cost_max=cadastral_cost_max,
        pct_cadastral_min=pct_cadastral_min, pct_cadastral_max=pct_cadastral_max,
        deposit_min=deposit_min, deposit_max=deposit_max,
        area_min=area_min, area_max=area_max,
        area_kn_min=area_kn_min, area_kn_max=area_kn_max,
        land_purposes=purpose, rubric_tg=rubric_tg, rubric_kn=rubric_kn,
        auction_types=auction_type, auction_forms=auction_form, deal_types=deal_type,
        section_tg=section_tg, etp=etp,
        resale_types=resale_type,
        sublease_allowed=sublease_allowed, assignment_allowed=assignment_allowed,
        sources=source if source else ["torgi_gov"], cadastral=cadastral,
        submission_end_from=submission_end_from, submission_end_to=submission_end_to,
        has_coords=has_coords,
    )

    q = select(
        Lot.id, Lot.start_price, Lot.area_sqm, Lot.area_sqm_kn,
        Lot.land_purpose, Lot.rubric_tg, Lot.pct_price_to_cadastral,
        Lot.cadastral_cost, Lot.cadastral_number, Lot.location,
        Lot.auction_form, Lot.deal_type, Lot.resale_type, Lot.etp,
        Lot.category_kn, Lot.vri_kn, Lot.category_tg, Lot.vri_tg,
        Lot.submission_end, Lot.auction_start_date, Lot.auction_end_date, Lot.lot_url,
        Lot.region_name, Lot.notice_number,
        Lot.score, Lot.discount_to_market_pct, Lot.score_badges,
    ).where(and_(*conditions, Lot.location.isnot(None))).limit(5000)

    rows = (await db.execute(q)).all()
    points = []
    for row in rows:
        if row.location:
            try:
                from shapely import wkb
                point = wkb.loads(bytes(row.location.data))
                points.append({
                    "id": row.id,
                    "lat": point.y,
                    "lng": point.x,
                    "price": row.start_price,
                    "area": row.area_sqm,
                    "area_kn": row.area_sqm_kn,
                    "purpose": row.land_purpose.value if row.land_purpose else None,
                    "rubric_tg": row.rubric_tg,
                    "pct": row.pct_price_to_cadastral,
                    "cadastral_cost": row.cadastral_cost,
                    "cadastral_number": row.cadastral_number,
                    "auction_form": row.auction_form.value if row.auction_form else None,
                    "deal_type": row.deal_type.value if row.deal_type else None,
                    "resale_type": row.resale_type.value if row.resale_type else None,
                    "etp": row.etp,
                    "category_kn": row.category_kn,
                    "vri_kn": row.vri_kn,
                    "category_tg": row.category_tg,
                    "vri_tg": row.vri_tg,
                    "submission_end": row.submission_end.isoformat() if row.submission_end else None,
                    "auction_start_date": row.auction_start_date.isoformat() if row.auction_start_date else None,
                    "auction_end_date": row.auction_end_date.isoformat() if row.auction_end_date else None,
                    "lot_url": row.lot_url,
                    "region_name": row.region_name,
                    "notice_number": row.notice_number,
                    "score": row.score,
                    "discount_to_market_pct": row.discount_to_market_pct,
                    "score_badges": row.score_badges if isinstance(row.score_badges, list) else None,
                })
            except Exception:
                pass

    return {"points": points, "total": len(points)}


@router.get("/etps")
async def get_etps(db: AsyncSession = Depends(get_db)):
    """Список уникальных ЭТП из БД"""
    result = await db.execute(
        select(Lot.etp).where(Lot.etp.isnot(None), Lot.etp != "").distinct()
    )
    etps = sorted([row[0] for row in result.all() if row[0]])
    return {"etps": etps}


@router.get("/vri-search")
async def search_vri(q: str = Query("", min_length=0), db: AsyncSession = Depends(get_db)):
    """Поиск по ВРИ [TG] — автодополнение"""
    query = select(Lot.vri_tg).where(
        Lot.vri_tg.isnot(None), Lot.vri_tg != ""
    ).distinct()
    if q:
        query = query.where(Lot.vri_tg.ilike(f"%{q}%"))
    query = query.limit(20)
    result = await db.execute(query)
    items = sorted([row[0] for row in result.all() if row[0]])
    return {"items": items}


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Уникальные категории TG и auction_type из БД"""
    cat_result = await db.execute(
        select(Lot.category_tg).where(Lot.category_tg.isnot(None), Lot.category_tg != "").distinct()
    )
    categories = sorted([row[0] for row in cat_result.all() if row[0]])

    at_result = await db.execute(
        select(Lot.auction_type).where(Lot.auction_type.isnot(None)).distinct()
    )
    auction_types = sorted([row[0].value if hasattr(row[0], 'value') else str(row[0]) for row in at_result.all() if row[0]])

    return {"categories": categories, "auction_types": auction_types}


@router.get("/sections")
async def get_sections_tg(db: AsyncSession = Depends(get_db)):
    """Уникальные разделы torgi.gov (biddType.name) из БД"""
    result = await db.execute(
        select(Lot.section_tg).where(Lot.section_tg.isnot(None), Lot.section_tg != "").distinct()
    )
    sections = sorted([row[0] for row in result.all() if row[0]])
    return {"sections": sections}


@router.get("/rubrics")
async def get_rubrics():
    """Список всех рубрик (плоский)"""
    return {"rubrics": get_all_rubrics()}


@router.get("/rubrics/grouped")
async def get_rubrics_grouped():
    """Рубрики, сгруппированные по разделам — для UI фильтра"""
    return {
        "sections": get_sections(),
        "rubrics_by_section": get_rubrics_by_section(),
    }


class MarketLot(BaseModel):
    id: int
    title: Optional[str]
    start_price: Optional[float]
    area_sqm: Optional[float]
    price_per_sqm: Optional[float]
    address: Optional[str]
    lot_url: Optional[str]
    source: str
    class Config:
        from_attributes = True


@router.get("/{lot_id}/market", response_model=List[MarketLot])
async def get_market_comparison(lot_id: int, db: AsyncSession = Depends(get_db)):
    """Похожие рыночные лоты из ЦИАН в том же регионе."""
    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    def _build_q(source_enum):
        sub = (
            select(Lot)
            .where(
                Lot.source == source_enum,
                Lot.region_code == lot.region_code,
                Lot.start_price.isnot(None),
            )
            .order_by(Lot.published_at.desc().nullslast())
            .limit(4)
        )
        if lot.area_sqm:
            sub = sub.where(
                Lot.area_sqm >= lot.area_sqm / 5,
                Lot.area_sqm <= lot.area_sqm * 5,
            )
        return sub

    cian_rows = (await db.execute(_build_q(LotSource.CIAN))).scalars().all()
    avito_rows = (await db.execute(_build_q(LotSource.AVITO))).scalars().all()
    rows = list(cian_rows) + list(avito_rows)
    return [
        MarketLot(
            id=r.id,
            title=r.title,
            start_price=r.start_price,
            area_sqm=r.area_sqm,
            price_per_sqm=r.price_per_sqm,
            address=r.address,
            lot_url=r.lot_url,
            source=r.source.value if r.source else "cian",
        )
        for r in rows
    ]


@router.get("/region-data/{region_code}")
async def get_region_data(region_code: str):
    """Региональные особенности: % выкупа сельхозки, разрешение строить КФХ, % перераспределения."""
    from services.regional_data import get_regional_data
    return get_regional_data(region_code)


@router.get("/{lot_id}", response_model=LotDetail)
async def get_lot(lot_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    item = _lot_to_item(lot)
    return LotDetail(
        **item.model_dump(),
        description=lot.description,
        final_price=lot.final_price,
        price_per_sqm=lot.price_per_sqm,
        organizer_name=lot.organizer_name,
        auction_start_date=lot.auction_start_date.isoformat() if lot.auction_start_date else None,
        rosreestr_data=lot.rosreestr_data,
        ai_assessment=lot.ai_assessment,
    )
