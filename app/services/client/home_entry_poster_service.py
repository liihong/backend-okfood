"""小程序弹窗海报 CRUD（同表 home_entry_poster，按 poster_type 区分场景）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.home_entry_poster import (
    POSTER_TYPE_ENTRY,
    POSTER_TYPE_MENU,
    HomeEntryPoster,
)
from app.schemas.marketing.home_entry_poster import (
    HomeEntryPosterOut,
    HomeEntryPosterPublicOut,
    HomeEntryPosterUpsertIn,
)


def _normalize_poster_type(poster_type: str) -> str:
    value = str(poster_type or "").strip().lower()
    if value == POSTER_TYPE_MENU:
        return POSTER_TYPE_MENU
    return POSTER_TYPE_ENTRY


def _to_out(row: HomeEntryPoster) -> HomeEntryPosterOut:
    return HomeEntryPosterOut(
        id=int(row.id),
        store_id=int(row.store_id),
        poster_type=_normalize_poster_type(row.poster_type),
        image_url=str(row.image_url),
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _get_row(db: Session, *, store_id: int, poster_type: str) -> HomeEntryPoster | None:
    normalized = _normalize_poster_type(poster_type)
    return db.scalar(
        select(HomeEntryPoster).where(
            HomeEntryPoster.store_id == int(store_id),
            HomeEntryPoster.poster_type == normalized,
        )
    )


def get_active_poster(
    db: Session, *, store_id: int, poster_type: str = POSTER_TYPE_ENTRY
) -> HomeEntryPosterPublicOut | None:
    """获取指定场景下已启用的海报（供小程序端）。"""
    row = _get_row(db, store_id=store_id, poster_type=poster_type)
    if not row or not bool(row.is_active):
        return None
    image_url = str(row.image_url or "").strip()
    if not image_url:
        return None
    return HomeEntryPosterPublicOut(image_url=image_url)


def get_poster_admin(
    db: Session, *, store_id: int, poster_type: str = POSTER_TYPE_ENTRY
) -> HomeEntryPosterOut | None:
    """管理端读取指定场景的海报配置。"""
    row = _get_row(db, store_id=store_id, poster_type=poster_type)
    if not row:
        return None
    return _to_out(row)


def upsert_poster(
    db: Session,
    *,
    store_id: int,
    body: HomeEntryPosterUpsertIn,
    poster_type: str = POSTER_TYPE_ENTRY,
) -> HomeEntryPosterOut:
    """管理端保存指定场景的海报配置（每门店每场景 upsert 一条）。"""
    normalized = _normalize_poster_type(poster_type)
    row = _get_row(db, store_id=store_id, poster_type=normalized)
    image_url = body.image_url.strip()
    if row:
        row.image_url = image_url
        row.is_active = bool(body.is_active)
    else:
        row = HomeEntryPoster(
            store_id=int(store_id),
            poster_type=normalized,
            image_url=image_url,
            is_active=bool(body.is_active),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def get_active_entry_poster(db: Session, *, store_id: int) -> HomeEntryPosterPublicOut | None:
    return get_active_poster(db, store_id=store_id, poster_type=POSTER_TYPE_ENTRY)


def get_entry_poster_admin(db: Session, *, store_id: int) -> HomeEntryPosterOut | None:
    return get_poster_admin(db, store_id=store_id, poster_type=POSTER_TYPE_ENTRY)


def upsert_entry_poster(
    db: Session, *, store_id: int, body: HomeEntryPosterUpsertIn
) -> HomeEntryPosterOut:
    return upsert_poster(db, store_id=store_id, body=body, poster_type=POSTER_TYPE_ENTRY)


def get_active_menu_poster(db: Session, *, store_id: int) -> HomeEntryPosterPublicOut | None:
    return get_active_poster(db, store_id=store_id, poster_type=POSTER_TYPE_MENU)


def get_menu_poster_admin(db: Session, *, store_id: int) -> HomeEntryPosterOut | None:
    return get_poster_admin(db, store_id=store_id, poster_type=POSTER_TYPE_MENU)


def upsert_menu_poster(
    db: Session, *, store_id: int, body: HomeEntryPosterUpsertIn
) -> HomeEntryPosterOut:
    return upsert_poster(db, store_id=store_id, body=body, poster_type=POSTER_TYPE_MENU)
