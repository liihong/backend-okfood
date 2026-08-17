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
from app.schemas.admin import SfSameCityPreviewRow, SfSameCityPushIn
from app.services.delivery.sf_same_city_service import (
    _ensure_failed_push_rows,
    _persist_pre_push_validation_failure,
    _persist_pre_push_validation_failure_best_effort,
    _validate_sf_push_row,
    push_sf_same_city,
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


def test_missing_coords_validate_without_agg_is_failure() -> None:
    """停靠点聚合缺失时，预览行无坐标仍须判失败，避免默认坐标悄悄创单。"""
    item = _preview_row(recv_lng=None, recv_lat=None)
    skip = _validate_sf_push_row(
        None,
        item,
        d=date(2026, 8, 13),
        success_stop_ids=set(),
        success_member_map={},
        ags={},
    )
    assert skip is not None
    assert skip.ok is False
    assert "缺少有效坐标" in (skip.message or "")


def _gset() -> SimpleNamespace:
    return SimpleNamespace(
        SF_OPEN_SHOP_ID="shop1",
        SF_OPEN_DEV_ID=1,
        SF_OPEN_SECRET="secret",
        SF_PICKUP_PHONE="13800000000",
        SF_PICKUP_ADDRESS="取件地址",
        SF_DEFAULT_PRODUCT_TYPE=1,
        SF_VEHICLE_TYPE_CODE=1,
    )


def test_push_same_city_missing_coords_writes_monitor_fail(persist_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """批量推单遇到缺坐标：不调顺丰，写入创单失败行。"""
    from contextlib import nullcontext

    import app.services.delivery.sf_same_city_service as svc

    monkeypatch.setattr(svc, "_sf_push_serial_lock", lambda *a, **k: nullcontext())
    monkeypatch.setattr(svc, "merged_sf_integration_namespace", lambda *a, **k: _gset())
    monkeypatch.setattr(
        svc,
        "get_store_config",
        lambda *a, **k: SimpleNamespace(store_name="测试门店", store_lng=113.8, store_lat=35.2),
    )

    called = {"http": 0}

    def _forbid_http(*a, **k):
        called["http"] += 1
        raise AssertionError("缺坐标不得请求顺丰 createorder")

    monkeypatch.setattr(svc, "_sf_http_create_order", _forbid_http)

    item = _preview_row(recv_lng=None, recv_lat=None)
    agg = _FakeAgg()
    agg.sub_lines = []
    out = push_sf_same_city(
        persist_db,
        SfSameCityPushIn(delivery_date=date(2026, 8, 13), rows=[item]),
        store_id=1,
        ags_hint={item.stop_id: agg},
    )
    assert called["http"] == 0
    assert len(out.results) == 1
    assert out.results[0].ok is False
    assert "缺少有效坐标" in (out.results[0].message or "")
    row = persist_db.scalars(select(SfSameCityPush)).one()
    assert row.error_code == -1
    assert "缺少有效坐标" in (row.error_msg or "")
    preview = (row.request_snapshot or {}).get("preview_row") or {}
    assert preview.get("recv_phone") == "18568538855"


def test_best_effort_persist_writes_minimal_row_when_snapshot_fails(
    persist_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """完整快照失败时仍须落下最小失败行。"""
    import app.services.delivery.sf_same_city_service as svc

    def _boom(*a, **k):
        raise RuntimeError("snapshot boom")

    monkeypatch.setattr(svc, "_persist_pre_push_validation_failure", _boom)
    item = _preview_row(recv_lng=None, recv_lat=None)
    _persist_pre_push_validation_failure_best_effort(
        persist_db,
        store_id=1,
        delivery_date=date(2026, 8, 13),
        item=item,
        agg_cur=_FakeAgg(),
        err_msg="会员18568538855默认配送地址缺少有效坐标，不可推顺丰",
        push_kind="delivery_sheet",
        gset=_gset(),
        existing_push_id=None,
    )
    row = persist_db.scalars(select(SfSameCityPush)).one()
    assert row.error_code == -1
    assert 3579 in ((row.request_snapshot or {}).get("fulfillment_member_ids") or [])


def test_ensure_failed_push_rows_backfills_missing(persist_db: Session) -> None:
    """批次结果失败但尚未落库时补写。"""
    from app.schemas.admin import SfSameCityPushItemResult

    item = _preview_row(recv_lng=None, recv_lat=None)
    _ensure_failed_push_rows(
        persist_db,
        store_id=1,
        delivery_date=date(2026, 8, 13),
        results=[
            SfSameCityPushItemResult(
                stop_id=item.stop_id,
                ok=False,
                message="配送地址缺少有效坐标，不可推顺丰",
                sf_order_id=None,
            )
        ],
        items_by_stop={item.stop_id: item},
        ags={item.stop_id: _FakeAgg()},
        push_kind="delivery_sheet",
        gset=_gset(),
    )
    row = persist_db.scalars(select(SfSameCityPush)).one()
    assert row.error_code == -1
    assert row.stop_id == item.stop_id
