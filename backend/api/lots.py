from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from geoalchemy2.functions import ST_DWithin, ST_MakePoint, ST_SetSRID
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime, timezone
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
    # Локация и инфра
    nearest_city_name: Optional[str] = None
    nearest_city_distance_km: Optional[float] = None
    nearest_city_population: Optional[int] = None
    communications: Optional[dict] = None
    # Снижение цены (повторные торги)
    last_price_drop_pct: Optional[float] = None
    last_price_drop_at: Optional[str] = None

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
    full_description: Optional[str] = None
    technical_conditions: Optional[str] = None
    contract_terms: Optional[dict] = None
    nearby_features: Optional[dict] = None
    organizer_contacts: Optional[dict] = None


class LotsResponse(BaseModel):
    items: List[LotListItem]
    total: int
    page: int
    pages: int


# ── Filter builder ────────────────────────────────────────────────────────────

def build_filters(
    status: Optional[str] = None,
    region_codes: Optional[List[str]] = None,
    # Скоринг
    score_min: Optional[int] = None,
    badges_min: Optional[int] = None,
    discount_min: Optional[float] = None,
    # Ликвидность (high/medium/low) — опирается на расстояние до города и его население
    liquidity: Optional[str] = None,
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

    # Скоринг
    if score_min is not None:
        conditions.append(Lot.score >= score_min)
    if discount_min is not None:
        conditions.append(Lot.discount_to_market_pct >= discount_min)
    if badges_min is not None and badges_min > 0:
        # Фильтр по минимальному количеству бейджей в JSON-массиве
        from sqlalchemy import func as _f, cast, JSON
        conditions.append(_f.json_array_length(cast(Lot.score_badges, JSON)) >= badges_min)

    # Ликвидность по близости к городу и его населению
    if liquidity == "high":
        conditions.append(Lot.nearest_city_distance_km <= 30)
        conditions.append(Lot.nearest_city_population >= 500_000)
    elif liquidity == "medium":
        conditions.append(Lot.nearest_city_distance_km <= 100)
        conditions.append(Lot.nearest_city_population >= 100_000)
    elif liquidity == "low":
        conditions.append(or_(
            Lot.nearest_city_distance_km > 100,
            Lot.nearest_city_population < 100_000,
        ))

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
        nearest_city_name=lot.nearest_city_name,
        nearest_city_distance_km=lot.nearest_city_distance_km,
        nearest_city_population=lot.nearest_city_population,
        communications=lot.communications if isinstance(lot.communications, dict) else None,
        last_price_drop_pct=lot.last_price_drop_pct,
        last_price_drop_at=lot.last_price_drop_at.isoformat() if lot.last_price_drop_at else None,
    )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=LotsResponse)
