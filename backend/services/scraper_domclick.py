"""
Парсер Домклик (Сбербанк) — земельные участки для сравнения рыночных цен.

Использует открытый JSON API Домклик без авторизации.
Данные сохраняются в таблицу lots с source=DOMCLICK.
"""
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.lot import Lot, LotSource, LotStatus, LandPurpose


DOMCLICK_API = "https://api.domclick.ru/search/v4/offers"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://domclick.ru/",
    "Origin": "https://domclick.ru",
}

# Коды регионов → ID региона Домклик (совпадают с ФИАС/КЛАДР)
# Домклик принимает строку региона в параметре region_id
# Используем region_name для поиска
REGION_NAMES: dict[str, str] = {
    "77": "Москва",
    "50": "Московская область",
    "78": "Санкт-Петербург",
    "47": "Ленинградская область",
    "23": "Краснодарский край",
    "61": "Ростовская область",
    "52": "Нижегородская область",
    "63": "Самарская область",
    "66": "Свердловская область",
    "74": "Челябинская область",
    "54": "Новосибирская область",
    "59": "Пермский край",
    "16": "Республика Татарстан",
    "72": "Тюменская область",
    "02": "Республика Башкортостан",
    "38": "Иркутская область",
    "24": "Красноярский край",
    "55": "Омская область",
    "76": "Ярославская область",
    "36": "Воронежская область",
}


def _parse_purpose(category: Optional[str]) -> LandPurpose:
    if not category:
        return LandPurpose.OTHER
    t = category.lower()
    if "ижс" in t or "индивидуальн" in t:
        return LandPurpose.IZhS
    if "снт" in t or "садоводств" in t or "дач" in t:
        return LandPurpose.SNT
    if "лпх" in t or "подсобн" in t:
        return LandPurpose.LPKh
    if "сельхоз" in t or "фермерск" in t or "сельскохоз" in t:
        return LandPurpose.AGRICULTURAL
    if "коммерч" in t or "торгов" in t:
        return LandPurpose.COMMERCIAL
    if "промышл" in t or "производств" in t:
        return LandPurpose.INDUSTRIAL
    return LandPurpose.OTHER


class DomclickScraper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        region_codes: Optional[list] = None,
        pages_per_region: int = 3,
    ) -> int:
        if not region_codes:
            region_codes = list(REGION_NAMES.keys())

        saved = 0
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for code in region_codes:
                region_name = REGION_NAMES.get(code)
                if not region_name:
                    continue

                print(f"[domclick] Регион {code} ({region_name})")
                for page in range(pages_per_region):
                    count = await self._scrape_page(client, region_name, code, page)
                    saved += count
                    if count == 0:
                        break
                    await asyncio.sleep(1.0)

        print(f"[domclick] Итого: {saved}")
        return saved

    async def _scrape_page(
        self, client: httpx.AsyncClient, region_name: str, region_code: str, page: int
    ) -> int:
        params = {
            "deal_type": "sale",
            "category": "land",
            "offset": page * 20,
            "limit": 20,
            "region": region_name,
        }

        try:
            resp = await client.get(DOMCLICK_API, params=params)
            if resp.status_code == 404:
                return 0
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[domclick] Ошибка (регион {region_code}, стр.{page}): {e}")
            return 0

        offers = data.get("offers") or data.get("items") or data.get("result") or []
        if isinstance(data, list):
            offers = data

        if not offers:
            print(f"[domclick] Нет данных (регион {region_code}, стр.{page}). Keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
            return 0

        saved = 0
        for offer in offers:
            try:
                await self._upsert_lot(offer, region_code)
                saved += 1
            except Exception as e:
                print(f"[domclick] Ошибка лота {offer.get('id')}: {e}")

        await self.db.commit()
        print(f"[domclick] {region_name} стр.{page}: {saved}/{len(offers)}")
        return saved

    async def _upsert_lot(self, offer: dict, region_code: str) -> None:
        offer_id = str(offer.get("id") or offer.get("offer_id") or "").strip()
        if not offer_id:
            return

        external_id = f"domclick_{offer_id}"

        result = await self.db.execute(select(Lot).where(Lot.external_id == external_id))
        lot = result.scalar_one_or_none()

        price = None
        for key in ("price", "cost", "total_price"):
            if offer.get(key):
                try:
                    price = float(offer[key])
                    break
                except (ValueError, TypeError):
                    pass

        area_sqm = None
        for key in ("land_area", "area", "square"):
            if offer.get(key):
                try:
                    raw = float(offer[key])
                    unit = offer.get("land_area_unit", offer.get("area_unit", "sotka"))
                    if "сот" in str(unit).lower() or unit == "sotka":
                        area_sqm = raw * 100
                    elif "га" in str(unit).lower() or unit == "hectare":
                        area_sqm = raw * 10_000
                    else:
                        area_sqm = raw  # кв.м
                    break
                except (ValueError, TypeError):
                    pass

        category = offer.get("land_category") or offer.get("category_name") or offer.get("subcategory") or ""
        purpose = _parse_purpose(category)

        address_parts = []
        for key in ("address", "full_address", "location"):
            v = offer.get(key)
            if isinstance(v, str) and v:
                address_parts.append(v)
                break
            elif isinstance(v, dict):
                address_parts.append(v.get("full_address") or v.get("address") or "")
                break
        address = (address_parts[0] if address_parts else "")[:500]

        lat = offer.get("lat") or (offer.get("geo") or {}).get("lat")
        lng = offer.get("lon") or offer.get("lng") or (offer.get("geo") or {}).get("lon")

        title = offer.get("title") or offer.get("name") or f"Земельный участок Домклик {offer_id}"

        lot_url = offer.get("url") or f"https://domclick.ru/card/sale__land_{offer_id}"

        from services.rubrics import normalize_vri_to_rubric

        if lot is None:
            lot = Lot(external_id=external_id, source=LotSource.DOMCLICK)

        lot.title = str(title)[:500]
        lot.start_price = price
        lot.area_sqm = area_sqm
        lot.area_ha = round(area_sqm / 10_000, 4) if area_sqm else None
        lot.price_per_sqm = round(price / area_sqm, 2) if (price and area_sqm and area_sqm > 0) else None
        lot.land_purpose = purpose
        lot.land_purpose_raw = category
        lot.rubric_tg = normalize_vri_to_rubric(category or title)
        lot.status = LotStatus.ACTIVE
        lot.region_code = region_code
        lot.address = address
        lot.lot_url = lot_url
        lot.raw_data = offer

        if lat and lng:
            try:
                from geoalchemy2.shape import from_shape
                from shapely.geometry import Point
                lot.location = from_shape(Point(float(lng), float(lat)), srid=4326)
            except Exception:
                pass

        self.db.add(lot)
