"""
Парсер torgi.gov.ru — официальный API государственных торгов.
Документация: https://torgi.gov.ru/new/public/lots/api/swagger-ui/index.html

Основной эндпоинт: GET /new/public/lots/api/v1/lots
Параметры:
  - lotStatus: PUBLISHED (активные)
  - biddType: 178FZ (Аукционы по 178-ФЗ о приватизации) | ZK (Земельный кодекс)
  - category: ZU (Земельный участок)
  - page, size
"""
import asyncio
import httpx
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from models.lot import Lot, LotStatus, LandPurpose, AuctionType, LotSource, AuctionForm, DealType, AreaDiscrepancy, ResaleType
from services.rubrics import normalize_vri_to_rubric
from core.config import settings


TORGI_BASE = "https://torgi.gov.ru/new/api/public"

# Маппинг subjectRFCode -> название региона
REGION_MAP = {
    "01": "Адыгея", "02": "Башкортостан", "03": "Бурятия", "04": "Алтай",
    "05": "Дагестан", "06": "Ингушетия", "07": "Кабардино-Балкария", "08": "Калмыкия",
    "09": "Карачаево-Черкесия", "10": "Карелия", "11": "Коми", "12": "Марий Эл",
    "13": "Мордовия", "14": "Саха (Якутия)", "15": "Северная Осетия", "16": "Татарстан",
    "17": "Тыва", "18": "Удмуртия", "19": "Хакасия", "20": "Чечня",
    "21": "Чувашия", "22": "Алтайский край", "23": "Краснодарский край",
    "24": "Красноярский край", "25": "Приморский край", "26": "Ставропольский край",
    "27": "Хабаровский край", "28": "Амурская область", "29": "Архангельская область",
    "30": "Астраханская область", "31": "Белгородская область", "32": "Брянская область",
    "33": "Владимирская область", "34": "Волгоградская область", "35": "Вологодская область",
    "36": "Воронежская область", "37": "Ивановская область", "38": "Иркутская область",
    "39": "Калининградская область", "40": "Калужская область", "41": "Камчатский край",
    "42": "Кемеровская область", "43": "Кировская область", "44": "Костромская область",
    "45": "Курганская область", "46": "Курская область", "47": "Ленинградская область",
    "48": "Липецкая область", "49": "Магаданская область", "50": "Московская область",
    "51": "Мурманская область", "52": "Нижегородская область", "53": "Новгородская область",
    "54": "Новосибирская область", "55": "Омская область", "56": "Оренбургская область",
    "57": "Орловская область", "58": "Пензенская область", "59": "Пермский край",
    "60": "Псковская область", "61": "Ростовская область", "62": "Рязанская область",
    "63": "Самарская область", "64": "Саратовская область", "65": "Сахалинская область",
    "66": "Свердловская область", "67": "Смоленская область", "68": "Тамбовская область",
    "69": "Тверская область", "70": "Томская область", "71": "Тульская область",
    "72": "Тюменская область", "73": "Ульяновская область", "74": "Челябинская область",
    "75": "Забайкальский край", "76": "Ярославская область", "77": "Москва",
    "78": "Санкт-Петербург", "79": "Еврейская АО", "83": "Ненецкий АО",
    "86": "Ханты-Мансийский АО", "87": "Чукотский АО", "89": "Ямало-Ненецкий АО",
    "91": "Крым", "92": "Севастополь",
}

