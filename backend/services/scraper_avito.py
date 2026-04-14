"""
Парсер Avito — земельные участки для сравнения рыночных цен.

Использует:
  - httpx для запросов с браузерными заголовками
  - BeautifulSoup + __NEXT_DATA__ JSON (Next.js стандарт)
  - Playwright как fallback если страница не загрузилась без JS

Данные сохраняются в таблицу lots с source=AVITO.
"""
import asyncio
import json
import re
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.lot import Lot, LotSource, LotStatus, LandPurpose
from core.config import settings


AVITO_BASE = "https://www.avito.ru"

# Маппинг наших кодов регионов → slug Авито
# Полный список на: https://www.avito.ru/all
REGION_SLUGS: dict[str, str] = {
    "01": "respublika_adygeya",
    "02": "respublika_bashkortostan",
    "03": "respublika_buryatiya",
    "04": "respublika_altay",
    "05": "respublika_dagestan",
    "06": "respublika_ingushetiya",
    "07": "kabardino-balkarskaya_respublika",
    "08": "respublika_kalmykiya",
    "09": "karachaevo-cherkesskaya_respublika",
    "10": "respublika_kareliya",
    "11": "respublika_komi",
    "12": "respublika_mariy_el",
    "13": "respublika_mordoviya",
    "14": "respublika_sakha_yakutiya",
    "15": "respublika_severnaya_osetiya",
    "16": "respublika_tatarstan",
    "17": "respublika_tyva",
    "18": "udmurtskaya_respublika",
    "19": "respublika_khakasiya",
    "20": "chechenskaya_respublika",
    "21": "chuvashskaya_respublika",
    "22": "altayskiy_kray",
    "23": "krasnodarskiy_kray",
    "24": "krasnoyarskiy_kray",
    "25": "primorskiy_kray",
    "26": "stavropolskiy_kray",
    "27": "khabarovskiy_kray",
    "28": "amurskaya_oblast",
    "29": "arkhangelskaya_oblast",
    "30": "astrakhanskaya_oblast",
    "31": "belgorodskaya_oblast",
    "32": "bryanskaya_oblast",
    "33": "vladimirskaya_oblast",
    "34": "volgogradskaya_oblast",
    "35": "vologodskaya_oblast",
    "36": "voronezhskaya_oblast",
    "37": "ivanovskaya_oblast",
    "38": "irkutskaya_oblast",
    "39": "kaliningradskaya_oblast",
    "40": "kaluzhskaya_oblast",
    "41": "kamchatskiy_kray",
    "42": "kemerovskaya_oblast",
    "43": "kirovskaya_oblast",
    "44": "kostromskaya_oblast",
    "45": "kurganskaya_oblast",
    "46": "kurskaya_oblast",
    "47": "leningradskaya_oblast",
    "48": "lipetskaya_oblast",
    "49": "magadanskaya_oblast",
    "50": "moskovskaya_oblast",
    "51": "murmanskaya_oblast",
    "52": "nizhegorodskaya_oblast",
    "53": "novgorodskaya_oblast",
    "54": "novosibirskaya_oblast",
    "55": "omskaya_oblast",
    "56": "orenburgskaya_oblast",
    "57": "orlovskaya_oblast",
    "58": "penzenskaya_oblast",
    "59": "permskiy_kray",
    "60": "pskovskaya_oblast",
    "61": "rostovskaya_oblast",
    "62": "ryazanskaya_oblast",
    "63": "samarskaya_oblast",
    "64": "saratovskaya_oblast",
    "65": "sakhalinskaya_oblast",
    "66": "sverdlovskaya_oblast",
    "67": "smolenskaya_oblast",
    "68": "tambovskaya_oblast",
    "69": "tverskaya_oblast",
    "70": "tomskaya_oblast",
    "71": "tulskaya_oblast",
    "72": "tyumenskaya_oblast",
    "73": "ulyanovskaya_oblast",
    "74": "chelyabinskaya_oblast",
    "75": "zabaykalskiy_kray",
    "76": "yaroslavskaya_oblast",
    "77": "moskva",
    "78": "sankt-peterburg",
    "79": "evreyskaya_ao",
    "83": "nenetskiy_ao",
    "86": "khanty-mansiyskiy_ao",
    "87": "chukotskiy_ao",
    "89": "yamalo-nenetskiy_ao",
}


