"""region_geo：多边形解析与点选（无数据库）。"""

import pytest

from app.services.region_geo import extract_outer_ring, point_in_polygon


def test_point_inside_triangle():
    tri = [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)]
    assert point_in_polygon(5.0, 2.0, tri) is True


def test_point_outside_triangle():
    tri = [(0.0, 0.0), (10.0, 0.0), (5.0, 10.0)]
    assert point_in_polygon(50.0, 50.0, tri) is False


def test_extract_outer_ring_coord_list():
    raw = [[120.0, 30.0], [121.0, 30.0], [120.5, 31.0]]
    ring = extract_outer_ring(raw)
    assert len(ring) == 3
    assert ring[0] == (120.0, 30.0)


def test_extract_outer_ring_geojson_polygon():
    raw = {"type": "Polygon", "coordinates": [[[120.0, 30.0], [121.0, 30.0], [120.5, 31.0]]]}
    ring = extract_outer_ring(raw)
    assert len(ring) == 3


def test_extract_outer_ring_too_few_points():
    with pytest.raises(ValueError, match="至少"):
        extract_outer_ring([[1.0, 2.0], [3.0, 4.0]])


def test_point_in_polygon_short_ring():
    assert point_in_polygon(0.0, 0.0, [(0, 0), (1, 1)]) is False
