"""管理端系统消息：创建、查询、确认。"""

from __future__ import annotations

from datetime import date, time

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive, now_shanghai, today_shanghai
from app.models.admin_system_notification import AdminSystemNotification
from app.models.sf_same_city_push import SfSameCityPush

# 与 sf_same_city_pushes.push_kind 中「大表合并」取值一致
_SF_PUSH_KIND_DELIVERY_SHEET = "delivery_sheet"

KIND_SF_NIGHTLY_PUSH = "sf_nightly_push"
# 顺丰大表快照已成立后，小程序侧又让会员「当日重新应配送」时需客服人工并入顺丰链路
KIND_DELIVERY_SHEET_MANUAL_ATTENTION = "delivery_sheet_manual_attention"
# 小程序自助购卡已缴、待客服确认起送日并同步入账
KIND_MINIPROGRAM_CARD_ORDER_PENDING = "miniprogram_card_order_pending"


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


def store_should_prompt_manual_delivery_sheet_reconciliation(db: Session, *, store_id: int) -> bool:
    """
    是否适合对「小程序侧恢复当日应配送」发客服跟进提醒。

    - 先满足：已过早间推单常见时点 (08:50) 或当日已有成功的大表合并推单（与原先一致）。
    - 若当日存在未取消且创单成功的顺丰记录：仅当 **仍有未履约完毕的推单** 时继续提醒；
      当日全部推单均已妥投/履约完成后不再发送（餐送完不再刷屏）。
    - 若当日无任何有效顺丰推单：仍仅按上一条时间/大表快照条件判断（无顺丰时不做履约门禁）。
    """
    # 懒加载：避免 admin_system_notification → sf_order_fulfillment → … → member_service 循环 import
    from app.services.sf_order_fulfillment_service import (
        store_all_sf_pushes_fulfilled_on_delivery_date,
        store_has_active_sf_push_on_delivery_date,
    )

    sid = int(store_id)
    if sid <= 0:
        return False
    biz_today = today_shanghai()
    wall = now_shanghai()
    baseline_open = False
    if wall.time() >= time(8, 50):
        baseline_open = True
    else:
        row_id = db.scalar(
            select(SfSameCityPush.id).where(
                SfSameCityPush.store_id == sid,
                SfSameCityPush.delivery_date == biz_today,
                SfSameCityPush.error_code == 0,
                or_(
                    SfSameCityPush.push_kind.is_(None),
                    SfSameCityPush.push_kind == "",
                    SfSameCityPush.push_kind == _SF_PUSH_KIND_DELIVERY_SHEET,
                ),
            ).limit(1)
        )
        baseline_open = row_id is not None

    if not baseline_open:
        return False

    if store_has_active_sf_push_on_delivery_date(db, store_id=sid, delivery_date=biz_today):
        if store_all_sf_pushes_fulfilled_on_delivery_date(db, store_id=sid, delivery_date=biz_today):
            return False
    return True


def create_delivery_sheet_manual_attention_notification(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    action_labels_cn: list[str],
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
) -> AdminSystemNotification | None:
    """新增一条配送大表跟进提醒（不 upsert）；message 总长受 500 字限制。"""
    sid = int(store_id)
    if sid <= 0:
        return None
    if not action_labels_cn:
        return None
    label_join = "、".join(str(x).strip() for x in action_labels_cn if str(x).strip())
    if not label_join:
        return None

    phones = str(member_phone or "").strip()[:32]
    if not phones:
        phones = "(无手机号)"

    naming = str(member_name or "").strip()
    naming = naming[:40] + ("…" if len(naming) > 40 else "")

    title = f"大表顺丰需人工跟进 · {business_date.isoformat()}"
    # 说明：快照不自动追加，客服合并大表并补骑手/顺丰信息
    body = (
        f"小程序操作「{label_join}」，会员 mid={int(member_id)} {phones} "
        f"{('「' + naming + '」') if naming else ''}"
        "今日可能已计入大表但不在早间顺丰快照，请并入配送并补链路。"
    )
    if len(body) > 500:
        body = body[:497] + "…"

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_DELIVERY_SHEET_MANUAL_ATTENTION,
        business_date=business_date,
        title=title[:200],
        message=body,
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=None,
    )
    db.add(row)
    db.flush()
    return row


def create_miniprogram_card_order_pending_notification(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    card_kind: str,
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
    delivery_start_date: date | None,
) -> AdminSystemNotification | None:
    """小程序自助购卡支付成功：提醒客服确认起送日并在开卡工单中同步入账。"""
    sid = int(store_id)
    if sid <= 0:
        return None

    biz = today_shanghai()
    phones = str(member_phone or "").strip()[:32] or "(无手机号)"
    naming = str(member_name or "").strip()
    naming = naming[:40] + ("…" if len(naming) > 40 else "")

    kind_label = str(card_kind or "").strip() or "会员卡"
    ds_text = delivery_start_date.isoformat() if delivery_start_date else "未填写"
    title = f"小程序自助购卡待确认 · 工单#{int(order_id)}"
    body = (
        f"会员 mid={int(member_id)} {phones} "
        f"{('「' + naming + '」') if naming else ''}"
        f"已微信支付购买{kind_label}，用户所选起送日 {ds_text}。"
        "用户可能在小程序完善配送信息中已填写起送日；"
        "请在「开卡工单」核对起送日与配送方式后点击「确认入账」。"
    )
    if len(body) > 500:
        body = body[:497] + "…"

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_MINIPROGRAM_CARD_ORDER_PENDING,
        business_date=biz,
        title=title[:200],
        message=body,
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=None,
    )
    db.add(row)
    db.flush()
    return row


def try_notify_delivery_sheet_manual_attention(
    db: Session,
    *,
    store_id: int,
    action_labels_cn: list[str],
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
) -> AdminSystemNotification | None:
    """
    在 ``store_should_prompt_manual_delivery_sheet_reconciliation`` 为真时写入一条跟进提醒；
    与 ``upsert_sf_nightly_push_notification`` 不同，每次事件插入新行，便于客服逐条消除。

    当日顺丰有效推单若已全部履约完毕，守门为假，不再写入（餐送完不再通知）。
    """
    if not store_should_prompt_manual_delivery_sheet_reconciliation(db, store_id=store_id):
        return None
    biz = today_shanghai()
    return create_delivery_sheet_manual_attention_notification(
        db,
        store_id=int(store_id),
        business_date=biz,
        action_labels_cn=action_labels_cn,
        member_id=int(member_id),
        member_phone=member_phone,
        member_name=member_name,
    )


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
