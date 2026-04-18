"""地图概览会员点：当日送达字段序列化。"""

from app.schemas.delivery_region import MapOverviewMemberMarkerOut


def test_marker_delivered_today_defaults_false():
    m = MapOverviewMemberMarkerOut(id=1, name="n", phone="1", area="东区")
    assert m.delivered_today is False
    assert m.model_dump(mode="json")["delivered_today"] is False


def test_marker_delivered_today_true_in_dump():
    m = MapOverviewMemberMarkerOut(id=1, name="n", phone="1", area="东区", delivered_today=True)
    assert m.model_dump(mode="json")["delivered_today"] is True
