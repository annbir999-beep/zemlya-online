"""Поллер комментариев YouTube-канала — этап 3 единого инбокса.

YouTube Data API v3 (API key, read-only): commentThreads.list по каналу.
Автоответ на YouTube требует OAuth — на этом этапе комменты только собираются,
скорятся и эскалируются; отвечает Анна вручную из студии.
"""
from datetime import datetime, timedelta, timezone

import httpx

from core.config import settings

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
FRESH_WINDOW_HOURS = 24  # на первом прогоне не тащим всю историю


async def poll_comments() -> int:
    """Собирает свежие комменты канала в инбокс. Возвращает число новых."""
    if not settings.YOUTUBE_API_KEY or not settings.YOUTUBE_CHANNEL_ID:
        return 0

    from db.database import AsyncSessionLocal
    from services.inbox_hub import ingest

    params = {
        "part": "snippet",
        "allThreadsRelatedToChannelId": settings.YOUTUBE_CHANNEL_ID,
        "order": "time",
        "maxResults": 50,
        "textFormat": "plainText",
        "key": settings.YOUTUBE_API_KEY,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(API_URL, params=params)
        if r.status_code != 200:
            print(f"[youtube-comments] HTTP {r.status_code}: {r.text[:200]}")
            return 0
        items = r.json().get("items") or []

    if not items:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESH_WINDOW_HOURS)
    new_count = 0
    async with AsyncSessionLocal() as db:
        for item in items:
            top = ((item.get("snippet") or {}).get("topLevelComment") or {})
            sn = top.get("snippet") or {}
            comment_id = top.get("id")
            if not comment_id or not sn.get("textOriginal"):
                continue
            published = sn.get("publishedAt") or ""
            try:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                if pub_dt < cutoff:
                    continue
            except ValueError:
                pass
            video_id = sn.get("videoId")
            msg = await ingest(
                db,
                source="youtube",
                event_type="comment",
                external_id=comment_id,
                author_id=(sn.get("authorChannelId") or {}).get("value"),
                author_name=sn.get("authorDisplayName"),
                author_url=sn.get("authorChannelUrl"),
                text=sn.get("textOriginal", ""),
                post_ref=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}" if video_id else None,
                raw={"video_id": video_id, "published_at": published},
            )
            if msg:
                new_count += 1
    return new_count
