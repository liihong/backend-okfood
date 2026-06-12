"""管理端系统消息：创建、查询、确认。"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
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
# 单次零售（单次点餐）微信支付成功，待客服在订单管理推送配送
KIND_SINGLE_MEAL_ORDER_PAID = "single_meal_order_paid"
KIND_STORE_RETAIL_ORDER_PAID = "store_retail_order_paid"
# 每日多份但剩余次数不足当日份数，未进配送大表，待客服联系确认续卡
KIND_MEMBER_INSUFFICIENT_BALANCE_FOR_DELIVERY = "member_insufficient_balance_for_delivery"

logger = logging.getLogger(__name__)


def _mask_phone_middle_four(phone: str | None) -> str:
    """系统消息展示用手机号：中间四位脱敏（如 138****8000）。"""
    raw = str(phone or "").strip()
    if not raw:
        return "无手机号"
    digits = re.sub(r"\D", "", raw)
    if len(digits) >= 7:
        return f"{digits[:3]}****{digits[-4:]}"
    return raw[:20]


def _system_notification_message_phone_unmasked(message: str | None) -> bool:
    """多行正文中「手机号：」行未含 **** 时视为需重新生成（补脱敏）。"""
    for line in str(message or "").splitlines():
        if not line.startswith("手机号："):
            continue
        val = line[len("手机号：") :].strip()
        if not val or val == "无手机号":
            return False
        return "****" not in val
    return False


def _sf_nightly_push_message(*, total: int, success: int, failed: int, skip_reason: str | None) -> str:
    if skip_reason:
        return f"今日自动推单未执行：{skip_reason}"
    return f"今日共推送 {total} 单，成功 {success} 单，失败 {failed} 单"


def _sf_push_batch_message(*, total: int, success: int, failed: int) -> str:
    return f"本次推送 {int(total)} 单，成功 {int(success)} 单，失败 {int(failed)} 单"


def upsert_sf_push_batch_notification(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    total: int,
    success: int,
    failed: int,
    title_prefix: str = "顺丰推单",
) -> AdminSystemNotification:
    """手动/重试推单批次结束后写入或更新当日门店摘要（同店同日 kind 仅一条）。"""
    kind = KIND_SF_NIGHTLY_PUSH
    title = f"{title_prefix} · {business_date.isoformat()}"
    message = _sf_push_batch_message(total=total, success=success, failed=failed)
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
            skip_reason=None,
        )
        db.add(row)
    else:
        row.title = title
        row.message = message
        row.total_count = int(total)
        row.success_count = int(success)
        row.failed_count = int(failed)
        row.skip_reason = None
    db.flush()
    return row


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


def _delivery_sheet_manual_attention_event_line(
    *,
    action_labels_cn: list[str],
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
) -> str:
    """单条小程序侧操作摘要（用于合并进当日唯一系统消息）。"""
    label_join = "、".join(str(x).strip() for x in action_labels_cn if str(x).strip())
    if not label_join:
        return ""
    phones = str(member_phone or "").strip()[:32] or "(无手机号)"
    naming = str(member_name or "").strip()
    naming = naming[:40] + ("…" if len(naming) > 40 else "")
    name_part = f"「{naming}」" if naming else ""
    return (
        f"小程序操作「{label_join}」，会员 mid={int(member_id)} {phones} {name_part}"
        "今日可能已计入大表但不在早间顺丰快照，请并入配送并补链路。"
    )


def _append_message_capped(base: str, addon: str, *, max_len: int = 500) -> str:
    base = (base or "").strip()
    addon = (addon or "").strip()
    if not addon:
        return base
    merged = f"{base}\n{addon}" if base else addon
    if len(merged) <= max_len:
        return merged
    return merged[: max_len - 1] + "…"


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
    """写入或合并当日配送大表跟进提醒（同店同日 kind 唯一，重复操作追加 message）。"""
    sid = int(store_id)
    if sid <= 0:
        return None
    event_line = _delivery_sheet_manual_attention_event_line(
        action_labels_cn=action_labels_cn,
        member_id=member_id,
        member_phone=member_phone,
        member_name=member_name,
    )
    if not event_line:
        return None

    title = f"大表顺丰需人工跟进 · {business_date.isoformat()}"
    existing = db.scalars(
        select(AdminSystemNotification)
        .where(
            AdminSystemNotification.store_id == sid,
            AdminSystemNotification.kind == KIND_DELIVERY_SHEET_MANUAL_ATTENTION,
            AdminSystemNotification.business_date == business_date,
        )
        .limit(1)
    ).first()

    if existing is not None:
        existing.title = title[:200]
        existing.message = _append_message_capped(existing.message or "", event_line)
        db.flush()
        return existing

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_DELIVERY_SHEET_MANUAL_ATTENTION,
        business_date=business_date,
        title=title[:200],
        message=event_line[:500] if len(event_line) <= 500 else event_line[:497] + "…",
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=None,
    )
    db.add(row)
    db.flush()
    return row


def _miniprogram_card_order_pending_notification_marker(order_id: int) -> str:
    """skip_reason 存工单 id，便于去重、跳转与入账后消隐。"""
    return f"card_order_id:{int(order_id)}"


def _miniprogram_card_order_pending_business_date(order_id: int) -> date:
    """
    每工单独占 (store_id, kind, business_date) 唯一键。

    库表对 kind=miniprogram_card_order_pending 与顺丰日摘要等同约束「同店同日一条」；
    购卡待审批须按工单区分，故用稳定映射日期，真实业务日见 title/message。
    """
    return date(2000, 1, 1) + timedelta(days=int(order_id))


_MINIPROGRAM_CARD_ORDER_ID_MARKER_RE = re.compile(r"^card_order_id:(\d+)$")


def _order_id_from_miniprogram_card_pending_skip_reason(skip_reason: str | None) -> int | None:
    m = _MINIPROGRAM_CARD_ORDER_ID_MARKER_RE.match(str(skip_reason or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _is_legacy_miniprogram_card_order_pending_notification_message(message: str | None) -> bool:
    """旧版单行 mid= 文案；新版以「用户：」「会员UID：」分行展示。"""
    msg = str(message or "")
    if "用户：" in msg and "会员UID：" in msg:
        return False
    return "mid=" in msg or "已微信支付购买" in msg


def _miniprogram_card_order_pending_message(
    *,
    order_id: int,
    card_kind: str,
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
    delivery_start_date: date | None,
) -> tuple[str, str]:
    """生成小程序自助购卡待核对消息（多行，pre-line 展示）。"""
    phone = _mask_phone_middle_four(member_phone)
    naming = str(member_name or "").strip()
    naming = (naming[:24] + "…") if len(naming) > 24 else (naming or "会员")

    kind_label = str(card_kind or "").strip() or "会员卡"
    ds_text = delivery_start_date.isoformat() if delivery_start_date else "未填写"
    title = f"小程序自助购卡待核对 · 工单#{int(order_id)}"
    body_lines = [
        f"用户：{naming}",
        f"会员UID：{int(member_id)}",
        f"手机号：{phone}",
        f"卡型：{kind_label}",
        "支付方式：微信支付",
        "入账状态：餐次已入账",
        f"起送日：{ds_text}",
        "",
        "请在「开卡工单」核对配送方式与起送日，完善后用户即可参与派单。",
    ]
    body = "\n".join(body_lines)
    if len(body) > 500:
        body = body[:497] + "…"
    return title[:200], body


def try_refresh_legacy_miniprogram_card_order_pending_notification(
    db: Session,
    row: AdminSystemNotification,
) -> bool:
    """将库内旧版单行购卡待核对消息升级为最新多行格式（列表拉取时懒修复）。"""
    if row.kind != KIND_MINIPROGRAM_CARD_ORDER_PENDING:
        return False
    needs_legacy = _is_legacy_miniprogram_card_order_pending_notification_message(row.message)
    needs_mask = _system_notification_message_phone_unmasked(row.message)
    if not needs_legacy and not needs_mask:
        return False
    oid = _order_id_from_miniprogram_card_pending_skip_reason(row.skip_reason)
    if oid is None:
        return False

    from app.models.member import Member
    from app.models.member_card_order import MemberCardOrder

    order = db.get(MemberCardOrder, oid)
    if not order or int(order.store_id) != int(row.store_id):
        return False
    member = db.get(Member, int(order.member_id))
    title, body = _miniprogram_card_order_pending_message(
        order_id=oid,
        card_kind=(order.card_kind or "").strip(),
        member_id=int(order.member_id),
        member_phone=(member.phone if member else None),
        member_name=(member.name if member else None),
        delivery_start_date=order.delivery_start_date,
    )
    row.title = title
    row.message = body
    db.add(row)
    return True


def _miniprogram_card_order_pending_notification_row(
    db: Session,
    *,
    store_id: int,
    order_id: int,
) -> AdminSystemNotification | None:
    marker = _miniprogram_card_order_pending_notification_marker(order_id)
    return db.scalars(
        select(AdminSystemNotification)
        .where(
            AdminSystemNotification.store_id == int(store_id),
            AdminSystemNotification.kind == KIND_MINIPROGRAM_CARD_ORDER_PENDING,
            AdminSystemNotification.skip_reason == marker,
        )
        .order_by(AdminSystemNotification.id.desc())
        .limit(1)
    ).first()


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
    """小程序自助购卡支付成功：每工单仅 1 条待核对配送提醒，供客服核对履约信息。"""
    sid = int(store_id)
    if sid <= 0:
        return None

    existing = _miniprogram_card_order_pending_notification_row(
        db, store_id=sid, order_id=int(order_id)
    )
    if existing is not None:
        return existing

    biz = _miniprogram_card_order_pending_business_date(int(order_id))
    title, body = _miniprogram_card_order_pending_message(
        order_id=int(order_id),
        card_kind=card_kind,
        member_id=int(member_id),
        member_phone=member_phone,
        member_name=member_name,
        delivery_start_date=delivery_start_date,
    )
    marker = _miniprogram_card_order_pending_notification_marker(order_id)

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_MINIPROGRAM_CARD_ORDER_PENDING,
        business_date=biz,
        title=title,
        message=body,
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=marker,
    )
    db.add(row)
    db.flush()
    return row


def refresh_miniprogram_card_order_pending_notification(
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
    """用户完善配送信息后刷新待审批消息中的起送日（未确认前）。"""
    row = _miniprogram_card_order_pending_notification_row(
        db, store_id=int(store_id), order_id=int(order_id)
    )
    if row is None or row.acknowledged_at is not None:
        return None
    title, body = _miniprogram_card_order_pending_message(
        order_id=int(order_id),
        card_kind=card_kind,
        member_id=int(member_id),
        member_phone=member_phone,
        member_name=member_name,
        delivery_start_date=delivery_start_date,
    )
    row.title = title
    row.message = body
    db.flush()
    return row


def acknowledge_miniprogram_card_order_pending_notifications(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    admin_username: str,
) -> int:
    """开卡工单确认入账后，自动消隐对应待审批系统消息。"""
    marker = _miniprogram_card_order_pending_notification_marker(order_id)
    rows = list(
        db.scalars(
            select(AdminSystemNotification).where(
                AdminSystemNotification.store_id == int(store_id),
                AdminSystemNotification.kind == KIND_MINIPROGRAM_CARD_ORDER_PENDING,
                AdminSystemNotification.skip_reason == marker,
                AdminSystemNotification.acknowledged_at.is_(None),
            )
        ).all()
    )
    if not rows:
        return 0
    now = beijing_now_naive()
    who = str(admin_username or "").strip() or None
    for row in rows:
        row.acknowledged_at = now
        row.acknowledged_by = who
    db.flush()
    return len(rows)


_SINGLE_MEAL_SUPPLY_DAY_RE = re.compile(r"供餐日[：:\s]*(\d{4}-\d{2}-\d{2})")
_SINGLE_MEAL_ORDER_ID_MARKER_RE = re.compile(r"^single_meal_order_id:(\d+)$")


def supply_day_from_single_meal_notification_message(message: str | None) -> str:
    """从单次零售系统消息正文解析真实供餐日（business_date 列为 uk 槽位，非供餐日）。"""
    m = _SINGLE_MEAL_SUPPLY_DAY_RE.search(str(message or ""))
    return m.group(1) if m else ""


def _single_meal_order_paid_notification_marker(order_id: int) -> str:
    """skip_reason 存订单 id，回调重试时幂等去重。"""
    return f"single_meal_order_id:{int(order_id)}"


def _single_meal_order_paid_business_date_for_uk(order_id: int) -> date:
    """
    每订单独占 ``(store_id, kind, business_date)`` 唯一键。

    ``business_date`` 列仅为 DATE，无法存毫秒时间戳；与开卡待审批同策略用 order_id 映射槽位，
    真实供餐日写在 message 多行正文中。
    """
    return date(2000, 1, 1) + timedelta(days=int(order_id))


def _format_single_meal_order_paid_time_zh(dt: datetime) -> str:
    """支付入账时刻（库内北京时间 naive）→「2026年6月4日17点8分35秒」。"""
    return f"{int(dt.year)}年{int(dt.month)}月{int(dt.day)}日{int(dt.hour)}点{int(dt.minute)}分{int(dt.second)}秒"


def _order_id_from_single_meal_paid_skip_reason(skip_reason: str | None) -> int | None:
    m = _SINGLE_MEAL_ORDER_ID_MARKER_RE.match(str(skip_reason or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _is_legacy_single_meal_paid_notification_message(message: str | None) -> bool:
    """旧版单行 mid=/trace= 文案；新版以「用户：」分行展示。"""
    msg = str(message or "")
    if "用户：" in msg:
        return False
    return "mid=" in msg or "trace=" in msg or "已支付" in msg


def _build_single_meal_order_paid_notification_text(
    *,
    order_id: int,
    delivery_date: date,
    dish_name: str | None,
    quantity: int,
    store_pickup: bool,
    member_phone: str | None,
    member_name: str | None,
    order_created_at: datetime | None,
    out_trade_no: str | None,
    pay_channel: str | None,
) -> tuple[str, str]:
    """生成单次零售系统消息标题与正文（多行，pre-line 展示）。"""
    oid = int(order_id)
    phone = _mask_phone_middle_four(member_phone)
    naming = str(member_name or "").strip()
    naming = (naming[:24] + "…") if len(naming) > 24 else (naming or "会员")

    dish = str(dish_name or "").strip() or "单次点餐"
    qty = max(1, int(quantity))
    fulfill = "门店自提" if bool(store_pickup) else "配送到家"
    paid_at = order_created_at if isinstance(order_created_at, datetime) else beijing_now_naive()
    time_text = _format_single_meal_order_paid_time_zh(paid_at)
    supply_day = delivery_date.isoformat()
    order_no = (str(out_trade_no or "").strip()) or str(oid)

    pay_tag = (str(pay_channel or "").strip())
    pay_note = "（会员卡支付）" if pay_tag == "会员卡" else ""

    title = f"单次零售新订单 · #{oid}"
    dish_line = f"{dish}×{qty}{pay_note}"
    body_lines = [
        f"用户：{naming}",
        f"手机号：{phone}",
        f"下单时间：{time_text}",
        f"餐品：{dish_line}",
        f"供餐日：{supply_day}（{fulfill}）",
        f"配送方式：{fulfill}",
        f"订单号：{order_no}",
        "",
        "请尽快在「订单管理」推送配送或安排自提。",
    ]
    body = "\n".join(body_lines)
    if len(body) > 500:
        body = body[:497] + "…"
    return title[:200], body


def try_refresh_legacy_single_meal_order_paid_notification(
    db: Session,
    row: AdminSystemNotification,
) -> bool:
    """将库内旧版单行消息升级为最新多行格式（列表拉取时懒修复）。"""
    if row.kind != KIND_SINGLE_MEAL_ORDER_PAID:
        return False
    needs_legacy = _is_legacy_single_meal_paid_notification_message(row.message)
    needs_mask = _system_notification_message_phone_unmasked(row.message)
    if not needs_legacy and not needs_mask:
        return False
    oid = _order_id_from_single_meal_paid_skip_reason(row.skip_reason)
    if oid is None:
        return False

    from app.models.member import Member
    from app.models.menu_dish import MenuDish
    from app.models.single_meal_order import SingleMealOrder

    order = db.get(SingleMealOrder, oid)
    if not order or int(order.store_id) != int(row.store_id):
        return False
    member = db.get(Member, int(order.member_id))
    dish = db.get(MenuDish, int(order.dish_id)) if order.dish_id else None
    title, body = _build_single_meal_order_paid_notification_text(
        order_id=oid,
        delivery_date=order.delivery_date,
        dish_name=(dish.name if dish else None),
        quantity=int(order.quantity or 1),
        store_pickup=bool(getattr(order, "store_pickup", False)),
        member_phone=(member.phone if member else None),
        member_name=(member.name if member else None),
        order_created_at=order.created_at,
        out_trade_no=str(order.out_trade_no or ""),
        pay_channel=str(order.pay_channel or ""),
    )
    row.title = title
    row.message = body
    db.add(row)
    return True


def _single_meal_order_paid_notification_row(
    db: Session,
    *,
    store_id: int,
    order_id: int,
) -> AdminSystemNotification | None:
    marker = _single_meal_order_paid_notification_marker(order_id)
    return db.scalars(
        select(AdminSystemNotification)
        .where(
            AdminSystemNotification.store_id == int(store_id),
            AdminSystemNotification.kind == KIND_SINGLE_MEAL_ORDER_PAID,
            AdminSystemNotification.skip_reason == marker,
        )
        .order_by(AdminSystemNotification.id.desc())
        .limit(1)
    ).first()


def create_single_meal_order_paid_notification(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    delivery_date: date,
    dish_name: str | None,
    quantity: int,
    amount_yuan: str | None,
    store_pickup: bool,
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
    order_created_at: datetime | None = None,
    out_trade_no: str | None = None,
    pay_channel: str | None = None,
) -> AdminSystemNotification | None:
    """单次零售支付成功：每订单一条客服提醒（幂等；不占用供餐日 uk 槽位）。"""
    _ = amount_yuan, member_id
    sid = int(store_id)
    if sid <= 0:
        return None

    oid = int(order_id)
    title, body = _build_single_meal_order_paid_notification_text(
        order_id=oid,
        delivery_date=delivery_date,
        dish_name=dish_name,
        quantity=quantity,
        store_pickup=store_pickup,
        member_phone=member_phone,
        member_name=member_name,
        order_created_at=order_created_at,
        out_trade_no=out_trade_no,
        pay_channel=pay_channel,
    )
    existing = _single_meal_order_paid_notification_row(db, store_id=sid, order_id=oid)
    if existing is not None:
        if existing.title != title or existing.message != body:
            existing.title = title
            existing.message = body
            db.add(existing)
            db.flush()
        return existing

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_SINGLE_MEAL_ORDER_PAID,
        business_date=_single_meal_order_paid_business_date_for_uk(oid),
        title=title,
        message=body,
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=_single_meal_order_paid_notification_marker(oid),
    )
    db.add(row)
    db.flush()
    return row


def _store_retail_order_paid_notification_marker(order_id: int) -> str:
    return f"store_retail_order_id:{int(order_id)}"


def _store_retail_order_paid_business_date_for_uk(order_id: int) -> date:
    return date(2010, 1, 1) + timedelta(days=int(order_id))


def _build_store_retail_order_paid_notification_text(
    *,
    order_id: int,
    product_title: str | None,
    quantity: int,
    store_pickup: bool,
    member_phone: str | None,
    member_name: str | None,
    order_created_at: datetime | None,
    out_trade_no: str | None,
    pay_channel: str | None,
) -> tuple[str, str]:
    phone = _mask_phone_middle_four(member_phone)
    naming = str(member_name or "").strip() or "会员"
    naming = (naming[:24] + "…") if len(naming) > 24 else naming
    prod = str(product_title or "").strip() or "商品"
    fulfill = "门店自提" if store_pickup else "配送到家"
    time_text = (
        _format_single_meal_order_paid_time_zh(order_created_at)
        if order_created_at is not None
        else "—"
    )
    order_no = str(out_trade_no or "").strip() or f"#{int(order_id)}"
    pay_note = f"（{pay_channel}）" if (pay_channel or "").strip() else ""
    title = f"商城订单支付成功 · 订单#{int(order_id)}"
    body_lines = [
        f"用户：{naming}",
        f"手机号：{phone}",
        f"下单时间：{time_text}",
        f"商品：{prod}×{int(quantity)}{pay_note}",
        f"配送方式：{fulfill}",
        f"订单号：{order_no}",
        "",
        "请尽快在「订单管理」商城订单 Tab 推送配送或安排自提。",
    ]
    body = "\n".join(body_lines)
    if len(body) > 500:
        body = body[:497] + "…"
    return title[:200], body


def create_store_retail_order_paid_notification(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    product_title: str | None,
    quantity: int,
    amount_yuan: str | None,
    store_pickup: bool,
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
    order_created_at: datetime | None = None,
    out_trade_no: str | None = None,
    pay_channel: str | None = None,
) -> AdminSystemNotification | None:
    _ = amount_yuan, member_id
    sid = int(store_id)
    if sid <= 0:
        return None
    oid = int(order_id)
    title, body = _build_store_retail_order_paid_notification_text(
        order_id=oid,
        product_title=product_title,
        quantity=quantity,
        store_pickup=store_pickup,
        member_phone=member_phone,
        member_name=member_name,
        order_created_at=order_created_at,
        out_trade_no=out_trade_no,
        pay_channel=pay_channel,
    )
    marker = _store_retail_order_paid_notification_marker(oid)
    existing = db.scalars(
        select(AdminSystemNotification)
        .where(
            AdminSystemNotification.store_id == sid,
            AdminSystemNotification.kind == KIND_STORE_RETAIL_ORDER_PAID,
            AdminSystemNotification.skip_reason == marker,
        )
        .order_by(AdminSystemNotification.id.desc())
        .limit(1)
    ).first()
    if existing is not None:
        if existing.title != title or existing.message != body:
            existing.title = title
            existing.message = body
            db.add(existing)
            db.flush()
        return existing
    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_STORE_RETAIL_ORDER_PAID,
        business_date=_store_retail_order_paid_business_date_for_uk(oid),
        title=title,
        message=body,
        total_count=0,
        success_count=0,
        failed_count=0,
        skip_reason=marker,
    )
    db.add(row)
    db.flush()
    return row


def _member_insufficient_balance_notification_exists(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    member_id: int,
) -> bool:
    """同日同店同会员是否已有余量不足配送提醒（含已确认），避免轮询重复写入。"""
    marker = f"mid={int(member_id)} "
    row_id = db.scalar(
        select(AdminSystemNotification.id).where(
            AdminSystemNotification.store_id == int(store_id),
            AdminSystemNotification.kind == KIND_MEMBER_INSUFFICIENT_BALANCE_FOR_DELIVERY,
            AdminSystemNotification.business_date == business_date,
            AdminSystemNotification.message.like(f"%{marker}%"),
        ).limit(1)
    )
    return row_id is not None


def create_member_insufficient_balance_for_delivery_notification(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    member_id: int,
    member_phone: str | None,
    member_name: str | None,
    balance: int,
    daily_meal_units: int,
) -> AdminSystemNotification | None:
    """每日多份但剩余次数不足：提醒客服联系用户确认是否续卡。"""
    sid = int(store_id)
    if sid <= 0:
        return None
    if _member_insufficient_balance_notification_exists(
        db, store_id=sid, business_date=business_date, member_id=int(member_id)
    ):
        return None

    phones = str(member_phone or "").strip()[:32] or "(无手机号)"
    naming = str(member_name or "").strip()
    naming = naming[:40] + ("…" if len(naming) > 40 else "")

    units = max(1, int(daily_meal_units))
    bal = max(0, int(balance))
    title = f"续费跟进·余量不足配送 · {business_date.isoformat()}"
    body = (
        f"会员 mid={int(member_id)} {phones} "
        f"{('「' + naming + '」') if naming else ''}"
        f"供餐日 {business_date.isoformat()} 应配送 {units} 份/日，剩余次数仅 {bal} 次，"
        "已无法计入配送大表。请联系用户确认是否续卡。"
    )
    if len(body) > 500:
        body = body[:497] + "…"

    row = AdminSystemNotification(
        store_id=sid,
        kind=KIND_MEMBER_INSUFFICIENT_BALANCE_FOR_DELIVERY,
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


def scan_insufficient_balance_delivery_notifications_for_all_stores(
    db: Session,
    *,
    business_date: date | None = None,
) -> int:
    """
    扫描全部门店：指定供餐日应履约但 ``balance < daily_meal_units``（且每日 >1 份）的会员，写入客服系统消息。
    返回本次新写入条数。

    头天晚间任务应传入 ``business_date=明日供餐日``，以便客服提前联系用户。
    """
    from app.models.store import Store
    from app.services.courier_service import list_members_insufficient_balance_for_delivery_day
    from app.services.member_service import effective_daily_meal_units

    biz = business_date or today_shanghai()
    if not is_subscription_delivery_day(biz):
        return 0

    store_ids = list(
        db.scalars(select(Store.id).where(Store.is_active.is_(True)).order_by(Store.id.asc())).all()
    )
    created = 0
    for sid in store_ids:
        sid_int = int(sid)
        members = list_members_insufficient_balance_for_delivery_day(
            db, delivery_date=biz, store_id=sid_int
        )
        for m in members:
            row = create_member_insufficient_balance_for_delivery_notification(
                db,
                store_id=sid_int,
                business_date=biz,
                member_id=int(m.id),
                member_phone=m.phone,
                member_name=m.name,
                balance=int(m.balance or 0),
                daily_meal_units=effective_daily_meal_units(m),
            )
            if row is not None:
                created += 1
    return created


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
    同店同日 ``delivery_sheet_manual_attention`` 仅一条（库表唯一键），重复事件合并进 message。

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
    rows = list(db.scalars(stmt).all())
    changed = False
    for row in rows:
        if try_refresh_legacy_single_meal_order_paid_notification(db, row):
            changed = True
        elif try_refresh_legacy_miniprogram_card_order_pending_notification(db, row):
            changed = True
    if changed:
        db.commit()
    return rows


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
    delivery_date = ""
    if row.kind == KIND_SINGLE_MEAL_ORDER_PAID:
        delivery_date = supply_day_from_single_meal_notification_message(row.message)
    return {
        "id": int(row.id),
        "store_id": int(row.store_id),
        "kind": row.kind,
        "business_date": row.business_date.isoformat() if row.business_date else "",
        "delivery_date": delivery_date,
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
