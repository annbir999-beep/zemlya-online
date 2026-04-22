"""
Клиент НСПД (nspd.gov.ru) — публичная кадастровая карта.
Открытый API — не требует регистрации или ключей.
Эндпоинт: /api/geoportal/v2/search/geoportal

Используем curl-cffi с Chrome TLS fingerprint — у httpx НСПД возвращает 502.
"""
import httpx  # оставляем для HTTPError совместимости
from curl_cffi.requests import AsyncSession
from typing import Optional


NSPD_BASE = "https://nspd.gov.ru"


class RosreestrClient:
    def __init__(self):
        from core.config import settings
        scheme = getattr(settings, "PROXY_SCHEME", None) or "http"
        proxy_url = (
            f"{scheme}://{settings.PROXY_USER}:{settings.PROXY_PASS}@{settings.PROXY_HOST}"
            if getattr(settings, "PROXY_HOST", None)
            else None
        )
        self.client = AsyncSession(
            timeout=30,
            verify=False,
            proxy=proxy_url,
            impersonate="chrome124",
            headers={
                "Referer": "https://nspd.gov.ru/map?thematic=PKK",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Origin": "https://nspd.gov.ru",
            },
        )

    async def get_cadastral_info(self, cadastral_number: str) -> Optional[dict]:
        """
        Получает данные по кадастровому номеру через НСПД.
        Возвращает dict с полями: area_sqm, address, category, vri, lat, lng, cadastral_cost
        """
        if not cadastral_number:
            return None

        try:
            resp = await self.client.get(
                f"{NSPD_BASE}/api/geoportal/v2/search/geoportal",
                params={"thematicSearchId": 1, "query": cadastral_number},
            )
            if resp.status_code != 200:
                print(f"[Росреестр] {cadastral_number}: HTTP {resp.status_code}")
                return None
            data = resp.json()
        except Exception as e:
            print(f"[Росреестр] Ошибка запроса {cadastral_number}: {type(e).__name__}")
            return None

        # Ответ: {"data": {"features": [...]}} или {"features": [...]}
        features = (
            data.get("data", {}).get("features")
            or data.get("features")
            or []
        )
        if not features:
            return None

        feature = features[0]
        props = feature.get("properties") or {}
        attrs = feature.get("attrs") or props
        options = props.get("options") or {}
        center = feature.get("center") or {}

        # Координаты могут быть в center.y/x или geometry.coordinates (EPSG:3857)
        lat = center.get("y")
        lng = center.get("x")

        # Если center пустой — берём центроид из geometry
        if (not lat or not lng) and feature.get("geometry"):
            try:
                from shapely.geometry import shape
                geom = shape(feature["geometry"])
                centroid = geom.centroid
                lng, lat = centroid.x, centroid.y
            except Exception:
                pass

        # Если координаты в метрах (EPSG:3857) — конвертируем в WGS84
        if lat and lng and (abs(lat) > 90 or abs(lng) > 180):
            try:
                from pyproj import Transformer
                transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
                lng, lat = transformer.transform(lng, lat)
            except Exception:
                lat, lng = None, None

        # Приоритет: options (новый НСПД API) → attrs (старый формат)
        result = {
            "cadastral_number": options.get("cad_num") or attrs.get("cn") or attrs.get("cadastral_number"),
            "area_sqm": options.get("area") or options.get("specified_area") or options.get("declared_area") or attrs.get("area_value"),
            "address": options.get("readable_address") or attrs.get("address"),
            "category": options.get("land_record_category_type") or props.get("categoryName") or attrs.get("category"),
            "vri": options.get("permitted_use_established_by_document") or attrs.get("util_by_doc") or attrs.get("vri"),
            "status": options.get("status") or attrs.get("status"),
            "cadastral_cost": options.get("cost_value") or attrs.get("cad_cost"),
            "cost_determination_date": options.get("cost_determination_date"),
            "lat": lat,
            "lng": lng,
        }

        return {k: v for k, v in result.items() if v is not None}

    async def search_by_coords(self, lat: float, lng: float) -> Optional[dict]:
        """Ищем участок по координатам"""
        try:
            resp = await self.client.get(
                f"{NSPD_BASE}/api/geoportal/v2/search/geoportal",
                params={
                    "thematicSearchId": 1,
                    "query": f"{lat},{lng}",
                },
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            features = data.get("data", {}).get("features") or data.get("features") or []
            if features:
                attrs = features[0].get("attrs") or features[0].get("properties") or {}
                return {"cadastral_number": attrs.get("cn"), "area_sqm": attrs.get("area_value")}
        except Exception:
            pass
        return None

    async def close(self):
        # curl_cffi AsyncSession exposes close() (not aclose())
        closer = getattr(self.client, "aclose", None) or getattr(self.client, "close", None)
        if closer is not None:
            result = closer()
            if hasattr(result, "__await__"):
                await result
