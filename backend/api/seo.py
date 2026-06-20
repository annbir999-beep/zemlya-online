"""SEO-лендинги по регионам — программные посадочные страницы.

89 уникальных страниц «Земельные торги в {регион}» ловят локальный поиск.
Данные собираются из активных лотов + справочника регионов. Кэш 10 мин.

  · GET /api/seo/regions          — список регионов со счётчиками (для индекса)
  · GET /api/seo/regions/{slug}   — данные одной региональной страницы
"""
import json as _json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.lot import Lot, LotStatus, LotSource

router = APIRouter()

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def region_slug(name: str) -> str:
    out = []
    for ch in (name or "").lower():
        if ch in _TRANSLIT:
            out.append(_TRANSLIT[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    slug = "".join(out)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


async def _region_rows(db: AsyncSession):
    base = and_(Lot.status == LotStatus.ACTIVE, Lot.source == LotSource.TORGI_GOV)
    rows = (await db.execute(
        select(
            Lot.region_code, Lot.region_name,
            func.count(Lot.id).label("cnt"),
            func.avg(Lot.discount_to_market_pct).label("avg_disc"),
            func.avg(Lot.score).label("avg_score"),
            func.min(Lot.start_price).label("min_price"),
        )
        .where(base, Lot.region_name.isnot(None))
        .group_by(Lot.region_code, Lot.region_name)
        .order_by(desc("cnt"))
    )).all()
    return rows


@router.get("/regions")
async def list_regions(db: AsyncSession = Depends(get_db)):
    from services.telegram_bot import get_redis
    redis = get_redis()
    try:
        cached = await redis.get("seo:regions:v1")
        if cached:
            return _json.loads(cached)
    except Exception:
        pass

    rows = await _region_rows(db)
    items = [{
        "slug": region_slug(r.region_name),
        "code": r.region_code,
        "name": r.region_name,
        "count": r.cnt,
        "avg_discount_pct": round(float(r.avg_disc)) if r.avg_disc else None,
        "avg_score": round(float(r.avg_score)) if r.avg_score else None,
        "min_price": float(r.min_price) if r.min_price else None,
    } for r in rows]
    payload = {"items": items, "total": len(items)}
    try:
        await redis.setex("seo:regions:v1", 600, _json.dumps(payload, default=str))
    except Exception:
        pass
    return payload


@router.get("/regions/{slug}")
async def region_page(slug: str, db: AsyncSession = Depends(get_db)):
    rows = await _region_rows(db)
    match = next((r for r in rows if region_slug(r.region_name) == slug), None)
    if not match:
        raise HTTPException(status_code=404, detail="Регион не найден")

    # Топ-10 лотов региона по скору
    top = (await db.execute(
        select(Lot)
        .where(
            Lot.status == LotStatus.ACTIVE,
            Lot.source == LotSource.TORGI_GOV,
            Lot.region_code == match.region_code,
            Lot.start_price.isnot(None),
        )
        .order_by(desc(Lot.score), desc(Lot.discount_to_market_pct))
        .limit(10)
    )).scalars().all()

    top_lots = [{
        "id": l.id,
        "title": l.title,
        "start_price": float(l.start_price) if l.start_price else None,
        "area_sqm": float(l.area_sqm) if l.area_sqm else None,
        "land_purpose": l.land_purpose.value if l.land_purpose else None,
        "score": l.score,
        "discount_to_market_pct": round(float(l.discount_to_market_pct)) if l.discount_to_market_pct else None,
        "submission_end": l.submission_end.isoformat() if l.submission_end else None,
    } for l in top]

    # Справка по региону (коэффициенты выкупа и т.п.)
    try:
        from services.regional_data import get_regional_data
        regional = get_regional_data(match.region_code) or {}
    except Exception:
        regional = {}

    return {
        "slug": slug,
        "code": match.region_code,
        "name": match.region_name,
        "count": match.cnt,
        "avg_discount_pct": round(float(match.avg_disc)) if match.avg_disc else None,
        "avg_score": round(float(match.avg_score)) if match.avg_score else None,
        "min_price": float(match.min_price) if match.min_price else None,
        "top_lots": top_lots,
        "regional": regional,
    }
