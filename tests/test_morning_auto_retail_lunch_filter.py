"""零售单不再参与 08:50 定时任务（圈选函数仅预留）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.delivery import sf_same_city_service as svc


def test_nightly_auto_push_does_not_invoke_retail_relay() -> None:
    """08:50 只推大表，不调用零售推接驳。"""
    db = MagicMock()
    with (
        patch.object(svc, "_sf_nightly_auto_push_global_lock") as lock_ctx,
        patch.object(svc, "today_shanghai", return_value=__import__("datetime").date(2026, 3, 18)),
        patch.object(svc, "select") as mock_select,
        patch.object(svc, "auto_push_sf_today_business_day_for_store") as auto_push,
        patch(
            "app.services.admin.admin_system_notification_service.upsert_sf_nightly_push_notification",
        ),
        patch(
            "app.services.order.single_meal_order_service.push_morning_auto_retail_orders_to_relay_shop",
        ) as retail_push,
    ):
        lock_ctx.return_value.__enter__ = MagicMock(return_value=True)
        lock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        chain = MagicMock()
        chain.where.return_value = chain
        mock_select.return_value = chain
        db.scalars.return_value.all.return_value = [7]
        auto_push.return_value = svc.SfNightlyAutoPushStoreResult(total=1, success=1)
        svc.run_sf_nightly_auto_push_for_all_stores(db)
        auto_push.assert_called_once()
        retail_push.assert_not_called()