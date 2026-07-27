"""IndexNow — мгновенное уведомление Яндекса/Bing о новых/изменённых URL.

Ключ верифицируется файлом {KEY}.txt на корне сайта (frontend/public/).
Один запрос — до 10 000 URL за раз (используем bulk-эндпоинт).
"""
import httpx

INDEXNOW_KEY = "31de4056cecb4ed696e2e7987aa91935"
_ENDPOINT = "https://api.indexnow.org/indexnow"


async def submit_urls(urls: list[str], host: str = "torgi-zemli.ru") -> bool:
    """Отправляет список URL в IndexNow. True — принято (200/202)."""
    if not urls:
        return True
    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": f"https://{host}/{INDEXNOW_KEY}.txt",
        "urlList": urls[:10_000],
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_ENDPOINT, json=payload)
            return r.status_code in (200, 202)
    except Exception as e:
        print(f"[indexnow] submit failed: {type(e).__name__}: {e}")
        return False
