"""Ответы на комментарии YouTube от имени канала.

Чтение комментов идёт по API-ключу (`youtube_comments.py`), но ЗАПИСЬ Google
разрешает только по OAuth со scope `youtube.force-ssl`. Поэтому здесь отдельный
контур: долгоживущий refresh-токен из настроек меняем на короткий access-токен
и постим ответ через `comments.insert`.

Refresh-токен выдаётся один раз — `tools/youtube_oauth.py` (согласие в браузере
даёт владелец канала).
"""
import time

import httpx

from core.config import settings

TOKEN_URL = "https://oauth2.googleapis.com/token"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"

_token: str | None = None
_expires_at: float = 0.0


def is_configured() -> bool:
    return bool(
        settings.YOUTUBE_OAUTH_CLIENT_ID
        and settings.YOUTUBE_OAUTH_CLIENT_SECRET
        and settings.YOUTUBE_OAUTH_REFRESH_TOKEN
    )


async def _access_token() -> str | None:
    """Access-токен живёт ~час — держим в памяти процесса и обновляем заранее."""
    global _token, _expires_at
    if _token and time.time() < _expires_at - 60:
        return _token
    if not is_configured():
        return None
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(TOKEN_URL, data={
            "client_id": settings.YOUTUBE_OAUTH_CLIENT_ID,
            "client_secret": settings.YOUTUBE_OAUTH_CLIENT_SECRET,
            "refresh_token": settings.YOUTUBE_OAUTH_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        })
    if r.status_code != 200:
        print(f"[youtube-reply] token HTTP {r.status_code}: {r.text[:200]}")
        return None
    data = r.json()
    _token = data.get("access_token")
    _expires_at = time.time() + float(data.get("expires_in") or 3600)
    return _token


async def reply_to_comment(parent_comment_id: str, text: str) -> bool:
    """Отвечает веткой на комментарий верхнего уровня. True = отправлено."""
    if not (parent_comment_id and text):
        return False
    token = await _access_token()
    if not token:
        return False
    payload = {"snippet": {"parentId": parent_comment_id, "textOriginal": text[:9000]}}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            COMMENTS_URL,
            params={"part": "snippet"},
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
    if r.status_code in (200, 201):
        return True
    print(f"[youtube-reply] HTTP {r.status_code}: {r.text[:300]}")
    return False
