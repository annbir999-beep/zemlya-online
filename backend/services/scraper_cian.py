"""
Парсер CIAN — земельные участки для сравнения рыночных цен.

Использует внутренний JSON API CIAN (не требует Playwright).
Данные сохраняются в таблицу lots с source=CIAN.
"""
import asyncio
import httpx
import json
import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.lot import Lot, LotSource, LotStatus, LandPurpose


CIAN_API = "https://api.cian.ru/search-offers/v2/search-offers-desktop/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.cian.ru",
    "Referer": "https://www.cian.ru/",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# Наши коды регионов → ID региона CIAN
REGION_MAP: dict[str, int] = {
    "77": 1,       # Москва
    "50": 4593,    # Московская область
    "78": 2,       # Санкт-Петербург
    "47": 4588,    # Ленинградская область
    "23": 4,       # Краснодарский край
    "61": 4606,    # Ростовская область
    "52": 4596,    # Нижегородская область
    "63": 4608,    # Самарская область
    "66": 4612,    # Свердловская область
    "74": 4618,    # Челябинская область
    "54": 4598,    # Новосибирская область
    "59": 4604,    # Пермский край
    "16": 4594,    # Республика Татарстан
    "72": 4619,    # Тюменская область
    "02": 4580,    # Республика Башкортостан
}


def _parse_purpose(category: Optional[str], title: Optional[str]) -> LandPurpose:
    """Определяем назначение по категории/названию ЦИАН."""
    text = ((category or "") + " " + (title or "")).lower()
    if "ижс" in text or "индивидуальн" in text:
        return LandPurpose.IZhS
    if "снт" in text or "садоводств" in text or "дач" in text:
        return LandPurpose.SNT
    if "лпх" in text or "подсобн" in text:
        return LandPurpose.LPKh
    if "сельхоз" in text or "фермерск" in text or "пашн" in text or "сельскохоз" in text:
        return LandPurpose.AGRICULTURAL
    if "коммерч" in text or "торгов" in text:
        return LandPurpose.COMMERCIAL
    if "промышл" in text or "производств" in text:
        return LandPurpose.INDUSTRIAL
    return LandPurpose.OTHER


