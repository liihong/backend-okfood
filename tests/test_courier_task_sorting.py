"""骑手任务排序：锚点选择与距离计算（无数据库）。"""

from types import SimpleNamespace

from app.models.member_address import MemberAddress
from app.services.courier_task_sorting import (
    centroid_of_member_addresses,
    distance_from_anchor_m,
    reference_lng_lat_for_task_sorting,
    task_sort_key,
)


def _addr(mid: int, lng: float, lat: float) -> MemberAddress:
    return MemberAddress(
        member_id=mid,
        contact_name="",
        contact_phone="",
        detail_address="",
        lng=lng,
        lat=lat,
        is_default=True,
    )


def test_reference_prefers_store_coordinates():
    m = SimpleNamespace(id=1)
    defaults = {1: _addr(1, 114.0, 36.0)}
    lng, lat = reference_lng_lat_for_task_sorting(113.0, 35.0, [m], defaults)
    assert lng == 113.0 and lat == 35.0


def test_reference_falls_back_to_centroid_when_store_unset():
    m1 = SimpleNamespace(id=1)
    m2 = SimpleNamespace(id=2)
    defaults = {
        1: _addr(1, 114.0, 36.0),
        2: _addr(2, 112.0, 34.0),
    }
    lng, lat = reference_lng_lat_for_task_sorting(None, None, [m1, m2], defaults)
    assert abs(lng - 113.0) < 1e-9
    assert abs(lat - 35.0) < 1e-9


def test_centroid_empty():
    m = SimpleNamespace(id=1)
    assert centroid_of_member_addresses([m], {1: None}) == (None, None)


def test_distance_from_anchor():
    d = distance_from_anchor_m(113.0, 35.0, 113.001, 35.0)
    assert d is not None
    assert 80 < d < 120


def test_task_sort_key_orders_none_last():
    rows = [(None,), (100.0,), (50.0,)]
    rows.sort(key=lambda t: task_sort_key(t[0]))
    assert [t[0] for t in rows] == [50.0, 100.0, None]
