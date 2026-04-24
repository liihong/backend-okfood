"""全局 singleton `app_settings`：门店展示、地图锚点、配送费与会员卡标价。"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.app_settings import AppSettings
from app.schemas.admin import StoreConfigOut, StoreConfigUpdateIn


def ensure_app_settings_row(db: Session) -> AppSettings:
    """保证存在 id=1 的全局配置行；新建时数值类字段与当前环境变量默认对齐。"""
    row = db.get(AppSettings, 1)
    if row:
        return row
    s = get_settings()
    row = AppSettings(
        id=1,
        leave_deadline_time=time(21, 0, 0),
        courier_delivery_base_yuan=s.COURIER_DELIVERY_BASE_YUAN,
        courier_delivery_extra_per_unit_yuan=s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN,
        member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN,
        member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_courier_delivery_fee_config(db: Session) -> tuple[Decimal, Decimal]:
    """骑手配送费：(首份基础价, 每多一份加价)，优先读库，无行时回退 .env / 代码默认。"""
    row = db.get(AppSettings, 1)
    if not row:
        s = get_settings()
        return s.COURIER_DELIVERY_BASE_YUAN, s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN
    return Decimal(row.courier_delivery_base_yuan), Decimal(row.courier_delivery_extra_per_unit_yuan)


def get_member_card_prices_yuan(db: Session) -> tuple[Decimal, Decimal]:
    """小程序周卡、月卡标价（元）；优先读库。"""
    s = get_settings()
    row = db.get(AppSettings, 1)
    if not row:
        return s.MEMBER_CARD_WEEK_PRICE_YUAN, s.MEMBER_CARD_MONTH_PRICE_YUAN
    wk, mo = row.member_card_week_price_yuan, row.member_card_month_price_yuan
    # 历史数据或异常导入可能导致列为 NULL，Decimal(None) 会抛错并变成接口 500
    return (
        s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
        s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
    )


def get_store_config(db: Session) -> StoreConfigOut:
    s = get_settings()
    row = db.get(AppSettings, 1)
    if not row:
        return StoreConfigOut(
            courier_delivery_base_yuan=s.COURIER_DELIVERY_BASE_YUAN,
            courier_delivery_extra_per_unit_yuan=s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN,
            member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN,
            member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN,
        )
    wk, mo = row.member_card_week_price_yuan, row.member_card_month_price_yuan
    return StoreConfigOut(
        store_name=row.store_name,
        store_logo_url=row.store_logo_url,
        store_lng=float(row.store_lng) if row.store_lng is not None else None,
        store_lat=float(row.store_lat) if row.store_lat is not None else None,
        courier_delivery_base_yuan=Decimal(row.courier_delivery_base_yuan),
        courier_delivery_extra_per_unit_yuan=Decimal(row.courier_delivery_extra_per_unit_yuan),
        member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
        member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
    )


def update_store_config(db: Session, body: StoreConfigUpdateIn) -> StoreConfigOut:
    row = ensure_app_settings_row(db)
    data = body.model_dump(exclude_unset=True)
    if "store_name" in data:
        row.store_name = data["store_name"]
    if "store_logo_url" in data:
        row.store_logo_url = data["store_logo_url"]
    if "store_lng" in data:
        row.store_lng = data["store_lng"]
    if "store_lat" in data:
        row.store_lat = data["store_lat"]
    if "courier_delivery_base_yuan" in data and data["courier_delivery_base_yuan"] is not None:
        row.courier_delivery_base_yuan = data["courier_delivery_base_yuan"]
    if "courier_delivery_extra_per_unit_yuan" in data and data["courier_delivery_extra_per_unit_yuan"] is not None:
        row.courier_delivery_extra_per_unit_yuan = data["courier_delivery_extra_per_unit_yuan"]
    if "member_card_week_price_yuan" in data and data["member_card_week_price_yuan"] is not None:
        row.member_card_week_price_yuan = data["member_card_week_price_yuan"]
    if "member_card_month_price_yuan" in data and data["member_card_month_price_yuan"] is not None:
        row.member_card_month_price_yuan = data["member_card_month_price_yuan"]
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