class CianScraper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        region_codes: Optional[list] = None,
        pages_per_region: int = 3,
    ) -> int:
        """
        Парсит объявления о продаже земли с ЦИАН.
        region_codes — список наших кодов регионов.
        """
        if not region_codes:
            region_codes = list(REGION_MAP.keys())

        saved = 0
        async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
            for code in region_codes:
                cian_id = REGION_MAP.get(code)
                if not cian_id:
                    print(f"[cian] Нет маппинга для региона {code}, пропускаем")
                    continue

                print(f"[cian] Регион {code} (CIAN ID: {cian_id})")
                for page in range(1, pages_per_region + 1):
                    count = await self._scrape_page(client, cian_id, code, page)
                    saved += count
                    if count == 0:
                        break
                    await asyncio.sleep(1.5)

        print(f"[cian] Итого сохранено/обновлено: {saved}")
        return saved

    async def _scrape_page(
        self, client: httpx.AsyncClient, cian_id: int, region_code: str, page: int
    ) -> int:
        payload = {
            "jsonQuery": {
                "_type": "landsale",
                "engine_version": {"type": "term", "value": 2},
                "region": {"type": "terms", "value": [cian_id]},
                "page": {"type": "term", "value": page},
            }
        }

        try:
            resp = await client.post(CIAN_API, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[cian] Ошибка запроса (регион {region_code}, стр.{page}): {e}")
            return 0

        offers = self._extract_offers(data)
        if not offers:
            print(f"[cian] Нет объявлений (регион {region_code}, стр.{page})")
            return 0

        saved = 0
        for offer in offers:
            try:
                await self._upsert_lot(offer, region_code)
                saved += 1
            except Exception as e:
                print(f"[cian] Ошибка лота {offer.get('id')}: {e}")

        await self.db.commit()
        print(f"[cian] Регион {region_code} стр.{page}: {saved}/{len(offers)}")
        return saved

    def _extract_offers(self, data: dict) -> list:
        """Извлекаем список предложений из ответа CIAN API."""
        try:
            return data["data"]["offersSerialized"] or []
        except (KeyError, TypeError):
            pass
        # Резервный поиск
        if isinstance(data, dict):
            for key in ("offersSerialized", "offers", "items"):
                if key in data:
                    return data[key] or []
            for v in data.values():
                if isinstance(v, dict):
                    for key in ("offersSerialized", "offers"):
                        if key in v:
                            return v[key] or []
        return []

    async def _upsert_lot(self, offer: dict, region_code: str) -> None:
        offer_id = str(offer.get("id", "")).strip()
        if not offer_id:
            return

        # Только чистая земля — отсеиваем дома/дачи/коттеджи
        category = (offer.get("category") or "").lower()
        if category and "land" not in category:
            return
        title_lower = (offer.get("title") or "").lower()
        if any(word in title_lower for word in ("дом", "коттедж", "таунхаус", "house")):
            return

        external_id = f"cian_{offer_id}"

        result = await self.db.execute(select(Lot).where(Lot.external_id == external_id))
        lot = result.scalar_one_or_none()

        # --- Цена ---
        price_obj = offer.get("bargainTerms") or {}
        price = None
        if price_obj.get("price"):
            try:
                price = float(price_obj["price"])
            except (ValueError, TypeError):
                pass

        # --- Площадь ---
        area_sqm = None
        land_obj = offer.get("land") or {}
        if land_obj.get("area"):
            try:
                unit = land_obj.get("areaUnitType", "sotka")
                raw_area = float(land_obj["area"])
                if unit == "hectare":
                    area_sqm = raw_area * 10_000
                else:
                    area_sqm = raw_area * 100  # сотки → кв.м
            except (ValueError, TypeError):
                pass

        # --- Назначение ---
        category = offer.get("category", "")
        title = offer.get("title", "") or ""
        purpose = _parse_purpose(category, title)

        # --- Адрес и координаты ---
        geo = offer.get("geo") or {}
        address_parts = []
        for part in (geo.get("address") or []):
            val = part.get("fullName") or part.get("name") or ""
            if val:
                address_parts.append(val)
        address = ", ".join(address_parts)[:500]

        lat = geo.get("coordinates", {}).get("lat") if geo.get("coordinates") else None
        lng = geo.get("coordinates", {}).get("lng") if geo.get("coordinates") else None

        # --- URL ---
        lot_url = f"https://www.cian.ru/sale/land/{offer_id}/"

        # --- Публикация ---
        published_raw = offer.get("addedTimestamp") or offer.get("creationDate")
        published_at = None
        if published_raw:
            try:
                if isinstance(published_raw, (int, float)):
                    published_at = datetime.fromtimestamp(published_raw, tz=timezone.utc)
                else:
                    published_at = datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
            except Exception:
                pass

        from services.rubrics import normalize_vri_to_rubric

        if lot is None:
            lot = Lot(external_id=external_id, source=LotSource.CIAN)

        lot.title = (title or f"Земельный участок ЦИАН {offer_id}")[:500]
        lot.start_price = price
        lot.area_sqm = area_sqm
        lot.area_ha = round(area_sqm / 10_000, 4) if area_sqm else None
        lot.price_per_sqm = round(price / area_sqm, 2) if (price and area_sqm and area_sqm > 0) else None
        lot.land_purpose = purpose
        lot.land_purpose_raw = category
        lot.rubric_tg = normalize_vri_to_rubric(title)
        lot.status = LotStatus.ACTIVE
        lot.region_code = region_code
        lot.address = address
        lot.lot_url = lot_url
        lot.published_at = published_at
        lot.raw_data = offer

        # Координаты
        if lat and lng:
            from geoalchemy2.shape import from_shape
            from shapely.geometry import Point
            lot.location = from_shape(Point(lng, lat), srid=4326)

        self.db.add(lot)
