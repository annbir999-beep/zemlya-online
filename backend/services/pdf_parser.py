"""
Загрузка и парсинг PDF-документов лотов torgi.gov.

Документы прикрепляются через массив noticeAttachments в детальном API.
Каждый элемент содержит fileId, fileName, attachmentTypeCode/Name.

Мы скачиваем по приоритету типов:
- Извещение (Notice_Document) — основной текст с описанием участка
- Технические условия (Technical_*) — точные параметры подключения
- Проект договора (Draft_Contract*) — переуступка/субаренда/штрафы
- Опционально: схема расположения (Scheme_*)
"""
import io
from typing import Optional


# Приоритет типов документов (чем меньше — тем ценнее)
PRIORITY_TYPES = {
    # Извещение — главный документ с описанием участка
    "notice": ["Notice_Document", "Notice", "Извещение"],
    # Технические условия (электричество, газ, водопровод)
    "tech_conditions": ["Technical_Conditions", "TC_Document", "техническ"],
    # Проект договора аренды/купли
    "contract": ["Draft_Contract", "Contract_Draft", "проект договора", "договор"],
    # СРЗУ — обычно мало текста, но иногда полезно
    "scheme": ["Scheme", "СРЗУ", "схема расположения"],
}


def classify_attachment(att: dict) -> Optional[str]:
    """Возвращает наш ключ типа документа (notice/tech_conditions/contract/scheme) или None."""
    code = (att.get("attachmentTypeCode") or "").lower()
    name = (att.get("attachmentTypeName") or "").lower()
    file_name = (att.get("fileName") or "").lower()

    for our_type, keywords in PRIORITY_TYPES.items():
        for kw in keywords:
            kw_l = kw.lower()
            if kw_l in code or kw_l in name or kw_l in file_name:
                return our_type
    return None


def select_best_attachments(attachments: list[dict]) -> dict[str, dict]:
    """
    Из массива noticeAttachments выбирает по 1 документу каждого нашего типа.
    Возвращает {our_type: attachment_dict}.
    """
    result: dict[str, dict] = {}
    if not attachments:
        return result
    for att in attachments:
        if att.get("inactive"):
            continue
        # Пропускаем .doc/.docx — берём только PDF (.doc сложнее парсить)
        fname = (att.get("fileName") or "").lower()
        if not (fname.endswith(".pdf") or fname.endswith(".pdf.zip")):
            continue
        our_type = classify_attachment(att)
        if our_type and our_type not in result:
            result[our_type] = att
    return result


async def download_pdf(client, file_id: str) -> Optional[bytes]:
    """Скачивает PDF по fileId через прокси (используя готовый httpx-клиент скрапера)."""
    if not file_id:
        return None
    url = f"https://torgi.gov.ru/new/file-store/v1/{file_id}"
    try:
        resp = await client.get(url, timeout=60)
        if resp.status_code != 200:
            return None
        content = resp.content
        # Проверим что это действительно PDF (магические байты %PDF)
        if not content[:4] == b"%PDF":
            return None
        return content
    except Exception:
        return None


def extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = 30) -> str:
    """Извлекает текст из PDF (pdfplumber). Ограничиваем 30 страницами от мусора."""
    if not pdf_bytes:
        return ""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
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
        print(f"[pdf-parse] error: {type(e).__name__}: {e}")
        return ""


def truncate_for_db(text: str, limit: int = 100_000) -> str:
    """Обрезает текст до разумного размера для хранения в БД."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    # Берём начало (там обычно описание) + конец (там подпись/печать)
    return text[: limit - 1000] + "\n\n[...пропущено...]\n\n" + text[-1000:]
