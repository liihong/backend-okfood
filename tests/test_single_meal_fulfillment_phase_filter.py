"""单次点餐管理端：发货 Tab 过滤口径（待发货 vs 待自提）。"""

from __future__ import annotations

from app.services.order.single_meal_order_service import (
    _ADMIN_SINGLE_FULFILLMENT_PHASES,
    _apply_admin_single_fulfillment_phase_filter,
)


def _filter_text(fulfillment_phase: str) -> str:
    filters: list = []
    _apply_admin_single_fulfillment_phase_filter(filters, fulfillment_phase)
    return " ".join(str(f) for f in filters).lower()


def test_pending_pickup_in_admin_fulfillment_phases() -> None:
    assert "pending_pickup" in _ADMIN_SINGLE_FULFILLMENT_PHASES


def test_pending_ship_excludes_store_pickup() -> None:
    text = _filter_text("pending_ship")
    assert "store_pickup" in text
    assert "false" in text or "0" in text
    assert "fulfillment_status" in text


def test_pending_pickup_only_store_pickup() -> None:
    text = _filter_text("pending_pickup")
    assert "store_pickup" in text
    assert "true" in text or "1" in text
    assert "fulfillment_status" in text
