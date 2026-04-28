"""顺丰回调验签：与开放平台 ``json & dev_id & key`` → MD5 小写 hex → Base64 一致。"""

from __future__ import annotations

import pytest

from app.services.sf_callback_service import verify_sf_callback_signature
from app.services.sf_open.sign import generate_open_sign


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
    """报文带 ``dev_id`` 时与文档「按 dev_id 取密钥」对齐；此处仅验同一密钥下不同 dev 段."""
    body = '{"dev_id":777,"shop_order_id":"o1"}'
    dev_in_body = 777
    key = "same-key"
    sign = generate_open_sign(body, dev_in_body, key)
    assert verify_sf_callback_signature(body, sign, [999, dev_in_body], key)
    assert not verify_sf_callback_signature(body, sign, [999], key)


def test_verify_form_body_cancel_callback_style() -> None:
    """顺丰取消类回调常见为 ``x-www-form-urlencoded``，摘要放在 query 或与 body 中 ``sign`` 一致。"""
    dev_id = 4242
    key = "sek"
    post_without_sign = "sf_order_id=JSX&shop_order_id=OK1&url_index=sf_cancel&order_status=2"
    sign_val = generate_open_sign(post_without_sign, dev_id, key)
    raw_post = post_without_sign + f"&sign={sign_val}"
    assert verify_sf_callback_signature(raw_post, sign_val, [dev_id], key)
