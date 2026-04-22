"""
骑手当日任务列表的排序参考点与距离度量。

业务约定（与产品「由近到远、不绕路」表述对齐）：
---------------------------------------------------------------------------
1. **锚点（排序原点）**
   - 若后台已配置门店经纬度，则锚点为门店坐标（出餐/取餐中心）。
   - 否则退回「当前批次会员默认地址坐标的算术平均」（质心），与历史实现一致，避免无配置时无法排序。

2. **距离**
   - 使用 Haversine 大圆距离（米），与 `app.services.geo.haversine_m` 一致。
   - 不做道路网最短路、不做 TSP 回路优化；该距离是「直线」意义上的远近。

3. **「不绕路」**
   - 本模块**不**求解车辆路径问题；仅按「离锚点直线距离升序」排列。
   - 该顺序可理解为从门店出发的辐射式访问次序，不会在算法层引入刻意折返；
 实际道路绕行由导航软件处理。

单测请针对本模块的纯函数编写，避免依赖数据库。
"""

from __future__ import annotations

from app.models.member import Member
from app.models.member_address import MemberAddress
from app.services.geo import haversine_m


def centroid_of_member_addresses(
    members: list[Member],
    defaults: dict[int, MemberAddress | None],
) -> tuple[float | None, float | None]:
    """会员默认地址坐标质心；无有效坐标时返回 (None, None)。"""
    pts: list[tuple[float, float]] = []
    for m in members:
        a = defaults.get(m.id)
        if a is not None and a.lng is not None and a.lat is not None:
            pts.append((float(a.lng), float(a.lat)))
    if not pts:
        return None, None
    lng = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lng, lat


def reference_lng_lat_for_task_sorting(
    store_lng: float | None,
    store_lat: float | None,
    members: list[Member],
    defaults: dict[int, MemberAddress | None],
) -> tuple[float | None, float | None]:
    """
    任务排序用锚点经纬度。

    优先门店；门店缺一或均未配置时，退回质心。
    """
    if store_lng is not None and store_lat is not None:
        return float(store_lng), float(store_lat)
    return centroid_of_member_addresses(members, defaults)


def distance_from_anchor_m(
    anchor_lng: float | None,
    anchor_lat: float | None,
    addr_lng: float | None,
    addr_lat: float | None,
) -> float | None:
    """锚点到收件坐标的距离（米）；任一端缺失则无法计算，返回 None。"""
    if anchor_lng is None or anchor_lat is None:
        return None
    if addr_lng is None or addr_lat is None:
        return None
    return haversine_m(anchor_lng, anchor_lat, float(addr_lng), float(addr_lat))


def task_sort_key(sort_distance_m: float | None) -> tuple[bool, float]:
    """
    `CourierTaskMemberOut` 列表排序键：无距离的记录排在后面，其次按米数升序。
    """
    return (sort_distance_m is None, sort_distance_m or 0.0)
