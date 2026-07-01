"""小程序首页 Banner CRUD。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.home_banner import HomeBanner
from app.schemas.marketing.home_banner import (
    LINK_TYPES,
    HomeBannerCreateIn,
    HomeBannerOut,
    HomeBannerPatchIn,
    HomeBannerPublicOut,
)


def _validate_link(link_type: str, link_target: str | None) -> None:
    lt = (link_type or "none").strip().lower()
    if lt not in LINK_TYPES:
        raise HTTPException(status_code=400, detail=f"link_type 无效，允许: {', '.join(sorted(LINK_TYPES))}")
    target = (link_target or "").strip()
    if lt == "dish":
        if not target or not target.isdigit():
            raise HTTPException(status_code=400, detail="dish 跳转须填写有效 dish_id")
    elif lt == "tab":
        if not target:
            raise HTTPException(status_code=400, detail="tab 跳转须填写 pagePath")
    elif lt == "webview":
        if not target.startswith("https://"):
            raise HTTPException(status_code=400, detail="webview 跳转须为 https 链接")
    elif lt == "member_card":
        if not target or not target.isdigit():
            raise HTTPException(status_code=400, detail="member_card 跳转须填写有效卡包模版 id")


def _to_out(row: HomeBanner) -> HomeBannerOut:
    return HomeBannerOut(
        id=int(row.id),
        store_id=int(row.store_id),
        title=(row.title or "").strip() or None,
        image_url=str(row.image_url),
        link_type=str(row.link_type or "none"),
        link_target=(row.link_target or "").strip() or None,
        sort_order=int(row.sort_order or 0),
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _to_public(row: HomeBanner) -> HomeBannerPublicOut:
    return HomeBannerPublicOut(
        id=int(row.id),
        image_url=str(row.image_url),
        link_type=str(row.link_type or "none"),
        link_target=(row.link_target or "").strip() or None,
    )


def list_active_home_banners(db: Session, *, store_id: int) -> list[HomeBannerPublicOut]:
    rows = db.scalars(
        select(HomeBanner)
        .where(HomeBanner.store_id == int(store_id), HomeBanner.is_active.is_(True))
        .order_by(HomeBanner.sort_order.asc(), HomeBanner.id.asc())
    ).all()
    return [_to_public(r) for r in rows]


def list_home_banners_admin(db: Session, *, store_id: int) -> list[HomeBannerOut]:
    rows = db.scalars(
        select(HomeBanner)
        .where(HomeBanner.store_id == int(store_id))
        .order_by(HomeBanner.sort_order.asc(), HomeBanner.id.asc())
    ).all()
    return [_to_out(r) for r in rows]


def create_home_banner(db: Session, *, store_id: int, body: HomeBannerCreateIn) -> HomeBannerOut:
    lt = (body.link_type or "none").strip().lower()
    _validate_link(lt, body.link_target)
    row = HomeBanner(
        store_id=int(store_id),
        title=(body.title or "").strip() or None,
        image_url=body.image_url.strip(),
        link_type=lt,
        link_target=(body.link_target or "").strip() or None,
        sort_order=int(body.sort_order or 0),
        is_active=bool(body.is_active),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def patch_home_banner(
    db: Session, *, banner_id: int, store_id: int, body: HomeBannerPatchIn
) -> HomeBannerOut:
    row = db.scalar(
        select(HomeBanner).where(HomeBanner.id == int(banner_id), HomeBanner.store_id == int(store_id))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    if body.title is not None:
        row.title = body.title.strip() or None
    if body.image_url is not None:
        row.image_url = body.image_url.strip()
    if body.link_type is not None:
        row.link_type = body.link_type.strip().lower()
    if body.link_target is not None:
        row.link_target = body.link_target.strip() or None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    lt = str(row.link_type or "none")
    _validate_link(lt, row.link_target)
    db.commit()
    db.refresh(row)
    return _to_out(row)


def delete_home_banner(db: Session, *, banner_id: int, store_id: int) -> None:
    row = db.scalar(
        select(HomeBanner).where(HomeBanner.id == int(banner_id), HomeBanner.store_id == int(store_id))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    db.delete(row)
    db.commit()


def set_home_banner_active(
    db: Session, *, banner_id: int, store_id: int, is_active: bool
) -> HomeBannerOut:
    row = db.scalar(
        select(HomeBanner).where(HomeBanner.id == int(banner_id), HomeBanner.store_id == int(store_id))
    )
    if not row:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    row.is_active = bool(is_active)
    db.commit()
    db.refresh(row)
    return _to_out(row)