# Ключевые слова -> LandPurpose (ищем подстрокой в нижнем регистре)
PURPOSE_KEYWORDS: list[tuple[str, LandPurpose]] = [
    # ИЖС
    ("индивидуального жилищного строительства", LandPurpose.IZhS),
    ("ижс", LandPurpose.IZhS),
    ("жилищное строительство", LandPurpose.IZhS),
    ("малоэтажн", LandPurpose.IZhS),
    # СНТ / дача
    ("садоводств", LandPurpose.SNT),
    ("огородничеств", LandPurpose.SNT),
    ("дачн", LandPurpose.SNT),
    ("снт", LandPurpose.SNT),
    ("днп", LandPurpose.SNT),
    # ЛПХ
    ("личного подсобного хозяйства", LandPurpose.LPKh),
    ("лпх", LandPurpose.LPKh),
    ("подсобн", LandPurpose.LPKh),
    # Сельхоз
    ("сельскохозяйственного назначения", LandPurpose.AGRICULTURAL),
    ("сельскохоз", LandPurpose.AGRICULTURAL),
    ("фермерского хозяйства", LandPurpose.AGRICULTURAL),
    ("пашн", LandPurpose.AGRICULTURAL),
    ("растениеводств", LandPurpose.AGRICULTURAL),
    ("животноводств", LandPurpose.AGRICULTURAL),
    ("для сельскохозяйств", LandPurpose.AGRICULTURAL),
    # Коммерция
    ("коммерческого использования", LandPurpose.COMMERCIAL),
    ("объектов торговли", LandPurpose.COMMERCIAL),
    ("торговл", LandPurpose.COMMERCIAL),
    ("офисн", LandPurpose.COMMERCIAL),
    ("деловой", LandPurpose.COMMERCIAL),
    ("гостиниц", LandPurpose.COMMERCIAL),
    # Промышленность
    ("промышленност", LandPurpose.INDUSTRIAL),
    ("производственн", LandPurpose.INDUSTRIAL),
    ("складск", LandPurpose.INDUSTRIAL),
    ("транспорт", LandPurpose.INDUSTRIAL),
    ("энергетик", LandPurpose.INDUSTRIAL),
    ("земли промышленн", LandPurpose.INDUSTRIAL),
    # Лес
    ("лесного фонда", LandPurpose.FOREST),
    ("лесн", LandPurpose.FOREST),
    # Вода
    ("водного фонда", LandPurpose.WATER),
    ("водн", LandPurpose.WATER),
    # Спец
    ("особо охраняем", LandPurpose.SPECIAL_PURPOSE),
    ("запаса", LandPurpose.SPECIAL_PURPOSE),
]


def _parse_purpose(category_str: str, vri_str: str) -> LandPurpose:
    combined = ((vri_str or "") + " " + (category_str or "")).lower()
    for keyword, purpose in PURPOSE_KEYWORDS:
        if keyword in combined:
            return purpose
    return LandPurpose.OTHER


def _parse_auction_type(bidding_form: str) -> AuctionType:
    raw = (bidding_form or "").lower()
    if "аренд" in raw:
        return AuctionType.RENT
    if "приватизац" in raw:
        return AuctionType.PRIVATIZATION
    return AuctionType.SALE


def _parse_auction_form(form_str: str) -> Optional[AuctionForm]:
    raw = (form_str or "").lower()
    if "конкурс" in raw:
        return AuctionForm.TENDER
    if "публичн" in raw:
        return AuctionForm.PUBLIC_OFFER
    if "без торгов" in raw or "без проведения" in raw:
        return AuctionForm.WITHOUT_AUCTION
    if "аукцион" in raw:
        return AuctionForm.AUCTION
    return None


def _parse_deal_type(deal_str: str) -> Optional[DealType]:
    raw = (deal_str or "").lower()
    if "аренд" in raw:
        return DealType.LEASE
    if "безвозмезд" in raw:
        return DealType.FREE_USE
    if "оперативн" in raw:
        return DealType.OPERATIONAL
    if "собственност" in raw or "купл" in raw:
        return DealType.OWNERSHIP
    return None


def _calc_area_discrepancy(area_tg: Optional[float], area_kn: Optional[float]) -> AreaDiscrepancy:
    if not area_kn:
        return AreaDiscrepancy.NO_KN
    if not area_tg:
        return AreaDiscrepancy.NO_KN
    diff_pct = abs(area_tg - area_kn) / area_tg * 100
    if diff_pct < 1:
        return AreaDiscrepancy.MATCH
    if diff_pct < 10:
        return AreaDiscrepancy.MINOR
    return AreaDiscrepancy.MAJOR


