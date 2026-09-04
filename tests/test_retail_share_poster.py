"""零售商品分享海报：scene 编解码。"""

from app.integrations.wechat_mini import _wxacode_error_message
from app.services.client.retail_share_poster_service import (
    encode_retail_share_scene,
    parse_retail_share_scene,
)


def test_encode_retail_share_scene() -> None:
    assert encode_retail_share_scene(42) == "r42"
    assert encode_retail_share_scene(1) == "r1"
    assert parse_retail_share_scene(encode_retail_share_scene(99)) == 99


def test_parse_retail_share_scene() -> None:
    assert parse_retail_share_scene("r42") == 42
    assert parse_retail_share_scene("R9") == 9
    assert parse_retail_share_scene("123") == 123
    assert parse_retail_share_scene("r%34%32") == 42
    assert parse_retail_share_scene("") is None
    assert parse_retail_share_scene("abc") is None
    assert parse_retail_share_scene("r0") is None


def test_wxacode_error_message_maps_known_codes() -> None:
    assert "未发布" in _wxacode_error_message(41030, "invalid page")
    assert "小程序码" in _wxacode_error_message(12345, "foo")
