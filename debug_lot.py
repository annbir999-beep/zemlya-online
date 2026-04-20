"""
Собираем все уникальные noticeAttributes и lotAttributes из 50 лотов
Запускать с домашнего ПК без VPN.
"""
import asyncio
import httpx

TORGI_BASE = "https://torgi.gov.ru/new/api/public/lotcards"

async def run():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://torgi.gov.ru/",
    }
    all_codes: dict = {}  # code -> {fullName, values}

    async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=True) as client:
        for page in range(5):  # 5 страниц по 10 = 50 лотов
            resp = await client.get(f"{TORGI_BASE}/search", params=[
                ("lotStatus", "PUBLISHED"), ("catCode", "301"),
                ("byFirstVersion", "true"), ("page", page), ("size", 10),
            ])
            lots = resp.json().get("content", [])
            for lot in lots:
                lot_id = lot["id"]
                detail_resp = await client.get(f"{TORGI_BASE}/{lot_id}")
                if detail_resp.status_code != 200:
                    continue
                d = detail_resp.json()
                for attr in (d.get("noticeAttributes") or []) + (d.get("attributes") or []):
                    code = attr.get("code", "")
                    if not code:
                        continue
                    if code not in all_codes:
                        all_codes[code] = {
                            "fullName": attr.get("fullName", ""),
                            "values": set(),
                        }
                    val = attr.get("value")
                    if val is not None:
                        all_codes[code]["values"].add(str(val))
            print(f"Страница {page} — собрано кодов: {len(all_codes)}")

    print("\n=== Все уникальные атрибуты ===")
    for code, info in sorted(all_codes.items()):
        vals = ", ".join(sorted(info["values"])[:5])
        print(f"{code}: {info['fullName'][:70]} | значения: {vals}")

if __name__ == "__main__":
    asyncio.run(run())