def _parse_area_from_title(title: str) -> Optional[float]:
    """
    Парсим площадь из заголовка Авито.
    Примеры: "6 сот.", "0.5 га", "15 соток", "1200 кв.м"
    Возвращает площадь в кв.м или None.
    """
    t = title.lower()

    # Гектары
    m = re.search(r"([\d.,]+)\s*га\b", t)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) * 10000
        except ValueError:
            pass

    # Сотки
    m = re.search(r"([\d.,]+)\s*сот", t)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) * 100
        except ValueError:
            pass

    # кв.м
    m = re.search(r"([\d.,]+)\s*кв[\s\.]?м", t)
    if m:
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            pass

    return None


def _parse_purpose_from_title(title: str) -> LandPurpose:
    t = title.lower()
    if "ижс" in t or "индивидуальн" in t:
        return LandPurpose.IZhS
    if "снт" in t or "садоводств" in t or "дач" in t:
        return LandPurpose.SNT
    if "лпх" in t or "подсобн" in t:
        return LandPurpose.LPKh
    if "сельхоз" in t or "фермерск" in t or "пашн" in t:
        return LandPurpose.AGRICULTURAL
    if "коммерч" in t or "торгов" in t:
        return LandPurpose.COMMERCIAL
    if "промышл" in t or "производств" in t:
        return LandPurpose.INDUSTRIAL
    return LandPurpose.OTHER


