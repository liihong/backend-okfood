"""配送区域多边形解析与点选（GCJ-02 平面近似）。"""

from __future__ import annotations

from typing import Any


def extract_outer_ring(polygon_json: Any) -> list[tuple[float, float]]:
    """从 polygon_json 得到外环顶点 [(lng, lat), ...]，至少 3 点。"""
    if polygon_json is None:
        raise ValueError("polygon_json 不能为空")

    if isinstance(polygon_json, list):
        ring = _ring_from_coord_list(polygon_json)
    elif isinstance(polygon_json, dict):
        ring = _ring_from_geojson(polygon_json)
    else:
        raise ValueError("polygon_json 须为 JSON 数组或 GeoJSON 对象")

    if len(ring) < 3:
        raise ValueError("多边形至少需要 3 个顶点")

    return ring


def _ring_from_coord_list(raw: list[Any]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for item in raw:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            raise ValueError("顶点格式须为 [lng, lat]")
        lng, lat = float(item[0]), float(item[1])
        out.append((lng, lat))
    return out


def _ring_from_geojson(obj: dict[str, Any]) -> list[tuple[float, float]]:
    gtype = obj.get("type")
    if gtype == "Polygon":
        coords = obj.get("coordinates")
        if not coords or not isinstance(coords, list) or not coords[0]:
            raise ValueError("GeoJSON Polygon.coordinates 无效")
        return _ring_from_coord_list(coords[0])
    if gtype == "Feature":
        geom = obj.get("geometry")
        if not isinstance(geom, dict):
            raise ValueError("GeoJSON Feature.geometry 无效")
        return _ring_from_geojson(geom)
    raise ValueError("仅支持 GeoJSON Polygon或 Feature(Polygon)")


def point_in_polygon(lng: float, lat: float, ring: list[tuple[float, float]]) -> bool:
    """射线法判断点是否在有向闭合多边形内（不含边界精细处理；与高德 GCJ-02 平面坐标一致即可）。"""
    n = len(ring)
    if n < 3:
        return False
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-18) + xi):
            inside = not inside
        j = i
    return inside
