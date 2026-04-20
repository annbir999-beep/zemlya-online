"""
Test: bypass Qrator on domclick.ru using _sv session cookie + curl_cffi Chrome fingerprint + rotating proxy.
Checks if we get real listing HTML (looks for __NEXT_DATA__ or listing markers).
"""
import asyncio
from curl_cffi.requests import AsyncSession as CurlSession

PROXY = "http://USER923303-zone-custom-region-RU:cb497d@global.rotgb.711proxy.com:10000"
PROXIES = {"https": PROXY, "http": PROXY}

SV_COOKIE = "SV1.e53816d5-e003-4cfb-8179-1b86f2f44cb3.1756913792.1776632773"
VISIT_ID = "85345b8f-699d-4274-8833-59cf9f824994-f4f0dcc432ac8ba6"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

URL = "https://domclick.ru/search?deal_type=sale&category=land&offer_type=lot"


async def test():
    cookies = {"_sv": SV_COOKIE, "_visitId": VISIT_ID}

    print(f"Testing: {URL}")
    print(f"Cookie _sv: {SV_COOKIE[:40]}...")

    async with CurlSession(impersonate="chrome124") as s:
        try:
            r = await s.get(
                URL,
                proxies=PROXIES,
                timeout=90,
                verify=False,
                headers=HEADERS,
                cookies=cookies,
            )
            print(f"Status: {r.status_code}")
            text = r.text

            # Diagnose response
            has_next_data = "__NEXT_DATA__" in text
            has_offers = "offer" in text.lower() or "объявлен" in text.lower()
            has_captcha = "captcha" in text.lower() or "qrator" in text.lower()
            has_blocked = "заблокирован" in text.lower() or "403" in str(r.status_code)

            print(f"__NEXT_DATA__ found: {has_next_data}")
            print(f"Offers/listing keywords: {has_offers}")
            print(f"Captcha/Qrator markers: {has_captcha}")
            print(f"Blocked: {has_blocked}")
            print(f"Response length: {len(text)} chars")
            print(f"Title: {_extract_title(text)}")

            if has_next_data:
                print("\n✅ SUCCESS: Got real page with __NEXT_DATA__")
                # Try to extract offers count
                import re
                m = re.search(r'"totalCount":\s*(\d+)', text)
                if m:
                    print(f"Total offers found: {m.group(1)}")
                # Save snippet
                with open("/tmp/domclick_response.html", "w", encoding="utf-8") as f:
                    f.write(text[:50000])
                print("Saved first 50k chars to /tmp/domclick_response.html")
            else:
                print("\n❌ No __NEXT_DATA__ — probably blocked or wrong page")
                print("First 500 chars:")
                print(text[:500])

        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}")


def _extract_title(html: str) -> str:
    import re
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else "no title"


if __name__ == "__main__":
    asyncio.run(test())
