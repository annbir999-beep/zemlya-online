"""Фотографии участков из извещений torgi.gov.

В `raw_data.lotImages` карточки лота лежат идентификаторы файлов, а сами файлы
отдаёт `https://torgi.gov.ru/new/file-store/v1/{id}` — тот же файл-стор, откуда
качаются PDF извещений. Картинки есть практически у каждого лота: у части это
фото участка с земли, у большинства — спутниковый снимок с обведённой границей
из кадастра (покупателю он даже полезнее: видно форму, соседей и подъезд).

Отдавать браузеру прямую ссылку на torgi.gov нельзя: их файл-стор доступен не
отовсюду (мы сами ходим через прокси), и мы бы стали заложниками их аптайма.
Поэтому качаем сами и держим дисковый кэш — файл по id неизменен, инвалидация
не нужна.

Кэш ленивый: тянем картинку в момент первого запроса, а не пребилдом на все
12 тысяч лотов — на диске VPS свободно около 6 ГБ, а полный прогрев занял бы
больше двух.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx

from core.config import settings

CACHE_DIR = Path(os.getenv("LOT_PHOTO_CACHE", "/app/media/lot_photos"))
FILE_URL = "https://torgi.gov.ru/new/file-store/v1/{file_id}"

# Больше десятка картинок на лот не бывает; ограничение отсекает попытки
# перебирать индексы и заодно бережёт диск.
MAX_PHOTOS = 12

# Организаторы кладут в извещение снимки прямо с фотоаппарата — попадаются по
# 5-6 МБ. Отдавать такое в браузер нельзя: лот с пятью фото — под 30 МБ трафика,
# и дисковый кэш на VPS кончится за пару сотен лотов. Поэтому пересжимаем.
# Набор ширин фиксирован: произвольный ?w= позволил бы забить диск вариантами.
SIZES = {320: 78, 1400: 82}   # ширина -> качество JPEG
DEFAULT_SIZE = 1400

_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG": "image/png",
    b"GIF8": "image/gif",
}


def photo_ids(raw_data) -> list[str]:
    """Идентификаторы картинок лота в порядке из извещения."""
    if not isinstance(raw_data, dict):
        return []
    ids = raw_data.get("lotImages")
    if not isinstance(ids, list):
        return []
    return [str(i) for i in ids if isinstance(i, (str, int)) and str(i).strip()][:MAX_PHOTOS]


def sniff_content_type(blob: bytes) -> Optional[str]:
    """Тип по сигнатуре файла: torgi.gov отдаёт всё как octet-stream."""
    for sig, ctype in _SIGNATURES.items():
        if blob.startswith(sig):
            return ctype
    return None


def _cache_path(file_id: str, width: int) -> Path:
    # Раскладываем по ширине и подпапкам: 12 тысяч файлов в одном каталоге
    # тормозят любой обход директории.
    return CACHE_DIR / str(width) / file_id[:2] / file_id


def _shrink(blob: bytes, width: int) -> bytes:
    """Ужимает под нужную ширину. При ошибке возвращает исходник как есть."""
    import io

    from PIL import Image, ImageOps

    try:
        img = Image.open(io.BytesIO(blob))
        img = ImageOps.exif_transpose(img)   # снимки с телефона бывают повёрнуты
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        if img.width > width:
            height = round(img.height * width / img.width)
            img = img.resize((width, height), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=SIZES[width], optimize=True, progressive=True)
        return out.getvalue()
    except Exception:
        return blob


def _write_atomic(path: Path, blob: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Через временный файл: два параллельных запроса на одну картинку иначе
        # оставят на диске обрезанный файл, и он закэшируется битым.
        tmp = path.with_name(path.name + ".part")
        tmp.write_bytes(blob)
        tmp.replace(path)
    except OSError:
        pass  # диск кончился или нет прав — отдать картинку это не мешает


async def fetch_photo(file_id: str, width: int = DEFAULT_SIZE) -> Optional[tuple[bytes, str]]:
    """Байты картинки нужной ширины и её content-type. None — если не вышло."""
    if width not in SIZES:
        width = DEFAULT_SIZE

    path = _cache_path(file_id, width)
    if path.exists():
        blob = path.read_bytes()
        return blob, (sniff_content_type(blob) or "image/jpeg")

    if not settings.PROXY_HOST:
        return None
    proxy = f"http://{settings.PROXY_USER}:{settings.PROXY_PASS}@{settings.PROXY_HOST}"
    try:
        async with httpx.AsyncClient(
            proxy=proxy, verify=False, timeout=60, follow_redirects=True
        ) as client:
            resp = await client.get(FILE_URL.format(file_id=file_id))
        if resp.status_code != 200 or not resp.content:
            return None
    except Exception:
        return None

    if not sniff_content_type(resp.content):
        # Не картинка — в извещении по этому id может лежать что угодно.
        return None

    # Оригинал не храним: он бывает по 6 МБ, а нужен только как заготовка.
    # Заодно раскладываем сразу обе ширины — второй заход не полезет в сеть.
    blob = _shrink(resp.content, width)
    _write_atomic(path, blob)
    for other in SIZES:
        if other != width:
            _write_atomic(_cache_path(file_id, other), _shrink(resp.content, other))

    return blob, (sniff_content_type(blob) or "image/jpeg")
