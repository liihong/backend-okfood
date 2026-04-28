"""courier_task_sorting：最近邻线路排序（无 DB）。"""

from app.schemas.courier import CourierTaskMemberOut
from app.services.courier_task_sorting import (
    centroid_from_task_rows,
    order_task_rows_by_nearest_neighbor,
)


def _row(mid: int, lng: float, lat: float, dist: float | None) -> CourierTaskMemberOut:
    return CourierTaskMemberOut(
        member_id=mid,
        phone="",
        name="",
        address="",
        lng=lng,
        lat=lat,
        area="",
        remarks=None,
        daily_meal_units=1,
        sort_distance_m=dist,
        is_delivered=False,
    )


def test_nn_follows_greedy_chain_from_depot():
    """ depot 在原点，三点呈链 A(近)→B(中)→C(远)，NN 应为 A,B,C 而非按距原点排序打乱。 """
    depot_lng, depot_lat = 121.0, 31.0
    rows = [
        _row(1, 121.01, 31.0, 100.0),
        _row(2, 121.02, 31.0, 200.0),
        _row(3, 121.03, 31.0, 300.0),
    ]
    order_task_rows_by_nearest_neighbor(rows, depot_lng, depot_lat)
    assert [r.member_id for r in rows] == [1, 2, 3]


def test_nn_radial_vs_chain_off_axis():
    """侧向远一点但沿前进方向更近的点应先送：相对纯径向可能顺序不同。"""
    depot_lng, depot_lat = 121.0, 31.0
    # B 离 depot 比 A 远，但从 A 走到 B 比从 depot 直接去另一侧的 C 更符合 NN
    rows = [
        _row(1, 121.005, 31.0, None),
        _row(2, 121.015, 31.0, None),
        _row(3, 121.002, 31.01, None),
    ]
    order_task_rows_by_nearest_neighbor(rows, depot_lng, depot_lat)
    ids = [r.member_id for r in rows]
    assert ids[0] == 1  # 离 depot 最近
    assert set(ids) == {1, 2, 3}


def test_rows_without_coords_trail():
    rows = [
        _row(1, None, None, None),
        _row(2, 121.01, 31.0, 50.0),
    ]
    order_task_rows_by_nearest_neighbor(rows, 121.0, 31.0)
    assert rows[0].member_id == 2
    assert rows[1].member_id == 1


def test_no_depot_falls_back_to_sort_distance():
    rows = [
        _row(2, 121.0, 31.0, 200.0),
        _row(1, 121.0, 31.0, 100.0),
    ]
    order_task_rows_by_nearest_neighbor(rows, None, None)
    assert [r.member_id for r in rows] == [1, 2]


def test_centroid_from_task_rows_empty():
    assert centroid_from_task_rows([]) == (None, None)