def _parse_published_at(date_str: Optional[str]) -> Optional[datetime]:
    """Парсим дату публикации Авито. Форматы: '12 апреля', 'вчера', '2 часа назад'."""
    if not date_str:
        return None
    now = datetime.now(timezone.utc)
    s = date_str.lower().strip()

    if "назад" in s or "час" in s or "мин" in s:
        return now

    if "вчера" in s:
        return now - timedelta(days=1)

    months = {
        "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
        "мая": 5, "июня": 6, "июля": 7, "августа": 8,
        "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    }
    for month_name, month_num in months.items():
        m = re.match(rf"(\d+)\s+{month_name}(?:\s+(\d{{4}}))?", s)
        if m:
            day = int(m.group(1))
            year = int(m.group(2)) if m.group(2) else now.year
            try:
                return datetime(year, month_num, day, tzinfo=timezone.utc)
            except ValueError:
                pass
    return now


def _extract_items_from_next_data(data: dict) -> list:
    """
    Рекурсивно ищем массив items в __NEXT_DATA__ структуре.
    Структура меняется от версии к версии, поэтому ищем гибко.
    """
    # Пробуем известные пути
    try:
        return data["props"]["pageProps"]["initialState"]["catalog"]["items"]
    except (KeyError, TypeError):
        pass

    try:
        return data["props"]["pageProps"]["items"]
    except (KeyError, TypeError):
        pass

    # Рекурсивный поиск первого большого массива с объектами у которых есть "id" и "title"
    def _search(obj, depth=0):
        if depth > 6:
            return None
        if isinstance(obj, list) and len(obj) > 2:
            if isinstance(obj[0], dict) and "id" in obj[0] and "title" in obj[0]:
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                result = _search(v, depth + 1)
                if result:
                    return result
        return None

    return _search(data) or []


class AvitoScraper:
    def __init__(self, db: AsyncSession):
        self.db = db
        proxy_url = (
            f"socks5://{settings.PROXY_USER}:{settings.PROXY_PASS}@{settings.PROXY_HOST}"
            if getattr(settings, "PROXY_HOST", None)
            else None
        )
        self.client = httpx.AsyncClient(
            timeout=30.0,
            proxy=proxy_url,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": "https://www.avito.ru/",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
            },
        )

    async def run(
        self,
        region_codes: Optional[list] = None,
        pages_per_region: int = 3,
    ) -> int:
        """
        Запускает парсинг Авито.
        region_codes — список кодов регионов (по умолчанию топ-10 по популярности).
        """
        if not region_codes:
            # Топ регионы по объёму предложений на Авито
            region_codes = ["50", "77", "23", "61", "78", "66", "63", "54", "74", "59"]

        saved = 0
        for code in region_codes:
            slug = REGION_SLUGS.get(code, "rossiya")
            print(f"[avito] Регион {code} ({slug})")
            for page in range(1, pages_per_region + 1):
                count = await self._scrape_page(slug, code, page)
                saved += count
                if count == 0:
                    break  # нет результатов — переходим к следующему региону
                await asyncio.sleep(2.5)  # пауза между страницами

        await self.client.aclose()
        return saved

    async def _scrape_page(self, slug: str, region_code: str, page: int) -> int:
        url = f"{AVITO_BASE}/{slug}/zemelnye_uchastki"
        params = {"p": page, "s": 104}  # s=104 — сортировка по дате

        try:
            resp = await self.client.get(url, params=params)
            if resp.status_code != 200:
                print(f"[avito] HTTP {resp.status_code} для {url}")
                return 0
            html = resp.text
        except Exception as e:
            print(f"[avito] Ошибка запроса {url}: {e}")
            return 0

        items = self._parse_page(html)
        if not items:
            print(f"[avito] Нет лотов на странице {page} для {slug}")
            return 0

        saved = 0
        for item_data in items:
            try:
                await self._upsert_lot(item_data, region_code)
                saved += 1
            except Exception as e:
                print(f"[avito] Ошибка обработки лота {item_data.get('id')}: {e}")

        await self.db.commit()
        print(f"[avito] {slug} стр.{page}: сохранено {saved}/{len(items)}")
        return saved

    def _parse_page(self, html: str) -> list:
        """Извлекаем листинги из HTML страницы Авито."""
        soup = BeautifulSoup(html, "lxml")

        # Способ 1: __NEXT_DATA__ (Next.js)
        next_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_tag and next_tag.string:
            try:
                data = json.loads(next_tag.string)
                items = _extract_items_from_next_data(data)
                if items:
                    return items
            except (json.JSONDecodeError, Exception):
                pass

        # Способ 2: window.__initialData__ (старый формат, иногда base64+gzip)
        match = re.search(r'window\.__initialData__\s*=\s*"([^"]{100,})"', html)
        if match:
            try:
                import base64
                import gzip
                raw = base64.b64decode(match.group(1))
                text = gzip.decompress(raw).decode("utf-8")
                data = json.loads(text)
                items = _extract_items_from_next_data(data)
                if items:
                    return items
            except Exception:
                pass

        # Способ 3: Парсим HTML-карточки напрямую
        return self._parse_html_cards(soup)

    def _parse_html_cards(self, soup: BeautifulSoup) -> list:
        """Fallback: парсим карточки из HTML напрямую по data-маркерам Авито."""
        items = []
        cards = soup.find_all("div", attrs={"data-marker": "item"})
        for card in cards:
            try:
                # id
                item_id = card.get("data-item-id") or card.get("id", "").replace("i", "")

                # title
                title_tag = card.find(attrs={"itemprop": "name"}) or \
                            card.find("h3") or card.find("h2")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # price
                price_tag = card.find(attrs={"data-marker": "item-price"}) or \
                            card.find(itemprop="price")
                price_text = price_tag.get_text(strip=True) if price_tag else ""
                price = self._parse_price(price_text)

                # url
                link = card.find("a", attrs={"data-marker": "item-title"}) or card.find("a", href=True)
                item_url = link["href"] if link else ""
                if item_url and not item_url.startswith("http"):
                    item_url = AVITO_BASE + item_url

                # location
                loc_tag = card.find(attrs={"data-marker": "item-address"}) or \
                          card.find(itemprop="address")
                location = loc_tag.get_text(strip=True) if loc_tag else ""

                # date
                date_tag = card.find(attrs={"data-marker": "item-date"})
                date_str = date_tag.get_text(strip=True) if date_tag else None

                if not item_id or not title:
                    continue

                items.append({
                    "id": item_id,
                    "title": title,
                    "price": price,
                    "url": item_url,
                    "address": location,
                    "date": date_str,
                })
            except Exception:
                continue
        return items

    def _parse_price(self, text: str) -> Optional[float]:
        """'1 500 000 ₽' → 1500000.0"""
        digits = re.sub(r"[^\d]", "", text)
        return float(digits) if digits else None

    def _extract_from_json_item(self, item: dict) -> dict:
        """Нормализуем JSON-объект Авито к нашему формату."""
        # Цена
        price = None
        price_data = item.get("priceDetailed") or item.get("price") or {}
        if isinstance(price_data, dict):
            price = price_data.get("value") or price_data.get("postfix")
            if isinstance(price, str):
                price = self._parse_price(price)
        elif isinstance(price_data, (int, float)):
            price = float(price_data)

        # URL
        url = item.get("url") or item.get("urlPath") or ""
        if url and not url.startswith("http"):
            url = AVITO_BASE + url

        # Адрес / местоположение
        loc = item.get("location") or {}
        address = ""
        if isinstance(loc, dict):
            address = loc.get("name") or loc.get("address") or ""
        elif isinstance(loc, str):
            address = loc

        # Дата
        date_str = None
        for k in ("date", "sortDate", "time", "createdAt"):
            if item.get(k):
                date_str = str(item[k])
                break

        return {
            "id": str(item.get("id", "")),
            "title": item.get("title") or item.get("name") or "",
            "price": price,
            "url": url,
            "address": address,
            "date": date_str,
        }

    async def _upsert_lot(self, raw_item: dict, region_code: str) -> None:
        # Нормализуем если пришёл JSON-объект Авито
        if "priceDetailed" in raw_item or "urlPath" in raw_item or "location" in raw_item:
            raw_item = self._extract_from_json_item(raw_item)

        item_id = str(raw_item.get("id", "")).strip()
        if not item_id:
            return

        external_id = f"avito_{item_id}"

        result = await self.db.execute(select(Lot).where(Lot.external_id == external_id))
        lot = result.scalar_one_or_none()

        title = raw_item.get("title") or ""
        area_sqm = _parse_area_from_title(title)
        price = raw_item.get("price")
        if isinstance(price, str):
            price = self._parse_price(price)

        published_at = _parse_published_at(raw_item.get("date"))

        from services.rubrics import normalize_vri_to_rubric
        purpose = _parse_purpose_from_title(title)

        if lot is None:
            lot = Lot(external_id=external_id, source=LotSource.AVITO)

        lot.title = title[:500]
        lot.start_price = float(price) if price else None
        lot.area_sqm = area_sqm
        lot.area_ha = round(area_sqm / 10000, 4) if area_sqm else None
        lot.price_per_sqm = round(float(price) / area_sqm, 2) if (price and area_sqm and area_sqm > 0) else None
        lot.land_purpose = purpose
        lot.land_purpose_raw = title
        lot.rubric_tg = normalize_vri_to_rubric(title)
        lot.status = LotStatus.ACTIVE
        lot.auction_type = None
        lot.region_code = region_code
        lot.address = (raw_item.get("address") or "")[:500]
        lot.lot_url = raw_item.get("url") or ""
        lot.published_at = published_at
        lot.raw_data = raw_item

        self.db.add(lot)
