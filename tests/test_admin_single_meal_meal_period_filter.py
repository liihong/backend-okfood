"""零售订单列表按午餐/晚餐过滤。

curl 示例（需管理员 Token）：

curl -sS "http://127.0.0.1:8000/api/admin/orders/daily/single-meals?store_id=1&delivery_date=2026-11-16&meal_period=dinner" \\
  -H "Authorization: Bearer $TOKEN"
"""

from datetime import date

import pytest
from fastapi import HTTPException

from app.services.order.single_meal_order_service import (
    _admin_store_single_meal_scope_filters_for_delivery_day,
)


def _compiled(filters) -> str:
    return " ".join(str(f.compile(compile_kwargs={"literal_binds": True})) for f in filters)


def test_scope_filters_dinner_only() -> None:
    filters = _admin_store_single_meal_scope_filters_for_delivery_day(
        store_id=1,
        delivery_day=date(2026, 11, 16),
        q=None,
        delivery_phase=None,
        meal_period="dinner",
    )
    sql = _compiled(filters)
    assert "meal_period" in sql
    assert "dinner" in sql


def test_scope_filters_blank_meal_period_keeps_both() -> None:
    filters = _admin_store_single_meal_scope_filters_for_delivery_day(
        store_id=1,
        delivery_day=date(2026, 11, 16),
        q=None,
        delivery_phase=None,
        meal_period="",
    )
    assert "meal_period" not in _compiled(filters)


def test_scope_filters_reject_unknown_meal_period() -> None:
    with pytest.raises(HTTPException) as exc:
        _admin_store_single_meal_scope_filters_for_delivery_day(
            store_id=1,
            delivery_day=date(2026, 11, 16),
            q=None,
            delivery_phase=None,
            meal_period="brunch",
        )
    assert exc.value.status_code == 400
