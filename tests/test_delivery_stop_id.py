"""配送停靠点：同址不同会员必须拆成不同 stop_id。"""

from datetime import date

from app.services.delivery.delivery_stop_id import (
    compute_delivery_stop_id,
    compute_legacy_address_stop_id,
    member_ids_from_sf_push_snapshot,
)


def test_same_address_different_members_have_different_stop_ids() -> None:
    d = date(2026, 9, 1)
    area = "互联网区域"
    addr = "互联网区域 河南省新乡市红旗区 新乡市人民政府北门"
    a = compute_delivery_stop_id(d, area, addr, member_id=101)
    b = compute_delivery_stop_id(d, area, addr, member_id=202)
    assert a != b
    assert a == compute_delivery_stop_id(d, area, addr, member_id=101)


def test_legacy_address_stop_id_differs_from_per_member() -> None:
    d = date(2026, 9, 1)
    area = "互联网区域"
    addr = "互联网区域 河南省新乡市红旗区 新乡市人民政府北门"
    per_member = compute_delivery_stop_id(d, area, addr, member_id=101)
    legacy = compute_legacy_address_stop_id(d, area, addr)
    assert per_member != legacy
    assert len(per_member) == 32
    assert len(legacy) == 32


def test_member_ids_from_sf_push_snapshot() -> None:
    assert member_ids_from_sf_push_snapshot(None) == []
    assert member_ids_from_sf_push_snapshot({"fulfillment_member_ids": [11, "22", "x"]}) == [11, 22]
