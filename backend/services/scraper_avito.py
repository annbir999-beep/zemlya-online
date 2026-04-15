"""
Парсер Avito — земельные участки для сравнения рыночных цен.

Использует Playwright (headless Chromium) — Авито блокирует обычные HTTP-запросы.
Playwright эмулирует реальный браузер и обходит anti-bot защиту.

Данные сохраняются в таблицу lots с source=AVITO.
"""
import asyncio
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.lot import Lot, LotSource, LotStatus, LandPurpose
from core.config import settings


AVITO_BASE = "https://www.avito.ru"

# Прокси для обхода блокировки Авито (datacenter IP блокируется)
PROXY_SERVER = "socks5://45.139.110.68:8000"
PROXY_USERNAME = "Q5fu2o"
PROXY_PASSWORD = "3KNkAA"

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



class AvitoScraper:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def run(
        self,
        region_codes: Optional[list] = None,
        pages_per_region: int = 3,
    ) -> int:
        """
        Запускает парсинг Авито через Playwright.
        region_codes — список кодов регионов (по умолчанию топ-10 по популярности).
        """
        if not region_codes:
            region_codes = ["50", "77", "23", "61", "78", "66", "63", "54", "74", "59"]

        from playwright.async_api import async_playwright

        saved = 0
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
                proxy={"server": PROXY_SERVER},
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="ru-RU",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            for code in region_codes:
                slug = REGION_SLUGS.get(code, "rossiya")
                print(f"[avito] Регион {code} ({slug})")
                for p in range(1, pages_per_region + 1):
                    count = await self._scrape_page(page, slug, code, p)
                    saved += count
                    if count == 0:
                        break
                    await asyncio.sleep(2.0)

            await browser.close()
        return saved

    async def _scrape_page(self, page, slug: str, region_code: str, page_num: int) -> int:
        """Парсим одну страницу Авито через Playwright."""
        url = f"{AVITO_BASE}/{slug}/zemelnye_uchastki?s=104"
        if page_num > 1:
            url += f"&p={page_num}"

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)  # ждём рендер JS
            html = await page.content()
        except Exception as e:
            print(f"[avito] Playwright ошибка {url}: {e}")
            return 0

        items = self._parse_html(html)
        if not items:
            print(f"[avito] Нет лотов на странице {page_num} для {slug}")
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
        """Парсим HTML после рендера Playwright — данные в __NEXT_DATA__ или DOM."""
        soup = BeautifulSoup(html, "lxml")

        # Способ 1: __NEXT_DATA__
        next_tag = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_tag and next_tag.string:
            try:
                data = json.loads(next_tag.string)
                items = self._extract_items(data)
                if items:
                    print(f"[avito] __NEXT_DATA__: {len(items)} лотов")
                    return items
            except Exception as e:
                print(f"[avito] __NEXT_DATA__ ошибка: {e}")

        # Способ 2: data-маркеры в DOM
        cards = (
            soup.find_all("div", attrs={"data-marker": "item"}) or
            soup.find_all("article", attrs={"data-marker": "item"})
        )
        if cards:
            print(f"[avito] DOM cards: {len(cards)}")
            return self._parse_cards(cards)

        title = soup.title.string if soup.title else "?"
        print(f"[avito] Не распарсилось. Title: {title!r}")
        return []

    def _extract_items(self, data: dict) -> list:
        """Рекурсивно ищем items[] в __NEXT_DATA__."""
        def search(obj, depth=0):
            if depth > 8:
                return None
            if isinstance(obj, list) and len(obj) > 0 and isinstance(obj[0], dict):
                if "id" in obj[0] and ("title" in obj[0] or "name" in obj[0]):
                    return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    r = search(v, depth + 1)
                    if r:
                        return r
            return None
        return search(data) or []

    def _parse_cards(self, cards) -> list:
        items = []
        for card in cards:
            try:
                item_id = card.get("data-item-id", "")
                title_tag = card.find(attrs={"itemprop": "name"}) or card.find("h3") or card.find("h2")
                title = title_tag.get_text(strip=True) if title_tag else ""
                price_tag = card.find(attrs={"data-marker": "item-price"})
                price = self._parse_price(price_tag.get_text(strip=True)) if price_tag else None
                link = card.find("a", attrs={"data-marker": "item-title"}) or card.find("a", href=True)
                url = (AVITO_BASE + link["href"]) if link and not link["href"].startswith("http") else (link["href"] if link else "")
                if not item_id or not title:
                    continue
                items.append({"id": item_id, "title": title, "price": price, "url": url, "address": "", "date": None})
            except Exception:
                continue
        return items

    def _parse_price(self, text: str) -> Optional[float]:
        """'1 500 000 ₽' → 1500000.0"""
        digits = re.sub(r"[^\d]", "", text)
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
