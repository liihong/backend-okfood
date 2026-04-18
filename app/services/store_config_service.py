"""全局 singleton `app_settings` 中的门店展示与地图锚点字段读写。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.app_settings import AppSettings
from app.schemas.admin import StoreConfigOut, StoreConfigUpdateIn


def _ensure_settings_row(db: Session) -> AppSettings:
    row = db.get(AppSettings, 1)
    if row:
        return row
    from datetime import time

    row = AppSettings(id=1, leave_deadline_time=time(21, 0, 0))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_store_config(db: Session) -> StoreConfigOut:
    row = db.get(AppSettings, 1)
    if not row:
        return StoreConfigOut()
    return StoreConfigOut(
        store_name=row.store_name,
        store_logo_url=row.store_logo_url,
        store_lng=float(row.store_lng) if row.store_lng is not None else None,
        store_lat=float(row.store_lat) if row.store_lat is not None else None,
    )


def update_store_config(db: Session, body: StoreConfigUpdateIn) -> StoreConfigOut:
    row = _ensure_settings_row(db)
    data = body.model_dump(exclude_unset=True)
    if "store_name" in data:
        row.store_name = data["store_name"]
    if "store_logo_url" in data:
        row.store_logo_url = data["store_logo_url"]
    if "store_lng" in data:
        row.store_lng = data["store_lng"]
    if "store_lat" in data:
        row.store_lat = data["store_lat"]
    db.add(row)
    db.commit()
    db.refresh(row)
    return get_store_config(db)


def load_store_coordinates_for_sorting(db: Session) -> tuple[float | None, float | None]:
    """骑手排序：读取门店锚点；未配置或缺一半坐标时视为未配置。"""
    row = db.get(AppSettings, 1)
    if not row or row.store_lng is None or row.store_lat is None:
        return None, None
    return float(row.store_lng), float(row.store_lat)
