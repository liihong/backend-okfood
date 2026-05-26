"""管理端系统消息：创建、查询、确认。"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.admin_system_notification import AdminSystemNotification

KIND_SF_NIGHTLY_PUSH = "sf_nightly_push"


def _sf_nightly_push_message(*, total: int, success: int, failed: int, skip_reason: str | None) -> str:
    if skip_reason:
        return f"今日自动推单未执行：{skip_reason}"
    return f"今日共推送 {total} 单，成功 {success} 单，失败 {failed} 单"


def upsert_sf_nightly_push_notification(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    total: int,
    success: int,
    failed: int,
    skip_reason: str | None = None,
) -> AdminSystemNotification:
    """顺丰 08:50 自动推单结束后写入/更新当日门店摘要（同店同日仅一条）。"""
    kind = KIND_SF_NIGHTLY_PUSH
    title = f"顺丰自动推单 · {business_date.isoformat()}"
    message = _sf_nightly_push_message(
        total=total, success=success, failed=failed, skip_reason=skip_reason
    )
    row = db.scalar(
        select(AdminSystemNotification).where(
            AdminSystemNotification.store_id == int(store_id),
            AdminSystemNotification.kind == kind,
            AdminSystemNotification.business_date == business_date,
        )
    )
    if row is None:
        row = AdminSystemNotification(
            store_id=int(store_id),
            kind=kind,
            business_date=business_date,
            title=title,
            message=message,
            total_count=int(total),
            success_count=int(success),
            failed_count=int(failed),
            skip_reason=skip_reason,
        )
        db.add(row)
    else:
        row.title = title
        row.message = message
        row.total_count = int(total)
        row.success_count = int(success)
        row.failed_count = int(failed)
        row.skip_reason = skip_reason
        # 重新跑任务时刷新摘要，但不自动清除已确认状态
    db.flush()
    return row


def list_admin_system_notifications(
    db: Session,
    *,
    store_id: int,
    unacknowledged_only: bool = False,
    limit: int = 20,
) -> list[AdminSystemNotification]:
    stmt = (
        select(AdminSystemNotification)
        .where(AdminSystemNotification.store_id == int(store_id))
        .order_by(AdminSystemNotification.created_at.desc())
        .limit(max(1, min(int(limit), 100)))
    )
    if unacknowledged_only:
        stmt = stmt.where(AdminSystemNotification.acknowledged_at.is_(None))
    return list(db.scalars(stmt).all())


def count_unacknowledged_admin_system_notifications(db: Session, *, store_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AdminSystemNotification)
            .where(
                AdminSystemNotification.store_id == int(store_id),
                AdminSystemNotification.acknowledged_at.is_(None),
            )
        )
        or 0
    )


def acknowledge_admin_system_notification(
    db: Session,
    *,
    notification_id: int,
    store_id: int,
    admin_username: str,
) -> AdminSystemNotification:
    row = db.get(AdminSystemNotification, int(notification_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="系统消息不存在")
    if row.acknowledged_at is not None:
        return row
    row.acknowledged_at = beijing_now_naive()
    row.acknowledged_by = str(admin_username or "").strip() or None
    db.commit()
    db.refresh(row)
    return row


def admin_system_notification_to_dict(row: AdminSystemNotification) -> dict:
    return {
        "id": int(row.id),
        "store_id": int(row.store_id),
        "kind": row.kind,
        "business_date": row.business_date.isoformat() if row.business_date else "",
        "title": row.title,
        "message": row.message,
        "total": int(row.total_count),
        "success": int(row.success_count),
        "failed": int(row.failed_count),
        "skip_reason": row.skip_reason,
        "acknowledged_at": row.acknowledged_at.isoformat(sep=" ", timespec="seconds")
        if row.acknowledged_at
        else None,
        "acknowledged_by": row.acknowledged_by,
        "created_at": row.created_at.isoformat(sep=" ", timespec="seconds") if row.created_at else None,
    }
