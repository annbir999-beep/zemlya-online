"""Публичный API блога — статьи контент-машины.

  · GET /api/blog          — список опубликованных статей
  · GET /api/blog/{slug}   — полная статья (HTML)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.content import ContentPost

router = APIRouter()


@router.get("")
@router.get("/")
async def list_posts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    base = select(ContentPost).where(ContentPost.status == "published")
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()
    rows = (await db.execute(
        base.order_by(desc(ContentPost.published_at))
        .offset((page - 1) * per_page)
        .limit(per_page)
    )).scalars().all()
    return {
        "total": total,
        "items": [
            {
                "slug": p.slug,
                "title": p.title,
                "excerpt": p.excerpt,
                "reading_minutes": p.reading_minutes,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in rows
        ],
    }


@router.get("/{slug}")
async def get_post(slug: str, db: AsyncSession = Depends(get_db)):
    post = (await db.execute(
        select(ContentPost).where(ContentPost.slug == slug, ContentPost.status == "published")
    )).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Статья не найдена")
    return {
        "slug": post.slug,
        "title": post.title,
        "excerpt": post.excerpt,
        "body_html": post.body_html,
        "reading_minutes": post.reading_minutes,
        "published_at": post.published_at.isoformat() if post.published_at else None,
    }
