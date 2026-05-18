"""门店级配置：每门店一行 ``stores``；兼容旧库仅 ``app_settings`` 时的读逻辑。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.app_settings import AppSettings
from app.models.store import Store
from app.schemas.admin import StoreConfigOut, StoreConfigUpdateIn


def _decimal_or_none(v: Decimal | float | None) -> Decimal | None:
    if v is None:
        return None
    return Decimal(v)


@dataclass(frozen=True)
class MemberCardPricesExtended:
    """小程序会员卡标价及可选划线价（用于「活动价」样式切换）。"""

    week_price_yuan: Decimal
    month_price_yuan: Decimal
    week_list_price_yuan: Decimal | None
    month_list_price_yuan: Decimal | None

    @property
    def promotion_active(self) -> bool:
        w = (
            self.week_list_price_yuan is not None
            and self.week_list_price_yuan > self.week_price_yuan
        )
        m = (
            self.month_list_price_yuan is not None
            and self.month_list_price_yuan > self.month_price_yuan
        )
        return bool(w or m)


def get_leave_deadline_time_for_store(db: Session, store_id: int) -> time:
    """门店请假截止时刻；无门店行时回退 app_settings id=1。"""
    st = db.get(Store, int(store_id))
    if st is not None:
        return st.leave_deadline_time
    return ensure_app_settings_row(db).leave_deadline_time


def ensure_app_settings_row(db: Session) -> AppSettings:
    """保留：历史代码与未迁移环境仍可能读 id=1。"""
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


def _store_out_from_row(st: Store) -> StoreConfigOut:
    s = get_settings()
    wk, mo = st.member_card_week_price_yuan, st.member_card_month_price_yuan
    wl = _decimal_or_none(st.member_card_week_list_price_yuan)
    ml = _decimal_or_none(st.member_card_month_list_price_yuan)
    return StoreConfigOut(
        store_id=int(st.id),
        store_name=st.name,
        store_logo_url=st.store_logo_url,
        store_lng=float(st.store_lng) if st.store_lng is not None else None,
        store_lat=float(st.store_lat) if st.store_lat is not None else None,
        courier_delivery_base_yuan=Decimal(st.courier_delivery_base_yuan),
        courier_delivery_extra_per_unit_yuan=Decimal(st.courier_delivery_extra_per_unit_yuan),
        member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
        member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
        member_card_week_list_price_yuan=wl,
        member_card_month_list_price_yuan=ml,
        sf_nightly_auto_push_enabled=bool(getattr(st, "sf_nightly_auto_push_enabled", False)),
    )


def get_store_config(db: Session, *, store_id: int) -> StoreConfigOut:
    """按门店读配置；无 ``stores`` 行时回退 ``app_settings`` id=1。"""
    st = db.get(Store, int(store_id))
    if st is not None and st.is_active:
        return _store_out_from_row(st)
    s = get_settings()
    row = db.get(AppSettings, 1)
    if not row:
        return StoreConfigOut(
            store_id=int(store_id),
            courier_delivery_base_yuan=s.COURIER_DELIVERY_BASE_YUAN,
            courier_delivery_extra_per_unit_yuan=s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN,
            member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN,
            member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN,
            member_card_week_list_price_yuan=None,
            member_card_month_list_price_yuan=None,
            sf_nightly_auto_push_enabled=False,
        )
    wk, mo = row.member_card_week_price_yuan, row.member_card_month_price_yuan
    wl = _decimal_or_none(row.member_card_week_list_price_yuan)
    ml = _decimal_or_none(row.member_card_month_list_price_yuan)
    return StoreConfigOut(
        store_id=int(store_id),
        store_name=row.store_name,
        store_logo_url=row.store_logo_url,
        store_lng=float(row.store_lng) if row.store_lng is not None else None,
        store_lat=float(row.store_lat) if row.store_lat is not None else None,
        courier_delivery_base_yuan=Decimal(row.courier_delivery_base_yuan),
        courier_delivery_extra_per_unit_yuan=Decimal(row.courier_delivery_extra_per_unit_yuan),
        member_card_week_price_yuan=s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
        member_card_month_price_yuan=s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
        member_card_week_list_price_yuan=wl,
        member_card_month_list_price_yuan=ml,
        sf_nightly_auto_push_enabled=False,
    )


def get_courier_delivery_fee_config(db: Session, *, store_id: int | None = None) -> tuple[Decimal, Decimal]:
    """骑手配送费：(首份基础价, 每多一份加价)。"""
    s = get_settings()
    if store_id is not None:
        st = db.get(Store, int(store_id))
        if st is not None:
            return Decimal(st.courier_delivery_base_yuan), Decimal(st.courier_delivery_extra_per_unit_yuan)
    row = db.get(AppSettings, 1)
    if not row:
        return s.COURIER_DELIVERY_BASE_YUAN, s.COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN
    return Decimal(row.courier_delivery_base_yuan), Decimal(row.courier_delivery_extra_per_unit_yuan)


def get_member_card_prices_yuan(db: Session, *, store_id: int | None = None) -> tuple[Decimal, Decimal]:
    """小程序周卡、月卡标价（元）。"""
    s = get_settings()
    if store_id is not None:
        st = db.get(Store, int(store_id))
        if st is not None:
            wk, mo = st.member_card_week_price_yuan, st.member_card_month_price_yuan
            return (
                s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
                s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
            )
    row = db.get(AppSettings, 1)
    if not row:
        return s.MEMBER_CARD_WEEK_PRICE_YUAN, s.MEMBER_CARD_MONTH_PRICE_YUAN
    wk, mo = row.member_card_week_price_yuan, row.member_card_month_price_yuan
    return (
        s.MEMBER_CARD_WEEK_PRICE_YUAN if wk is None else Decimal(wk),
        s.MEMBER_CARD_MONTH_PRICE_YUAN if mo is None else Decimal(mo),
    )


def get_member_card_prices_extended(db: Session, *, store_id: int | None = None) -> MemberCardPricesExtended:
    """标价 + 划线价；划线价优先门店行，其次 ``app_settings`` id=1。"""
    week_sale, month_sale = get_member_card_prices_yuan(db, store_id=store_id)
    week_list: Decimal | None = None
    month_list: Decimal | None = None
    if store_id is not None:
        st = db.get(Store, int(store_id))
        if st is not None:
            week_list = _decimal_or_none(st.member_card_week_list_price_yuan)
            month_list = _decimal_or_none(st.member_card_month_list_price_yuan)
    row = db.get(AppSettings, 1)
    if row:
        if week_list is None:
            week_list = _decimal_or_none(row.member_card_week_list_price_yuan)
        if month_list is None:
            month_list = _decimal_or_none(row.member_card_month_list_price_yuan)
    return MemberCardPricesExtended(
        week_price_yuan=week_sale,
        month_price_yuan=month_sale,
        week_list_price_yuan=week_list,
        month_list_price_yuan=month_list,
    )


def update_store_config(db: Session, store_id: int, body: StoreConfigUpdateIn) -> StoreConfigOut:
    """更新指定门店配置；无行则创建（同租户默认租户 1）。"""
    st = db.get(Store, int(store_id))
    if not st:
        raise HTTPException(status_code=404, detail="门店不存在")
    fs = body.model_fields_set
    if "store_name" in fs and body.store_name is not None:
        st.name = str(body.store_name)
    if "store_logo_url" in fs:
        st.store_logo_url = body.store_logo_url
    if "store_lng" in fs:
        st.store_lng = body.store_lng
    if "store_lat" in fs:
        st.store_lat = body.store_lat
    if "courier_delivery_base_yuan" in fs and body.courier_delivery_base_yuan is not None:
        st.courier_delivery_base_yuan = body.courier_delivery_base_yuan
    if (
        "courier_delivery_extra_per_unit_yuan" in fs
        and body.courier_delivery_extra_per_unit_yuan is not None
    ):
        st.courier_delivery_extra_per_unit_yuan = body.courier_delivery_extra_per_unit_yuan
    if "member_card_week_price_yuan" in fs and body.member_card_week_price_yuan is not None:
        st.member_card_week_price_yuan = body.member_card_week_price_yuan
    if "member_card_month_price_yuan" in fs and body.member_card_month_price_yuan is not None:
        st.member_card_month_price_yuan = body.member_card_month_price_yuan
    if "member_card_week_list_price_yuan" in fs:
        st.member_card_week_list_price_yuan = body.member_card_week_list_price_yuan
    if "member_card_month_list_price_yuan" in fs:
        st.member_card_month_list_price_yuan = body.member_card_month_list_price_yuan
    if "sf_nightly_auto_push_enabled" in fs and body.sf_nightly_auto_push_enabled is not None:
        st.sf_nightly_auto_push_enabled = bool(body.sf_nightly_auto_push_enabled)
    db.add(st)
    db.commit()
    db.refresh(st)
    return get_store_config(db, store_id=int(st.id))


def load_store_coordinates_for_sorting(db: Session, *, store_id: int | None = None, tenant_id: int | None = None):
    """骑手排序锚点：优先指定门店；否则租户内取 id 最小的一家营业门店；再回退 app_settings。"""
    if store_id is not None:
        row = db.get(Store, int(store_id))
        if row and row.store_lng is not None and row.store_lat is not None:
            return float(row.store_lng), float(row.store_lat)
    if tenant_id is not None:
        from sqlalchemy import select

        st2 = db.scalars(
            select(Store)
            .where(Store.tenant_id == int(tenant_id), Store.is_active.is_(True))
            .order_by(Store.id.asc())
            .limit(1)
        ).first()
        if st2 and st2.store_lng is not None and st2.store_lat is not None:
            return float(st2.store_lng), float(st2.store_lat)
    row = db.get(AppSettings, 1)
    if not row or row.store_lng is None or row.store_lat is None:
        return None, None
    return float(row.store_lng), float(row.store_lat)
