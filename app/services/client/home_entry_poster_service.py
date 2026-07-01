"""小程序进入弹窗海报 CRUD。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.home_entry_poster import HomeEntryPoster
from app.schemas.marketing.home_entry_poster import (
    HomeEntryPosterOut,
    HomeEntryPosterPublicOut,
    HomeEntryPosterUpsertIn,
)


def _to_out(row: HomeEntryPoster) -> HomeEntryPosterOut:
    return HomeEntryPosterOut(
        id=int(row.id),
        store_id=int(row.store_id),
        image_url=str(row.image_url),
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def get_active_entry_poster(db: Session, *, store_id: int) -> HomeEntryPosterPublicOut | None:
    row = db.scalar(
        select(HomeEntryPoster).where(
            HomeEntryPoster.store_id == int(store_id),
            HomeEntryPoster.is_active.is_(True),
        )
    )
    if not row:
        return None
    image_url = str(row.image_url or "").strip()
    if not image_url:
        return None
    return HomeEntryPosterPublicOut(image_url=image_url)


def get_entry_poster_admin(db: Session, *, store_id: int) -> HomeEntryPosterOut | None:
    row = db.scalar(select(HomeEntryPoster).where(HomeEntryPoster.store_id == int(store_id)))
    if not row:
        return None
    return _to_out(row)


def upsert_entry_poster(
    db: Session, *, store_id: int, body: HomeEntryPosterUpsertIn
) -> HomeEntryPosterOut:
    row = db.scalar(select(HomeEntryPoster).where(HomeEntryPoster.store_id == int(store_id)))
    image_url = body.image_url.strip()
    if row:
        row.image_url = image_url
        row.is_active = bool(body.is_active)
    else:
        row = HomeEntryPoster(
            store_id=int(store_id),
            image_url=image_url,
            is_active=bool(body.is_active),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)
