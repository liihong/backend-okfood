"""顺丰推单系统消息：创单成功后取消的单计入失败。"""

from app.services.admin.admin_system_notification_service import combine_sf_push_notification_counts


def test_cancelled_success_counts_as_failed() -> None:
    """171 单里 169 成功、2 单已取消时，失败应为 2，而不是 0。"""
    total, success, failed = combine_sf_push_notification_counts(
        batch_total=169,
        batch_failed=0,
        db_total=171,
        db_success=169,
        db_failed=0,
    )
    assert (total, success, failed) == (171, 169, 2)


def test_create_failure_is_not_double_counted_with_cancel() -> None:
    total, success, failed = combine_sf_push_notification_counts(
        batch_total=171,
        batch_failed=2,
        db_total=171,
        db_success=169,
        db_failed=2,
    )
    assert (total, success, failed) == (171, 169, 2)


def test_unpersisted_batch_failure_still_counts() -> None:
    total, success, failed = combine_sf_push_notification_counts(
        batch_total=171,
        batch_failed=2,
        db_total=169,
        db_success=169,
        db_failed=0,
    )
    assert (total, success, failed) == (171, 169, 2)