async def get_lots(
    # Статус
    status: Optional[str] = Query(None),
    # Регион
    region: Optional[List[str]] = Query(None, alias="region"),
    # Скоринг
    score_min: Optional[int] = Query(None, ge=0, le=100),
    badges_min: Optional[int] = Query(None, ge=0, le=10),
    discount_min: Optional[float] = Query(None),
    liquidity: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
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
        score_min=score_min, badges_min=badges_min, discount_min=discount_min,
        liquidity=liquidity,
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


@router.get("/{lot_id}/report.pdf")
async def lot_pdf_report(lot_id: int, db: AsyncSession = Depends(get_db)):
    """PDF-отчёт по лоту: ключевые KPI + ИИ-вердикт + контакты + что рядом."""
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    from xhtml2pdf import pisa

    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    def fmt_p(v):
        if not v: return "—"
        if v >= 1_000_000: return f"{v/1_000_000:.2f} млн ₽"
        if v >= 1_000: return f"{v/1_000:.0f} тыс. ₽"
        return f"{int(v)} ₽"

    def fmt_a(v):
        if not v: return "—"
        if v >= 10_000: return f"{v/10_000:.2f} га"
        return f"{int(v):,} м²".replace(",", " ")

    contacts = lot.organizer_contacts or {}
    phones = "<br/>".join(contacts.get("phones", []) or []) or "—"
    emails = "<br/>".join(contacts.get("emails", []) or []) or "—"
    nearby = lot.nearby_features or {}
    nearby_lines = []
    if nearby.get("water"):
        w = nearby["water"]
        nearby_lines.append(f"🌊 {w.get('name', 'Водоём')} — {int(w.get('distance_m', 0))} м")
    if nearby.get("forest"):
        nearby_lines.append(f"🌲 Лес — {int(nearby['forest']['distance_m'])} м")
    if nearby.get("settlement"):
        s = nearby["settlement"]
        nearby_lines.append(f"🏘 {s.get('name', 'Посёлок')} — {int(s.get('distance_m', 0))} м")
    nearby_html = "<br/>".join(nearby_lines) or "—"

    ai = lot.ai_assessment or {}
    ai_summary = ai.get("summary", "") if isinstance(ai, dict) else ""
    ai_strategy = ai.get("best_strategy", "") if isinstance(ai, dict) else ""
    ai_score = ai.get("score") if isinstance(ai, dict) else None
    pros = ai.get("pros", []) if isinstance(ai, dict) else []
    cons = ai.get("cons", []) if isinstance(ai, dict) else []

    SITE = "https://xn--e1adnd0h.online"
    title = (lot.title or "Земельный участок")[:200]

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 1.6cm; }}
body {{ font-family: Helvetica, Arial, sans-serif; color: #1f2937; font-size: 11pt; line-height: 1.4; }}
.header {{ border-bottom: 3px solid #16a34a; padding-bottom: 10px; margin-bottom: 18px; }}
.brand {{ font-size: 18pt; font-weight: 700; color: #16a34a; }}
.brand-sub {{ font-size: 9pt; color: #6b7280; letter-spacing: 0.05em; text-transform: uppercase; }}
h1 {{ font-size: 14pt; margin: 0 0 6px; }}
.meta {{ color: #6b7280; font-size: 10pt; margin-bottom: 16px; }}
.kpi {{ background: #f3f4f6; border-radius: 6px; padding: 12px; margin-bottom: 14px; }}
.kpi-row {{ display: table; width: 100%; }}
.kpi-cell {{ display: table-cell; width: 50%; padding: 4px 8px; }}
.kpi-cell b {{ font-size: 14pt; color: #16a34a; }}
.kpi-cell .label {{ font-size: 9pt; color: #6b7280; }}
.section {{ margin-top: 16px; }}
.section h2 {{ font-size: 12pt; color: #1f2937; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }}
.section .row {{ margin: 4px 0; }}
.section .label {{ color: #6b7280; display: inline-block; min-width: 130px; }}
.score-box {{ display: inline-block; background: #dc2626; color: #fff; font-weight: 700;
              padding: 4px 12px; border-radius: 20px; font-size: 12pt; }}
.ai-box {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 10px 14px; border-radius: 4px; }}
.pros li {{ color: #16a34a; }}
.cons li {{ color: #dc2626; }}
.footer {{ margin-top: 24px; padding-top: 10px; border-top: 1px solid #e5e7eb;
           font-size: 9pt; color: #6b7280; text-align: center; }}
</style></head><body>

<div class="header">
  <div class="brand">земля.online</div>
  <div class="brand-sub">аукционы земли РФ — отчёт по лоту</div>
</div>

<h1>{title}</h1>
<div class="meta">
  Кадастровый номер: <b>{lot.cadastral_number or "—"}</b><br/>
  {lot.region_name or ""}{(" · " + lot.address) if lot.address else ""}
</div>

<div class="kpi">
  <div class="kpi-row">
    <div class="kpi-cell"><div class="label">Стартовая цена</div><b>{fmt_p(lot.start_price)}</b></div>
    <div class="kpi-cell"><div class="label">Площадь</div><b>{fmt_a(lot.area_sqm)}</b></div>
  </div>
  <div class="kpi-row">
    <div class="kpi-cell"><div class="label">Кадастровая стоимость</div>{fmt_p(lot.cadastral_cost)}</div>
    <div class="kpi-cell"><div class="label">% НЦ от КС</div>{lot.pct_price_to_cadastral:.1f}%{"" if lot.pct_price_to_cadastral else ""}</div>
  </div>
  <div class="kpi-row">
    <div class="kpi-cell"><div class="label">Дисконт к рынку</div>{f"{int(lot.discount_to_market_pct)}%" if lot.discount_to_market_pct else "—"}</div>
    <div class="kpi-cell"><div class="label">Скор</div><span class="score-box">{lot.score or 0}</span></div>
  </div>
</div>

{f'<div class="section"><h2>🤖 ИИ-анализ</h2>' if ai_summary else ''}
{f'<div class="ai-box"><b>Стратегия:</b> {ai_strategy}<br/><br/>{ai_summary}</div>' if ai_summary else ''}
{f'<p><b>Плюсы:</b><ul class="pros">{"".join(f"<li>{p}</li>" for p in pros[:5])}</ul></p>' if pros else ''}
{f'<p><b>Риски:</b><ul class="cons">{"".join(f"<li>{c}</li>" for c in cons[:5])}</ul></p>' if cons else ''}
{f'</div>' if ai_summary else ''}

<div class="section">
  <h2>📋 Условия торгов</h2>
  <div class="row"><span class="label">Тип:</span> {lot.auction_type.value if lot.auction_type else "—"}</div>
  <div class="row"><span class="label">Срок подачи заявок:</span> {lot.submission_end.strftime("%d.%m.%Y %H:%M") if lot.submission_end else "—"}</div>
  <div class="row"><span class="label">Задаток:</span> {fmt_p(lot.deposit)}</div>
  <div class="row"><span class="label">Категория земель:</span> {lot.category_tg or "—"}</div>
  <div class="row"><span class="label">ВРИ:</span> {(lot.vri_tg or "")[:200]}</div>
</div>

<div class="section">
  <h2>🌳 Что рядом</h2>
  <div class="row">{nearby_html}</div>
</div>

<div class="section">
  <h2>🏛 Контакты администрации</h2>
  <div class="row"><b>{lot.organizer_name or "—"}</b></div>
  <div class="row"><span class="label">Телефон:</span> {phones}</div>
  <div class="row"><span class="label">Email:</span> {emails}</div>
  {f'<div class="row"><span class="label">Ответственный:</span> {contacts.get("contact_person", "")}</div>' if contacts.get("contact_person") else ""}
  {f'<div class="row"><span class="label">ИНН:</span> {contacts.get("inn", "")}</div>' if contacts.get("inn") else ""}
  {f'<div class="row"><span class="label">Адрес:</span> {contacts.get("address", "")}</div>' if contacts.get("address") else ""}
</div>

<div class="footer">
  Открыть лот онлайн: {SITE}/lots/{lot.id}<br/>
  Отчёт сгенерирован {datetime.now(timezone.utc).strftime("%d.%m.%Y")} — данные могут устареть, перепроверьте перед сделкой.
</div>

</body></html>"""

    buf = BytesIO()
    pisa.CreatePDF(html, dest=buf, encoding="utf-8")
    buf.seek(0)
    filename = f"lot-{lot_id}-zemlya-online.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{lot_id}/roi")
async def calculate_roi(
    lot_id: int,
    house_area_sqm: float = Query(120, ge=20, le=1000),
    sell_price_per_sqm: float = Query(80000, ge=10000, le=500000),
    finish_level: str = Query("mid", pattern="^(rough|mid|premium)$"),
    db: AsyncSession = Depends(get_db),
):
    """Калькулятор окупаемости для лота — каркасный дом фиксированной площади.

    Оценивает: вложения = цена_лота + стоимость_постройки;
    выручка_от_продажи = площадь_дома × цена_за_м²;
    ROI = (выручка - вложения) / вложения × 100%.
    """
    from services.build_costs import get_build_cost

    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    build = get_build_cost(lot.region_code, house_area_sqm, finish_level)
    land_price = lot.start_price or 0
    investment = land_price + build["total_cost"]
    revenue = house_area_sqm * sell_price_per_sqm
    profit = revenue - investment
    roi_pct = (profit / investment * 100) if investment > 0 else 0
    payback_years = (investment / revenue) if revenue > 0 else None

    return {
        "lot_id": lot_id,
        "inputs": {
            "house_area_sqm": house_area_sqm,
            "sell_price_per_sqm": sell_price_per_sqm,
            "finish_level": finish_level,
        },
        "build": build,
        "land_price": int(land_price),
        "total_investment": int(investment),
        "expected_revenue": int(revenue),
        "expected_profit": int(profit),
        "roi_pct": round(roi_pct, 1),
        "payback_years": round(payback_years, 1) if payback_years else None,
    }


@router.get("/heatmap")
async def get_heatmap(db: AsyncSession = Depends(get_db)):
    """Тепловая карта по регионам РФ.

    Для каждого субъекта возвращает количество активных лотов, средний
    дисконт к рынку и средний score. Точка ставится в координатах
    административного центра субъекта (REGION_CENTERS). Кэш 5 минут.
    """
    import json as _json
    from services.telegram_bot import get_redis
    from services.region_centers import REGION_CENTERS

    cache_key = "heatmap:v1"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        pass

    base = and_(Lot.status == LotStatus.ACTIVE, Lot.source == LotSource.TORGI_GOV)

    rows = (
        await db.execute(
            select(
                Lot.region_code,
                Lot.region_name,
                func.count(Lot.id).label("cnt"),
                func.avg(Lot.discount_to_market_pct).label("avg_disc"),
                func.avg(Lot.score).label("avg_score"),
                func.avg(Lot.price_per_sqm).label("avg_psqm"),
            )
            .where(base)
            .group_by(Lot.region_code, Lot.region_name)
            .order_by(func.count(Lot.id).desc())
        )
    ).all()

    items = []
    for r in rows:
        center = REGION_CENTERS.get(r.region_code or "")
        if not center:
            continue
        items.append({
            "code": r.region_code,
            "name": r.region_name,
            "lat": center[0],
            "lng": center[1],
            "count": r.cnt,
            "avg_discount_pct": float(r.avg_disc) if r.avg_disc else None,
            "avg_score": float(r.avg_score) if r.avg_score else None,
            "avg_price_per_sqm": float(r.avg_psqm) if r.avg_psqm else None,
        })

    payload = {"items": items, "total_regions": len(items)}
    try:
        await redis.setex(cache_key, 300, _json.dumps(payload, default=str))
    except Exception:
        pass
    return payload


@router.get("/export")
async def export_lots_csv(
    # Используем ту же фильтрацию что и /api/lots — пробрасываем те же параметры
    status: Optional[str] = Query(None),
    region: Optional[List[str]] = Query(None, alias="region"),
    score_min: Optional[int] = Query(None),
    discount_min: Optional[float] = Query(None),
    liquidity: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
    price_min: Optional[float] = Query(None),
    price_max: Optional[float] = Query(None),
    area_min: Optional[float] = Query(None),
    area_max: Optional[float] = Query(None),
    purpose: Optional[List[str]] = Query(None, alias="purpose"),
    auction_type: Optional[List[str]] = Query(None, alias="auction_type"),
    source: Optional[List[str]] = Query(None, alias="source"),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(2000, le=5000),
):
    """Экспорт списка лотов в CSV (UTF-8 BOM для Excel)."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    conditions = build_filters(
        status=status, region_codes=region,
        score_min=score_min, discount_min=discount_min, liquidity=liquidity,
        price_min=price_min, price_max=price_max,
        area_min=area_min, area_max=area_max,
        land_purposes=purpose, auction_types=auction_type,
        sources=source if source else ["torgi_gov"],
    )
    q = (
        select(Lot)
        .where(and_(*conditions))
        .order_by(Lot.score.desc().nulls_last())
        .limit(limit)
    )
    lots = (await db.execute(q)).scalars().all()

    headers = [
        "ID", "Название", "Регион", "Адрес", "Кадастровый номер",
        "Назначение", "Тип торгов", "Площадь (м²)", "Цена (₽)",
        "Кадастровая стоимость (₽)", "% НЦ/КС", "Дисконт к рынку (%)",
        "Score", "Срок подачи", "Ссылка",
    ]

    purpose_label = {
        "izhs": "ИЖС", "lpkh": "ЛПХ", "snt": "СНТ/Дача",
        "agricultural": "Сельхоз", "commercial": "Коммерческое",
        "industrial": "Промышленное", "forest": "Лесной фонд",
        "water": "Водный фонд", "special": "Спец. назначения", "other": "Иное",
    }
    auction_label = {"sale": "Продажа", "rent": "Аренда", "priv": "Приватизация"}

    buf = io.StringIO()
    buf.write("﻿")  # BOM для Excel
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    w.writerow(headers)
    for l in lots:
        w.writerow([
            l.id,
            (l.title or "")[:200],
            l.region_name or "",
            l.address or "",
            l.cadastral_number or "",
            purpose_label.get(l.land_purpose.value if l.land_purpose else "", ""),
            auction_label.get(l.auction_type.value if l.auction_type else "", ""),
            f"{l.area_sqm:.0f}" if l.area_sqm else "",
            f"{l.start_price:.0f}" if l.start_price else "",
            f"{l.cadastral_cost:.0f}" if l.cadastral_cost else "",
            f"{l.pct_price_to_cadastral:.1f}" if l.pct_price_to_cadastral is not None else "",
            f"{l.discount_to_market_pct:.1f}" if l.discount_to_market_pct is not None else "",
            l.score if l.score is not None else "",
            l.submission_end.strftime("%d.%m.%Y %H:%M") if l.submission_end else "",
            l.lot_url or "",
        ])

    buf.seek(0)
    filename = f"zemlya-online-lots-{len(lots)}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/analytics")
async def get_analytics(db: AsyncSession = Depends(get_db)):
    """Сводная аналитика рынка для публичной страницы /analytics.

    Кэшируется в Redis на 5 минут — расчёт тяжёлый (5+ агрегатов по
    всей таблице lots), а данные обновляются медленно (раз в 30 мин по cron).
    """
    import json as _json
    from datetime import datetime, timezone, timedelta
    from services.telegram_bot import get_redis  # переиспользуем единый redis-клиент

    cache_key = "analytics:v1"
    redis = get_redis()
    try:
        cached = await redis.get(cache_key)
        if cached:
            return _json.loads(cached)
    except Exception:
        pass  # Redis недоступен — считаем заново

    base = and_(Lot.status == LotStatus.ACTIVE, Lot.source == LotSource.TORGI_GOV)
    now = datetime.now(timezone.utc)

    # ── KPI ──
    total_active = (await db.execute(select(func.count()).where(base))).scalar() or 0
    # Когда у лота отсутствует published_at (поле не всегда заполнено в API torgi),
    # fallback на created_at — момент появления лота в нашей БД.
    discovered_at = func.coalesce(Lot.published_at, Lot.created_at)
    new_24h = (
        await db.execute(
            select(func.count()).where(
                and_(base, discovered_at >= now - timedelta(hours=24))
            )
        )
    ).scalar() or 0
    avg_price_sqm = (
        await db.execute(select(func.avg(Lot.price_per_sqm)).where(base))
    ).scalar()
    avg_discount = (
        await db.execute(
            select(func.avg(Lot.discount_to_market_pct)).where(
                and_(base, Lot.discount_to_market_pct.isnot(None))
            )
        )
    ).scalar()
    pdf_parsed = (
        await db.execute(
            select(func.count()).where(and_(base, Lot.pdf_parsed_at.isnot(None)))
        )
    ).scalar() or 0
    ai_analyzed = (
        await db.execute(
            select(func.count()).where(and_(base, Lot.ai_assessment.isnot(None)))
        )
    ).scalar() or 0

    # ── Топ-15 регионов ──
    by_region_rows = (
        await db.execute(
            select(
                Lot.region_code,
                Lot.region_name,
                func.count(Lot.id).label("cnt"),
                func.avg(Lot.price_per_sqm).label("avg_psqm"),
            )
            .where(base)
            .group_by(Lot.region_code, Lot.region_name)
            .order_by(func.count(Lot.id).desc())
            .limit(15)
        )
    ).all()
    by_region = [
        {
            "code": r.region_code,
            "name": r.region_name,
            "count": r.cnt,
            "avg_price_per_sqm": float(r.avg_psqm) if r.avg_psqm else None,
        }
        for r in by_region_rows
    ]

    # ── Назначение земли ──
    by_purpose_rows = (
        await db.execute(
            select(Lot.land_purpose, func.count(Lot.id).label("cnt"))
            .where(base)
            .group_by(Lot.land_purpose)
            .order_by(func.count(Lot.id).desc())
        )
    ).all()
    purpose_label = {
        "izhs": "ИЖС", "lpkh": "ЛПХ", "snt": "СНТ/Дача",
        "agricultural": "Сельхоз", "commercial": "Коммерческое",
        "industrial": "Промышленное", "forest": "Лесной фонд",
        "water": "Водный фонд", "special": "Спец. назначения",
        "other": "Иное",
    }
    by_purpose = [
        {
            "key": (r.land_purpose.value if r.land_purpose else "unknown"),
            "label": purpose_label.get(r.land_purpose.value if r.land_purpose else "", "Не указано"),
            "count": r.cnt,
        }
        for r in by_purpose_rows
    ]

    # ── Распределение по score ──
    score_buckets = []
    for low, high, label in [(90, 101, "90+"), (70, 90, "70-89"), (50, 70, "50-69"), (0, 50, "0-49")]:
        cnt = (
            await db.execute(
                select(func.count()).where(
                    and_(base, Lot.score >= low, Lot.score < high)
                )
            )
        ).scalar() or 0
        score_buckets.append({"label": label, "count": cnt})

    # ── Появление новых лотов по дням за 30 дней ──
    daily_rows = (
        await db.execute(
            select(
                func.date(discovered_at).label("d"),
                func.count(Lot.id).label("cnt"),
            )
            .where(
                and_(
                    Lot.source == LotSource.TORGI_GOV,
                    discovered_at >= now - timedelta(days=30),
                )
            )
            .group_by(func.date(discovered_at))
            .order_by(func.date(discovered_at))
        )
    ).all()
    daily_new = [
        {"date": r.d.isoformat() if r.d else None, "count": r.cnt}
        for r in daily_rows
        if r.d
    ]

    # ── Топ-5 лотов по score ──
    top_lots_rows = (
        await db.execute(
            select(Lot)
            .where(and_(base, Lot.score.isnot(None)))
            .order_by(Lot.score.desc().nulls_last())
            .limit(5)
        )
    ).scalars().all()
    top_lots = [
        {
            "id": l.id,
            "title": (l.title or "")[:100],
            "region_name": l.region_name,
            "score": l.score,
            "discount_to_market_pct": l.discount_to_market_pct,
            "start_price": l.start_price,
            "area_sqm": l.area_sqm,
        }
        for l in top_lots_rows
    ]

    payload = {
        "summary": {
            "total_active": total_active,
            "new_24h": new_24h,
            "avg_price_per_sqm": float(avg_price_sqm) if avg_price_sqm else None,
            "avg_discount_pct": float(avg_discount) if avg_discount else None,
            "pdf_parsed": pdf_parsed,
            "ai_analyzed": ai_analyzed,
        },
        "by_region": by_region,
        "by_purpose": by_purpose,
        "by_score": score_buckets,
        "daily_new": daily_new,
        "top_lots": top_lots,
        "generated_at": now.isoformat(),
    }

    try:
        await redis.setex(cache_key, 300, _json.dumps(payload, default=str))
    except Exception:
        pass

    return payload


@router.get("/ai-picks")
async def get_ai_picks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Витрина лотов с готовым ИИ-анализом (ночной батч).

    Возвращает только ACTIVE лоты, у которых есть `ai_assessment` и
    свежесть < 14 дней, отсортированные по score лота. Сам ИИ-вердикт
    включён в каждый item — фронт может отрисовать карточку без
    дополнительных запросов.
    """
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    conditions = [
        Lot.status == LotStatus.ACTIVE,
        Lot.ai_assessment.isnot(None),
        Lot.ai_assessed_at >= cutoff,
    ]
    count_q = select(func.count()).select_from(Lot).where(and_(*conditions))
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * per_page
    q = (
        select(Lot)
        .where(and_(*conditions))
        .order_by(Lot.score.desc().nulls_last())
        .offset(offset)
        .limit(per_page)
    )
    lots = (await db.execute(q)).scalars().all()

    items = []
    for l in lots:
        base = _lot_to_item(l).model_dump()
        a = l.ai_assessment or {}
        base["ai"] = {
            "score": a.get("score"),
            "best_strategy": a.get("best_strategy"),
            "summary": a.get("summary"),
            "recommended_use": a.get("recommended_use"),
            "price_estimate": a.get("price_estimate"),
            "pros": (a.get("pros") or [])[:3],
            "assessed_at": l.ai_assessed_at.isoformat() if l.ai_assessed_at else None,
        }
        items.append(base)

    return {
        "items": items,
        "total": total,
        "page": page,
        "pages": math.ceil(total / per_page) if total else 0,
    }


@router.get("/map")
async def get_lots_for_map(
    status: Optional[str] = Query("active"),
    region: Optional[List[str]] = Query(None, alias="region"),
    score_min: Optional[int] = Query(None),
    badges_min: Optional[int] = Query(None),
    discount_min: Optional[float] = Query(None),
    liquidity: Optional[str] = Query(None, pattern="^(high|medium|low)$"),
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
        score_min=score_min, badges_min=badges_min, discount_min=discount_min,
        liquidity=liquidity,
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


@router.get("/{lot_id}/similar-history")
async def get_similar_history(lot_id: int, db: AsyncSession = Depends(get_db)):
    """Похожие завершённые лоты в том же регионе/назначении/площади (для оценки реальных цен)."""
    result = await db.execute(select(Lot).where(Lot.id == lot_id))
    lot = result.scalar_one_or_none()
    if not lot:
        raise HTTPException(status_code=404, detail="Лот не найден")

    q = (
        select(Lot)
        .where(
            Lot.id != lot_id,
            Lot.source == LotSource.TORGI_GOV,
            Lot.status == LotStatus.COMPLETED,
            Lot.region_code == lot.region_code,
            Lot.land_purpose == lot.land_purpose,
            Lot.start_price.isnot(None),
        )
        .order_by(Lot.submission_end.desc())
        .limit(20)
    )
    if lot.area_sqm:
        q = q.where(
            Lot.area_sqm >= lot.area_sqm * 0.5,
            Lot.area_sqm <= lot.area_sqm * 2.0,
        )

    rows = (await db.execute(q)).scalars().all()
    items = []
    for r in rows[:10]:
        items.append({
            "id": r.id,
            "title": r.title,
            "start_price": r.start_price,
            "final_price": r.final_price,
            "area_sqm": r.area_sqm,
            "address": r.address,
            "submission_end": r.submission_end.isoformat() if r.submission_end else None,
            "deal_type": r.deal_type.value if r.deal_type else None,
            "lot_url": r.lot_url,
        })
    # Статистика
    prices = [r.start_price for r in rows if r.start_price]
    psqm = [r.start_price / r.area_sqm for r in rows if r.start_price and r.area_sqm and r.area_sqm > 0]
    stats = {
        "count": len(rows),
        "median_price": sorted(prices)[len(prices)//2] if prices else None,
        "median_price_per_sqm": sorted(psqm)[len(psqm)//2] if psqm else None,
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
    }
    return {"items": items, "stats": stats}


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
        full_description=lot.full_description,
        technical_conditions=lot.technical_conditions,
        contract_terms=lot.contract_terms if isinstance(lot.contract_terms, dict) else None,
        nearby_features=lot.nearby_features if isinstance(lot.nearby_features, dict) else None,
        organizer_contacts=lot.organizer_contacts if isinstance(lot.organizer_contacts, dict) else None,
    )
