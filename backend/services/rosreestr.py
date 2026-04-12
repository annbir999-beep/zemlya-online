"""
Клиент публичной кадастровой карты Росреестра (pkk.rosreestr.ru).
Открытый API — не требует регистрации или ключей.
"""
import httpx
from typing import Optional


PKK_BASE = "https://pkk.rosreestr.ru/api"


class RosreestrClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            verify=False,  # pkk.rosreestr.ru использует самоподписанный сертификат
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Referer": "https://pkk.rosreestr.ru/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
        )

    async def get_cadastral_info(self, cadastral_number: str) -> Optional[dict]:
        """
        Получает данные по кадастровому номеру.
        Возвращает dict с полями: area, address, category, vri, lat, lng, status
        """
        if not cadastral_number:
            return None

        # Определяем тип объекта (ЗУ = тип 1)
        try:
            resp = await self.client.get(
                f"{PKK_BASE}/features/1",
                params={"text": cadastral_number, "limit": 1, "skip": 0},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as e:
            print(f"[Росреестр] Ошибка запроса {cadastral_number}: {e}")
            return None

        features = data.get("features", [])
        if not features:
            return None

        feature = features[0]
        attrs = feature.get("attrs", {})
        center = feature.get("center", {})

        result = {
            "cadastral_number": attrs.get("cn"),
            "area_sqm": attrs.get("area_value"),
            "address": attrs.get("address"),
            "category": attrs.get("category_type"),
            "vri": attrs.get("util_by_doc"),
            "status": attrs.get("status"),
            "owner_type": attrs.get("own_name"),
            "cadastral_cost": attrs.get("cad_cost"),
            "cadastral_cost_date": attrs.get("cad_cost_date"),
            "lat": center.get("y"),
            "lng": center.get("x"),
            "rosreestr_id": feature.get("id"),
        }

        # Убираем None-значения
        return {k: v for k, v in result.items() if v is not None}

    async def search_by_coords(self, lat: float, lng: float) -> Optional[dict]:
        """Ищем участок по координатам (клик на карте)"""
        try:
            resp = await self.client.get(
                f"{PKK_BASE}/features/1",
                params={"sq": f'{{"type":"Point","coordinates":[{lng},{lat}]}}', "limit": 1, "skip": 0},
            )
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            if features:
                attrs = features[0].get("attrs", {})
                return {"cadastral_number": attrs.get("cn"), "area_sqm": attrs.get("area_value")}
        except httpx.HTTPError:
            pass
        return None

    async def close(self):
        await self.client.aclose()
