import math


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """球面距离近似（米），用于清单内排序，非导航最优路径。"""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))
