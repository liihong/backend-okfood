"""后厨日总份数：非订阅配送日静默跳过。"""

from datetime import date
from unittest.mock import MagicMock

from app.services.store_kitchen_plan_service import set_menu_day_total_stock_by_business_date


def test_set_menu_day_total_stock_skips_sunday_without_db_write(monkeypatch):
    """周日无排单场景：不查周菜单槽位，直接返回请求份数。"""
    called = {"sync": False}

    def _fake_sync(*_args, **_kwargs):
        called["sync"] = True
        return True

    monkeypatch.setattr(
        "app.services.store_kitchen_plan_service.sync_kitchen_planned_to_menu_day_total_stock",
        _fake_sync,
    )

    # 2026-06-14 为周日
    result = set_menu_day_total_stock_by_business_date(
        MagicMock(),
        store_id=1,
        business_date=date(2026, 6, 14),
        total_stock=120,
    )

    assert result == 120
    assert called["sync"] is False
