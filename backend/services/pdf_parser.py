"""
Загрузка и парсинг документов лотов torgi.gov (PDF, DOC, DOCX).

Документы прикрепляются через массив noticeAttachments в детальном API.
Каждый элемент содержит fileId, fileName, attachmentTypeCode/Name (последние
часто пустые).

Алгоритм классификации (приоритет: код → имя файла):
- notice         — Извещение (описание участка, локация, ВРИ, обременения)
- tech_conditions — ТУ (электричество/газ/вода)
- contract       — Проект договора (переуступка, субаренда, штрафы)
- scheme         — СРЗУ (мало текста, опционально)
"""
import io
import re
from typing import Optional


# Ключевые слова для классификации (искать в любом из: code, type_name, file_name)
TYPE_KEYWORDS = {
    "notice": [
        "notice_document", "notice ", "извещени", "оповещени",
    ],
    "tech_conditions": [
        "technical", "tc_document", "tech_conditions",
        "техническ", "тех условия", "ту ",
    ],
    "contract": [
        "draft_contract", "contract", "договор", "проект дог",
        "договора", "проекта договора", "перенайм",
    ],
    "scheme": [
        "scheme", "срзу", "схема расположен",
    ],
}


def classify_attachment(att: dict) -> Optional[str]:
    """Возвращает наш ключ типа документа (notice/tech_conditions/contract/scheme) или None."""
    code = (att.get("attachmentTypeCode") or "").lower()
    name = (att.get("attachmentTypeName") or "").lower()
    file_name = (att.get("fileName") or "").lower()
    haystack = f"{code} | {name} | {file_name}"

    for our_type, keywords in TYPE_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack:
                return our_type
    return None


SUPPORTED_EXTENSIONS = (".pdf", ".pdf.zip", ".doc", ".docx", ".rtf")


def get_file_ext(file_name: str) -> str:
    """Возвращает расширение файла в нижнем регистре."""
    fname = (file_name or "").lower().strip()
    for ext in SUPPORTED_EXTENSIONS:
        if fname.endswith(ext):
            return ext
    # Может быть без расширения, или необычное расширение
    m = re.search(r"\.([a-z0-9]{1,5})$", fname)
    return f".{m.group(1)}" if m else ""


def select_best_attachments(attachments: list[dict]) -> dict[str, dict]:
    """
    Из массива noticeAttachments выбирает по 1 документу каждого нашего типа.
    Если для типа "contract"/"notice" не нашлось по классификатору — берём
    дополнительно первый файл с подходящим именем.
    """
    result: dict[str, dict] = {}
    if not attachments:
        return result

    # Первый проход — точные совпадения по классификатору
    for att in attachments:
        if att.get("inactive"):
            continue
        ext = get_file_ext(att.get("fileName", ""))
        if ext not in SUPPORTED_EXTENSIONS:
            continue
        our_type = classify_attachment(att)
        if our_type and our_type not in result:
            result[our_type] = att

    return result


async def download_file(client, file_id: str) -> Optional[bytes]:
    """Скачивает файл по fileId через прокси-клиент скрапера."""
    if not file_id:
        return None
    url = f"https://torgi.gov.ru/new/file-store/v1/{file_id}"
    try:
        resp = await client.get(url, timeout=90)
        if resp.status_code != 200:
            return None
        return resp.content
    except Exception:
        return None


# Backward-compat alias
download_pdf = download_file


def _extract_pdf(content: bytes, max_pages: int = 30) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            chunks = []
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    break
                try:
                    text = page.extract_text() or ""
                    chunks.append(text)
                except Exception:
                    pass
            return "\n".join(chunks)
    except Exception as e:
        print(f"[pdf-parse] PDF error: {type(e).__name__}: {e}")
        return ""


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        chunks = [p.text for p in doc.paragraphs if p.text]
        # Также таблицы
        for tbl in doc.tables:
            for row in tbl.rows:
                for cell in row.cells:
                    if cell.text:
                        chunks.append(cell.text)
        return "\n".join(chunks)
    except Exception as e:
        print(f"[pdf-parse] DOCX error: {type(e).__name__}: {e}")
        return ""


def _extract_doc_or_rtf(content: bytes) -> str:
    """
    Старый формат .doc и .rtf — пробуем извлечь читаемый текст байтным сканом.
    Это грубо, но даёт ~70% полезного текста при наличии русского контента.
    """
    try:
        # Пробуем Windows-1251 и UTF-8
        for encoding in ("cp1251", "utf-8", "latin-1"):
            try:
                text = content.decode(encoding, errors="ignore")
                # Берём только последовательности кириллицы и латиницы
                words = re.findall(r"[А-Яа-яA-Za-z0-9.,%/\-«»()№\s]{4,}", text)
                joined = " ".join(words)
                if len(joined) > 500:  # значимый объём текста
                    return joined
            except Exception:
                continue
    except Exception as e:
        print(f"[pdf-parse] DOC/RTF error: {type(e).__name__}: {e}")
    return ""


def extract_text(content: bytes, file_name: str = "", max_pages: int = 30) -> str:
    """
    Извлекает текст из документа любого поддерживаемого формата.
    Определяет формат по расширению + магическим байтам.
    """
    if not content or len(content) < 100:
        return ""

    ext = get_file_ext(file_name)

    # PDF — по расширению или магическим байтам
    if ext == ".pdf" or content[:4] == b"%PDF":
        return _extract_pdf(content, max_pages)

    # DOCX — это zip с word/document.xml внутри
    if ext == ".docx" or content[:4] == b"PK\x03\x04":
        return _extract_docx(content)

    # DOC/RTF/прочее — пробуем грубое извлечение
    return _extract_doc_or_rtf(content)


# Backward-compat
def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 30) -> str:
    return extract_text(pdf_bytes, ".pdf", max_pages)


def truncate_for_db(text: str, limit: int = 100_000) -> str:
    """Обрезает текст до разумного размера для хранения в БД."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1000] + "\n\n[...пропущено...]\n\n" + text[-1000:]
