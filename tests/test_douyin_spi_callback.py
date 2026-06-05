"""抖音 SPI 回调与验签单元测试。"""

from __future__ import annotations

import json

from app.integrations.douyin_spi_sign import (
    compute_spi_new_signature,
    compute_spi_old_signature,
    verify_spi_signature,
)
from app.services.douyin.spi_callback_service import parse_async_cancel_fulfil_items


def test_spi_new_signature_matches_official_example():
    secret = "yyyyyy"
    query = {"client_key": "xxxxxx", "timestamp": "1624293280123"}
    body = b"zzzzzz"
    expected = compute_spi_new_signature(client_secret=secret, query=query, body=body)
    assert verify_spi_signature(
        client_secret=secret,
        query=query,
        body=body,
        header_sign=expected,
        query_sign=None,
    )


def test_spi_old_signature_md5():
    secret = "yyyyyy"
    query = {"client_key": "xxxxxx", "timestamp": "1624293280123"}
    body = b"zzzzzz"
    expected = compute_spi_old_signature(client_secret=secret, query=query, body=body)
    assert verify_spi_signature(
        client_secret=secret,
        query=query,
        body=body,
        header_sign=None,
        query_sign=expected,
    )


def test_parse_async_cancel_fulfil_direct_fields():
    payload = {
        "certificate_id": "7091180835810052103",
        "verify_id": "7091478021421631519",
        "order_id": "order-1",
        "result_code": 0,
    }
    items = parse_async_cancel_fulfil_items(payload)
    assert len(items) == 1
    assert items[0].certificate_id == "7091180835810052103"
    assert items[0].verify_id == "7091478021421631519"


def test_parse_async_cancel_fulfil_cancel_results():
    payload = {
        "cancel_results": [
            {
                "certificate_id": "c1",
                "verify_id": "v1",
                "order_id": "o1",
                "result_code": 0,
            }
        ]
    }
    items = parse_async_cancel_fulfil_items(payload)
    assert len(items) == 1
    assert items[0].certificate_id == "c1"


def test_parse_async_cancel_fulfil_verify_cancel_msg():
    msg = {
        "status": "SUCCESS",
        "order_info": {"order_id": "10001"},
        "item_order_id": "80001",
    }
    payload = {"type": "verify_cancel", "msg": json.dumps(msg, ensure_ascii=False)}
    items = parse_async_cancel_fulfil_items(payload)
    assert len(items) == 1
    assert items[0].order_id == "10001"
    assert items[0].certificate_id == "80001"
