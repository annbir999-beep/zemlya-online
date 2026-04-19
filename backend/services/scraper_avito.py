"""
Парсер Avito — земельные участки для сравнения рыночных цен.
Использует curl_cffi (Chrome TLS fingerprint) + резидентный прокси с ротацией.
"""
import asyncio
import re
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession as CurlSession
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.lot import Lot, LotSource, LotStatus, LandPurpose
from core.config import settings


AVITO_BASE = "https://www.avito.ru"

PROXY = "http://USER923303-zone-custom-region-RU:cb497d@global.rotgb.711proxy.com:10000"
PROXIES = {"https": PROXY, "http": PROXY}

MAX_RETRIES = 5

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
    t = title.lower()
    m = re.search(r"([\d.,]+)\s*га\b", t)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) * 10000
        except ValueError:
            pass
    m = re.search(r"([\d.,]+)\s*сот", t)
    if m:
        try:
            return float(m.group(1).replace(",", ".")) * 100
        except ValueError:
            pass
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
        m = re.match(rf"(\d+)\s+{month_name}(?:\s+(\d{{4}}))?$", s)
        if m:
            day = int(m.group(1))
            year = int(m.group(2)) if m.group(2) else now.year
            try:
                return datetime(year, month_num, day, tzinfo=timezone.utc)
            except ValueError:
                pass
    return now


class AvitoScraper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        region_codes: Optional[list] = None,
        pages_per_region: int = 3,
    ) -> int:
        if not region_codes:
            region_codes = ["50", "77", "23", "61", "78", "66", "63", "54", "74", "59"]

        saved = 0
        for code in region_codes:
            slug = REGION_SLUGS.get(code, "rossiya")
            print(f"[avito] Регион {code} ({slug})")
            for p in range(1, pages_per_region + 1):
                count = await self._scrape_page(slug, code, p)
                saved += count
                if count == 0:
                    break
                await asyncio.sleep(2.0)

        return saved

    async def _fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch URL with retry until we get real listing HTML (proxy rotates IPs)."""
        for attempt in range(MAX_RETRIES):
            try:
                async with CurlSession(impersonate="chrome124") as s:
                    r = await s.get(url, proxies=PROXIES, timeout=90, verify=False)
                    if r.status_code == 200 and "data-item-id" in r.text:
                        return r.text
                    print(f"[avito] Попытка {attempt+1}: статус={r.status_code}, нет listings, retry...")
            except Exception as e:
                print(f"[avito] Попытка {attempt+1} ошибка: {type(e).__name__}: {str(e)[:80]}")
            await asyncio.sleep(2.0)
        return None

    async def _scrape_page(self, slug: str, region_code: str, page_num: int) -> int:
        url = f"{AVITO_BASE}/{slug}/zemelnye_uchastki?s=104"
        if page_num > 1:
            url += f"&p={page_num}"

        html = await self._fetch_with_retry(url)
        if not html:
            print(f"[avito] Нет лотов на стр.{page_num} для {slug}")
            return 0

        items = self._parse_html(html)
        if not items:
            print(f"[avito] Парсинг дал 0 лотов для {slug} стр.{page_num}")
            return 0

        saved = 0
        for item_data in items:
            try:
                await self._upsert_lot(item_data, region_code)
                saved += 1
            except Exception as e:
                print(f"[avito] Ошибка лота {item_data.get('id')}: {e}")

        await self.db.commit()
        print(f"[avito] {slug} стр.{page_num}: сохранено {saved}/{len(items)}")
        return saved

    def _parse_html(self, html: str) -> list:
        soup = BeautifulSoup(html, "html.parser")

        cards = (
            soup.find_all("div", attrs={"data-marker": "item"}) or
            soup.find_all("article", attrs={"data-marker": "item"})
        )
        if cards:
            result = self._parse_cards(cards)
            if result:
                print(f"[avito] DOM: {len(result)} лотов")
                return result

        title = soup.title.string if soup.title else "?"
        print(f"[avito] Не распарсилось. Title: {title!r}")
        return []

    def _parse_cards(self, cards) -> list:
        items = []
        for card in cards:
            try:
                item_id = card.get("data-item-id", "")

                title_tag = card.find(attrs={"itemprop": "name"}) or card.find("h3") or card.find("h2")
                title = title_tag.get_text(strip=True) if title_tag else ""

                # Цена — сначала itemprop content (числовое), потом текст маркера
                price_tag = card.find(attrs={"itemprop": "price"})
                if price_tag and price_tag.get("content"):
                    price = self._parse_price(price_tag["content"])
                else:
                    price_marker = card.find(attrs={"data-marker": "item-price"})
                    price = self._parse_price(price_marker.get_text(strip=True)) if price_marker else None

                # URL
                link = card.find("a", attrs={"data-marker": "item-title"}) or card.find("a", href=True)
                if link:
                    href = link.get("href", "")
                    url = href if href.startswith("http") else AVITO_BASE + href
                else:
                    url = ""

                # Адрес
                addr_tag = card.find(attrs={"data-marker": "item-address"})
                if not addr_tag:
                    addr_tag = card.find(attrs={"itemprop": "address"})
                address = addr_tag.get_text(strip=True) if addr_tag else ""

                # Дата
                date_tag = card.find(attrs={"data-marker": "item-date"})
                date_str = date_tag.get_text(strip=True) if date_tag else None

                if not item_id or not title:
                    continue

                items.append({
                    "id": item_id,
                    "title": title,
                    "price": price,
                    "url": url,
                    "address": address,
                    "date": date_str,
                })
            except Exception:
                continue
        return items

    def _parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        digits = re.sub(r"[^\d]", "", str(text))
        return float(digits) if digits else None

    async def _upsert_lot(self, raw_item: dict, region_code: str) -> None:
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
        purpose = _parse_purpose_from_title(title)

        from services.rubrics import normalize_vri_to_rubric

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
