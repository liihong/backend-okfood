"""推单冻结后 merged：挡取消请假、保留当日首餐白名单。"""

from datetime import date, time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.delivery_sheet_push_absent_snapshot import DeliverySheetPushAbsentSnapshot
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.delivery_sheet_push_snapshot_service import (
    capture_delivery_sheet_absent_members_on_first_push,
    member_qualifies_post_push_whitelist,
)
from app.services.delivery.delivery_sheet_service import _merged_home_member_ids_when_sheet_frozen


@pytest.fixture()
def merge_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        SfSameCityPush.__table__,
        DeliverySheetPushAbsentSnapshot.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="测试门店",
                leave_deadline_time=time(21, 0),
                is_active=True,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _add_member(
    db: Session,
    *,
    mid: int,
    phone: str,
    balance: int = 10,
    delivery_start_date: date | None = None,
    leave_range: tuple[date, date] | None = None,
    tomorrow_leave: date | None = None,
) -> Member:
    m = Member(
        id=mid,
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=f"会员{mid}",
        balance=balance,
        is_active=True,
        store_pickup=False,
        delivery_start_date=delivery_start_date,
    )
    if leave_range:
        m.leave_range_start, m.leave_range_end = leave_range
    if tomorrow_leave is not None:
        m.is_leaved_tomorrow = True
        m.tomorrow_leave_target_date = tomorrow_leave
    db.add(m)
    db.flush()
    return m


def test_merged_blocks_absent_cancel_leave_allows_first_day_whitelist(merge_db: Session):
    d = date(2026, 6, 3)
    # 在推单快照内
    _add_member(merge_db, mid=1, phone="13000000001", delivery_start_date=date(2026, 5, 1))
    # 推单当日请假（中午取消也不应并入）
    _add_member(
        merge_db,
        mid=2,
        phone="13000000002",
        leave_range=(d, d),
    )
    # 当日首餐新客（推单后达标应白名单并入）
    _add_member(merge_db, mid=3, phone="13000000003", delivery_start_date=d)
    merge_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-a",
            push_kind="delivery_sheet",
            shop_order_id="shop-a",
            error_code=0,
            request_snapshot={"fulfillment_member_ids": [1]},
        )
    )
    capture_delivery_sheet_absent_members_on_first_push(
        merge_db, store_id=1, delivery_date=d
    )
    # 模拟中午取消请假：当日不再缺席，但仍在 absent 快照中
    on_leave = merge_db.get(Member, 2)
    on_leave.leave_range_start = None
    on_leave.leave_range_end = None
    merge_db.commit()

    with patch(
        "app.services.delivery.delivery_sheet_service.post_push_first_day_whitelist_member_ids",
        return_value={3},
    ):
        merged = _merged_home_member_ids_when_sheet_frozen(
            merge_db, delivery_date=d, store_id=1
        )
    assert merged == {1, 3}


def test_whitelist_requires_delivery_start_equals_business_day(merge_db: Session):
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13000000009",
        name="x",
        balance=5,
        delivery_start_date=date(2026, 6, 4),
    )
    assert not member_qualifies_post_push_whitelist(m, delivery_date=date(2026, 6, 3))
    m.delivery_start_date = date(2026, 6, 3)
    assert member_qualifies_post_push_whitelist(m, delivery_date=date(2026, 6, 3))


def test_merged_without_absent_snapshot_only_frozen(merge_db: Session):
    """无请假快照时仅保留顺丰快照（不 union 全量 realtime）。"""
    d = date(2026, 6, 4)
    _add_member(merge_db, mid=10, phone="13000000010")
    _add_member(merge_db, mid=11, phone="13000000011")
    merge_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-b",
            push_kind="delivery_sheet",
            shop_order_id="shop-b",
            error_code=0,
            request_snapshot={"fulfillment_member_ids": [10]},
        )
    )
    merge_db.commit()

    with patch(
        "app.services.delivery.delivery_sheet_service.post_push_first_day_whitelist_member_ids",
        return_value=set(),
    ):
        merged = _merged_home_member_ids_when_sheet_frozen(
            merge_db, delivery_date=d, store_id=1
        )
    assert merged == {10}
