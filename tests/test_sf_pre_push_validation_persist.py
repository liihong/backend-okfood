"""缺坐标等推前校验失败必须写入 sf_same_city_pushes，监控「创单失败」可查。"""

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, or_, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import SfSameCityPreviewRow
from app.services.delivery.sf_same_city_service import (
    _persist_pre_push_validation_failure,
    _validate_sf_push_row,
)


class _FakeAgg:
    def __init__(self) -> None:
        self.group_area = "绿都城区域"
        self.address_line = "坦克销售店展厅"
        self.sub_lines = [
            {
                "member_id": 3579,
                "name": "Crush",
                "phone": "18568538855",
                "units": 1,
                "is_delivered": False,
            },
        ]
        self.singles = []


def _preview_row(*, recv_lng: float | None, recv_lat: float | None) -> SfSameCityPreviewRow:
    return SfSameCityPreviewRow(
        stop_id="stop-nocoord-001",
        group_area="绿都城区域",
        address_line="坦克销售店展厅",
        pickup_phone="13800000000",
        map_location_text="坦克销售店展厅",
        door_detail="",
        recv_address="坦克销售店展厅",
        recv_building="",
        recv_lng=recv_lng,
        recv_lat=recv_lat,
        recv_name="Crush",
        recv_phone="18568538855",
        product_category="餐品",
        weight_kg=0.5,
        push_immediately=True,
        expect_delivery_at=datetime(2026, 8, 13, 12, 0, 0),
        remark=None,
        is_direct=False,
        vehicle_type="小轿车",
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=1,
        single_meal_count=0,
        selected=True,
        already_pushed=False,
    )


@pytest.fixture()
def persist_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [Tenant.__table__, Store.__table__, SfSameCityPush.__table__]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True))
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_missing_coords_validate_row_is_failure() -> None:
    item = _preview_row(recv_lng=None, recv_lat=None)
    agg = _FakeAgg()
    agg.sub_lines = []
    skip = _validate_sf_push_row(
        None,
        item,
        d=date(2026, 8, 13),
        success_stop_ids=set(),
        success_member_map={},
        ags={item.stop_id: agg},
    )
    assert skip is not None
    assert skip.ok is False
    assert "缺少有效坐标" in (skip.message or "")


def test_persist_pre_push_validation_failure_is_monitor_fail(persist_db: Session) -> None:
    item = _preview_row(recv_lng=None, recv_lat=None)
    gset = SimpleNamespace(
        SF_OPEN_SHOP_ID="shop1",
        SF_OPEN_DEV_ID=1,
        SF_DEFAULT_PRODUCT_TYPE=1,
        SF_VEHICLE_TYPE_CODE=1,
    )
    _persist_pre_push_validation_failure(
        persist_db,
        store_id=1,
        delivery_date=date(2026, 8, 13),
        item=item,
        agg_cur=_FakeAgg(),
        err_msg="会员18568538855默认配送地址缺少有效坐标，不可推顺丰",
        push_kind="delivery_sheet",
        gset=gset,
        existing_push_id=None,
    )
    row = persist_db.scalars(select(SfSameCityPush)).one()
    assert row.error_code == -1
    assert "缺少有效坐标" in (row.error_msg or "")
    assert row.sf_order_id is None
    snap = row.request_snapshot or {}
    assert 3579 in (snap.get("fulfillment_member_ids") or [])
    preview = snap.get("preview_row") or {}
    assert preview.get("recv_phone") == "18568538855"
    # 与监控页「创单失败」筛选口径一致
    fails = persist_db.scalars(
        select(SfSameCityPush).where(
            or_(SfSameCityPush.error_code.is_(None), SfSameCityPush.error_code != 0)
        )
    ).all()
    assert len(fails) == 1
