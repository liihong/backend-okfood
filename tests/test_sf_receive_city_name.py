"""顺丰 receive 城市/地址解析：坐标与文案不一致时须以坐标逆地理为准。"""

from types import SimpleNamespace

from app.services.shared.amap import RegeoSnapshot
from app.services.delivery.sf_same_city_service import (
    _sf_receive_city_name,
    _sf_receive_full_address,
)


def _row(**kwargs):
    base = dict(
        map_location_text="互联网大厦517",
        recv_address="互联网大厦517",
        door_detail="",
        recv_building="",
        recv_lng=114.885119,
        recv_lat=33.425573,
        address_line="互联网大厦517",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_sf_receive_city_name_uses_regeo_when_text_has_no_city(monkeypatch):
    snap = RegeoSnapshot(
        pca_prefix_line="河南省周口市项城市",
        province="河南省",
        city="周口市",
        district="项城市",
    )
    monkeypatch.setattr(
        "app.services.delivery.sf_same_city_service._row_regeo_snapshot",
        lambda _row: snap,
    )
    city = _sf_receive_city_name(_row(), "新乡市")
    assert city == "周口市"


def test_sf_receive_full_address_prefixes_regeo_when_missing_admin(monkeypatch):
    snap = RegeoSnapshot(
        pca_prefix_line="河南省周口市项城市",
        province="河南省",
        city="周口市",
        district="项城市",
    )
    monkeypatch.setattr(
        "app.services.delivery.sf_same_city_service._row_regeo_snapshot",
        lambda _row: snap,
    )
    addr = _sf_receive_full_address(_row())
    assert addr == "河南省周口市项城市 互联网大厦517"


def test_sf_receive_city_name_prefers_parsed_text_over_regeo(monkeypatch):
    monkeypatch.setattr(
        "app.services.delivery.sf_same_city_service._row_regeo_snapshot",
        lambda _row: RegeoSnapshot(
            pca_prefix_line="河南省周口市项城市",
            province="河南省",
            city="周口市",
            district="项城市",
        ),
    )
    city = _sf_receive_city_name(
        _row(map_location_text="河南省新乡市红旗区某某小区", recv_address="河南省新乡市红旗区某某小区"),
        "新乡市",
    )
    assert city == "新乡市"
