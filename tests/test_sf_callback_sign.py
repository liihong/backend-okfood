"""顺丰回调：验签、嵌套 payload 解析。"""

from __future__ import annotations

import pytest

from app.services.sf_callback_service import verify_sf_callback_signature
from app.services.sf_open.sign import generate_open_sign
from app.services.sf_open_notify_payload import (
    embedded_json_wire_strings,
    extract_order_status_deep,
    extract_shop_and_sf_order_ids,
    normalize_sf_callback_payload,
)


def test_verify_matches_generate_vector() -> None:
    body = '{"a":1,"order_status":2}'
    dev_id = 123456
    key = "test-secret-key"
    sign = generate_open_sign(body, dev_id, key)
    assert verify_sf_callback_signature(body, sign, [dev_id], key)


@pytest.mark.parametrize("suffix", ("\n", "\r\n"))
def test_verify_trailing_newlines_still_ok(suffix: str) -> None:
    body = '{"sf_order_id":"x","shop_order_id":"y"}'
    dev_id = 99
    key = "k"
    sign = generate_open_sign(body, dev_id, key)
    assert verify_sf_callback_signature(body + suffix, sign, [dev_id], key)


def test_sign_query_space_instead_of_plus() -> None:
    """模拟 query 解码后 ``+`` 变空格."""
    body = '{"x":"y"}'
    dev_id = 1
    key = "secret"
    sign = generate_open_sign(body, dev_id, key)
    broken = sign.replace("+", " ")
    assert verify_sf_callback_signature(body, broken, [dev_id], key)


def test_dev_id_from_json_when_env_would_be_wrong() -> None:
    body = '{"dev_id":777,"shop_order_id":"o1"}'
    dev_in_body = 777
    key = "same-key"
    sign = generate_open_sign(body, dev_in_body, key)
    assert verify_sf_callback_signature(body, sign, [999, dev_in_body], key)
    assert not verify_sf_callback_signature(body, sign, [999], key)


def test_normalize_post_data_json_string() -> None:
    inner = '{"shop_order_id":"OKF20260521abc","sf_order_id":"SF123","order_status":17}'
    payload = {"post_data": inner}
    norm = normalize_sf_callback_payload(payload)
    shop, sf = extract_shop_and_sf_order_ids(norm)
    assert shop == "OKF20260521abc"
    assert sf == "SF123"
    assert extract_order_status_deep(norm) == 17


def test_verify_form_post_data_field() -> None:
    inner = '{"shop_order_id":"o1","order_status":17,"dev_id":42}'
    dev_id = 42
    key = "tenant-secret"
    sign = generate_open_sign(inner, dev_id, key)
    raw_body = f"post_data={inner}"
    payload = normalize_sf_callback_payload({"post_data": inner})
    assert verify_sf_callback_signature(raw_body, sign, [dev_id], key, payload=payload)
    assert inner in embedded_json_wire_strings(payload)


def test_nested_data_dict_order_status() -> None:
    payload = {"data": {"order_status": 17, "shop_order_id": "s1", "sf_order_id": "sf9"}}
    norm = normalize_sf_callback_payload(payload)
    assert extract_order_status_deep(norm) == 17
    shop, sf = extract_shop_and_sf_order_ids(norm)
    assert shop == "s1"
    assert sf == "sf9"
