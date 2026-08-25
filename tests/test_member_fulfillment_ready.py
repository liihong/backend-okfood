"""履约齐备判定：门店自提不要求默认配送地址。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.member.member_delivery_state_service import member_fulfillment_ready


def test_store_pickup_ready_without_address() -> None:
    """有起送日的门店自提会员，即使无默认地址也视为履约齐备。"""
    member = SimpleNamespace(
        id=1,
        store_pickup=True,
        delivery_start_date=date(2026, 8, 26),
    )
    assert member_fulfillment_ready(None, member) is True  # type: ignore[arg-type]


def test_home_delivery_not_ready_without_start_date() -> None:
    """配送到家无起送日则不齐备（不查地址）。"""
    member = SimpleNamespace(
        id=1,
        store_pickup=False,
        delivery_start_date=None,
    )
    assert member_fulfillment_ready(None, member) is False  # type: ignore[arg-type]