SUBLEASE_KEYWORDS = ["субаренд"]
ASSIGNMENT_KEYWORDS = ["переуступ", "уступк", "цессия", "третьим лицам"]


def _detect_sublease_assignment(raw: dict, title: str, description: str) -> tuple:
    """Ищем ключевые слова в тексте лота и атрибутах — возвращает (sublease, assignment)."""
    texts = [
        title or "",
        description or "",
        raw.get("lotDescription", "") or "",
    ]
    for attr in (raw.get("noticeAttributes") or []) + (raw.get("attributes") or []):
        val = attr.get("value") or attr.get("characteristicValue") or ""
        if isinstance(val, str):
            texts.append(val)
        texts.append(attr.get("fullName", "") or "")
    combined = " ".join(texts).lower()
    sublease = any(kw in combined for kw in SUBLEASE_KEYWORDS)
    assignment = any(kw in combined for kw in ASSIGNMENT_KEYWORDS)
    return sublease, assignment


def _parse_status(lot_status: str) -> LotStatus:
    mapping = {
        "PUBLISHED": LotStatus.ACTIVE,
        "APPLICATIONS_SUBMISSION": LotStatus.ACTIVE,
        "AUCTION_IN_PROGRESS": LotStatus.ACTIVE,
        "SUMMARIZING": LotStatus.COMPLETED,
        "COMPLETED": LotStatus.COMPLETED,
        "CANCELLED": LotStatus.CANCELLED,
        "DRAFT": LotStatus.UPCOMING,
    }
    return mapping.get(lot_status, LotStatus.ACTIVE)


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # torgi.gov возвращает ISO 8601
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class TorgiGovScraper:
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
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9",
                "Referer": "https://torgi.gov.ru/new/public/lots/lot",
            },
        )

    async def run(self) -> int:
        """Запускает полный цикл парсинга. Возвращает кол-во сохранённых/обновлённых лотов."""
        saved = 0
        page = 0
        size = 50
        total_pages = None

        while True:
            lots_data, total_pages_resp = await self._fetch_page(page, size)
            if total_pages is None and total_pages_resp is not None:
                total_pages = total_pages_resp
                print(f"[torgi] Всего страниц: {total_pages}")

            if not lots_data:
                break

            for raw_lot in lots_data:
                try:
                    count = await self._upsert_lot(raw_lot)
                    saved += count
                except Exception as e:
                    print(f"[torgi] Ошибка обработки лота {raw_lot.get('id')}: {e}")

            await asyncio.sleep(settings.TORGI_GOV_DELAY)

            if total_pages is not None:
                if page >= total_pages - 1:
                    break
            elif len(lots_data) < size:
                break
            page += 1

        await self.client.aclose()
        return saved

    async def _fetch_page(self, page: int, size: int) -> tuple:
        # Новый API принимает lotStatus как Set — передаём списком
        params = [
            ("lotStatus", "PUBLISHED"),
            ("lotStatus", "APPLICATIONS_SUBMISSION"),
            ("catCode", "301"),
            ("byFirstVersion", "true"),
            ("page", page),
            ("size", size),
            ("sort", "firstVersionPublicationDate,desc"),
        ]
        try:
            resp = await self.client.get(f"{TORGI_BASE}/lotcards/search", params=params)
            print(f"[torgi] HTTP статус: {resp.status_code}, страница {page}")
            resp.raise_for_status()
            data = resp.json()
            total = data.get("totalElements", "?")
            total_pages = data.get("totalPages")
            print(f"[torgi] Лотов: {total}, страниц: {total_pages}")
            return data.get("content", []), total_pages
        except Exception as e:
            print(f"[torgi] HTTP ошибка: {type(e).__name__}: {e}")
            try:
                print(f"[torgi] Ответ сервера: {resp.text[:500]}")
            except Exception:
                pass
            return [], None

    async def _upsert_lot(self, raw: dict) -> int:
        external_id = f"torgi_{raw['id']}"

        # Проверяем — уже есть?
        result = await self.db.execute(select(Lot).where(Lot.external_id == external_id))
        lot = result.scalar_one_or_none()

        # Извлекаем данные
        # Новый API: characteristics — массив объектов с полем characteristicValue
        char_list = raw.get("characteristics", [])
        if isinstance(char_list, dict):
            char_list = char_list.get("items", [])
        bidding = raw.get("biddForm", {})

        def get_char(codes):
            """Получить значение характеристики по коду."""
            for c in char_list:
                if c.get("code") in codes:
                    val = c.get("characteristicValue") or c.get("value", "")
                    # Multiselect возвращает список — берём первый элемент
                    if isinstance(val, list):
                        val = val[0].get("name", "") if val and isinstance(val[0], dict) else (str(val[0]) if val else "")
                    return val or ""
            return ""

        area_sqm = None
        area_raw = get_char(["SquareZU", "AREA", "ZU_AREA"])
        if area_raw:
            try:
                area_sqm = float(str(area_raw).replace(",", ".").replace(" ", ""))
            except (ValueError, TypeError):
                pass

        # Регион из subjectRFCode
        subject_code = str(raw.get("subjectRFCode", "")).zfill(2)
        region_name = REGION_MAP.get(subject_code, "")
        region_code = subject_code

        start_price = raw.get("priceMin") or raw.get("nmc")
        try:
            start_price = float(start_price) if start_price else None
        except (ValueError, TypeError):
            start_price = None

        address = ""
        lat = None
        lng = None

        purpose_raw = raw.get("lotName", "") or raw.get("subject", {}).get("name", "")
        # Категория земель — ищем по нескольким возможным кодам
        category_raw = get_char(["CategoryOfLand", "CATEGORY", "ZU_CATEGORY", "landCategory", "LandCategory"])
        vri_raw = get_char(["PermittedUse", "VRI", "ZU_VRI"])

        # Извлекаем ЭТП — поле etpCode ("ETP_SBAST", "ROSELTORG" и др.)
        ETP_NAMES: dict = {
            "ETP_SBAST": "Сбербанк АСТ",
            "ROSELTORG": "Росэлторг",
            "ZAKAZRF": "ЕЭТП",
            "RTS": "РТС-тендер",
            "AGZRT": "АГЗ РТ",
            "TEKTORG": "ТЭК-Торг",
            "ETPGPB": "ЭТП ГПБ",
        }
        etp_code = raw.get("etpCode") or ""
        etp_name = ETP_NAMES.get(etp_code, etp_code) if etp_code else None

        # Извлекаем задаток %
        deposit_val = raw.get("deposit")
        deposit_pct = None
        if deposit_val and start_price and start_price > 0:
            try:
                deposit_pct = round(float(deposit_val) / start_price * 100, 2)
            except (ValueError, TypeError):
                pass

        # Извлекаем форму проведения, вид сделки и раздел torgi.gov
        procedure = raw.get("procedure", {})
        form_str = procedure.get("name", "") or bidding.get("name", "")
        deal_str = raw.get("dealType", {}).get("name", "") or ""
        bidd_type = raw.get("biddType", {}) or {}
        section_name = bidd_type.get("name", "") or ""  # "Аренда и продажа земельных участков"

        # Переуступка — 3 уровня
        resale_raw = (raw.get("resale") or raw.get("cessation") or "").lower()
        if "согласов" in resale_raw:
            resale_type = ResaleType.WITH_APPROVAL
        elif "уведом" in resale_raw:
            resale_type = ResaleType.WITH_NOTICE
        elif resale_raw and resale_raw not in ("нет", "no", "false", "0"):
            resale_type = ResaleType.YES
        elif resale_raw in ("нет", "no", "false", "0"):
            resale_type = ResaleType.NO
        else:
            resale_type = None

        # Номер извещения
        notice_number = raw.get("noticeNumber") or raw.get("noticeNum") or raw.get("eid")

        if lot is None:
            lot = Lot(external_id=external_id, source=LotSource.TORGI_GOV)

        lot.title = (raw.get("lotName") or raw.get("subject", {}).get("name", ""))[:500]
        lot.description = raw.get("lotDescription", "")
        cadastral_raw = get_char(["CadastralNumber", "CADASTRAL_NUM", "ZU_CADASTRAL"])
        lot.cadastral_number = cadastral_raw or raw.get("cadastralNumber") or None
        lot.notice_number = str(notice_number)[:200] if notice_number else None
        lot.start_price = start_price
        lot.deposit = float(deposit_val) if deposit_val else None
        lot.deposit_pct = deposit_pct
        lot.area_sqm = area_sqm
        lot.area_ha = round(area_sqm / 10000, 4) if area_sqm else None
        lot.price_per_sqm = round(start_price / area_sqm, 2) if (start_price and area_sqm and area_sqm > 0) else None
        lot.land_purpose = _parse_purpose(purpose_raw, vri_raw)
        lot.land_purpose_raw = f"{purpose_raw} / {vri_raw}".strip(" /")
        lot.category_tg = category_raw[:300] if category_raw else None
        lot.vri_tg = vri_raw[:500] if vri_raw else None
        lot.rubric_tg = normalize_vri_to_rubric(vri_raw or purpose_raw)
        # auction_type — определяем по deal_type и разделу
        deal_type_parsed = _parse_deal_type(deal_str)
        if deal_type_parsed == DealType.LEASE:
            auction_type = AuctionType.RENT
        elif "приватизац" in (deal_str or "").lower() or "приватизац" in section_name.lower():
            auction_type = AuctionType.PRIVATIZATION
        else:
            auction_type = AuctionType.SALE
        lot.auction_type = auction_type
        lot.auction_form = _parse_auction_form(form_str)
        lot.deal_type = deal_type_parsed
        lot.section_tg = section_name[:500] if section_name else None
        lot.etp = etp_name[:200] if etp_name else None
        lot.resale_type = resale_type
        sublease, assignment = _detect_sublease_assignment(
            raw, lot.title or "", lot.description or ""
        )
        lot.sublease_allowed = sublease if (sublease or assignment) else None
        lot.assignment_allowed = assignment if (sublease or assignment) else None
        lot.region_code = str(region_code)
        lot.region_name = region_name
        lot.address = address
        lot.organizer_name = raw.get("organizer", {}).get("name", "")
        lot.lot_url = f"https://torgi.gov.ru/new/public/lots/lot/{raw['id']}"
        lot.auction_start_date = _parse_datetime(raw.get("auctionStartDate"))
        lot.auction_end_date = _parse_datetime(
            raw.get("auctionEndDate") or raw.get("auctionStartDate") or raw.get("biddEndTime")
        )
        lot.submission_start = _parse_datetime(raw.get("biddStartTime") or raw.get("submissionStartDate"))
        lot.submission_end = _parse_datetime(raw.get("biddEndTime") or raw.get("submissionEndDate"))

        api_status = _parse_status(raw.get("lotStatus", "PUBLISHED"))
        now_utc = datetime.now(timezone.utc)
        if api_status == LotStatus.CANCELLED:
            lot.status = LotStatus.CANCELLED
        elif lot.auction_end_date and lot.auction_end_date < now_utc:
            lot.status = LotStatus.COMPLETED
        elif lot.auction_start_date and lot.auction_start_date > now_utc:
            lot.status = LotStatus.UPCOMING
        else:
            lot.status = api_status
        lot.published_at = _parse_datetime(raw.get("firstVersionPublicationDate"))
        lot.raw_data = raw

        if lat and lng:
            try:
                lot.location = from_shape(Point(float(lng), float(lat)), srid=4326)
            except (ValueError, TypeError):
                pass

        self.db.add(lot)
        await self.db.flush()
        return 1
