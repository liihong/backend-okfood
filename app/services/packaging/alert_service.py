"""包装库存系统消息。

同一门店、同一天只留一条。确认状态不在这里清除，避免晚上重跑把客服已经点过的消息又弹出来。
正文最长 2000 字，装不下的品名改到库存结存页看完整名单。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.admin_system_notification import AdminSystemNotification
from app.models.packaging_consume_run import PackagingConsumeRun
from app.services.packaging.constants import ALERT_MESSAGE_LIMIT, KIND_PACKAGING_LOW_STOCK, MEAL_LABELS
from app.services.packaging.stock_command_service import list_stocks


def sync_day_alert(db: Session, *, store_id: int, biz_date: date) -> None:
    """按当天两餐的扣库备注和当前结存，刷新这一天的一条消息。"""
    warnings = _warnings_from_runs(db, store_id=store_id, biz_date=biz_date)
    lows = [row for row in list_stocks(db, store_id=store_id) if row["low"] and row["is_active"]]
    row = db.scalar(
        select(AdminSystemNotification).where(
            AdminSystemNotification.store_id == int(store_id),
            AdminSystemNotification.kind == KIND_PACKAGING_LOW_STOCK,
            AdminSystemNotification.business_date == biz_date,
        )
    )
    if not warnings and not lows:
        if row is not None and row.acknowledged_at is None:
            row.title = f"包装耗材 · {biz_date.isoformat()}"
            row.message = "包装耗材已回到最低库存以上。"
            row.total_count = 0
            row.failed_count = 0
        return
    title = f"包装耗材该采购 · {biz_date.isoformat()}" if lows else f"包装扣库待处理 · {biz_date.isoformat()}"
    message = build_alert_message(warnings, lows)
    if row is None:
        row = AdminSystemNotification(
            store_id=int(store_id),
            kind=KIND_PACKAGING_LOW_STOCK,
            business_date=biz_date,
            title=title,
            message=message,
            total_count=len(lows),
            success_count=0,
            failed_count=len(warnings),
            skip_reason=None,
        )
        db.add(row)
    else:
        row.title = title
        row.message = message
        row.total_count = len(lows)
        row.failed_count = len(warnings)
        row.skip_reason = None
    db.commit()


def build_alert_message(warnings: list[str], lows: list[dict]) -> str:
    """拼通知正文。超长时保留原因，品名列表截断。"""
    parts: list[str] = []
    for warning in warnings:
        text = (warning or "").strip()
        if text:
            parts.append(text)
    if lows:
        parts.append("低于最低库存：")
        shown = 0
        for row in lows:
            line = _low_line(row)
            trial = "\n".join(parts + [line])
            if len(trial) > ALERT_MESSAGE_LIMIT - 40:
                rest = len(lows) - shown
                parts.append(f"另有 {rest} 项，请打开库存结存查看。")
                break
            parts.append(line)
            shown += 1
    message = "\n".join(parts).strip() or "包装耗材库存需要处理。"
    if len(message) > ALERT_MESSAGE_LIMIT:
        message = message[: ALERT_MESSAGE_LIMIT - 1] + "…"
    return message


def _low_line(row: dict) -> str:
    safety = "未设置" if row.get("safety_stock") is None else str(row["safety_stock"])
    supplier = row.get("supplier_name") or "未填供应商"
    bag = "（每餐打包袋）" if row.get("is_meal_bag") else ""
    return f"{row['name']}{bag} 结存 {row['qty']}{row.get('unit') or ''}，最低 {safety}，供应商 {supplier}"


def _warnings_from_runs(db: Session, *, store_id: int, biz_date: date) -> list[str]:
    runs = db.scalars(
        select(PackagingConsumeRun)
        .where(
            PackagingConsumeRun.store_id == int(store_id),
            PackagingConsumeRun.biz_date == biz_date,
        )
        .order_by(PackagingConsumeRun.meal_period.asc())
    ).all()
    warnings: list[str] = []
    for run in runs:
        note = (run.note or "").strip()
        if not note:
            continue
        label = MEAL_LABELS.get(run.meal_period, run.meal_period)
        for line in note.split("\n"):
            text = line.strip()
            if text and text not in warnings:
                if not text.startswith(label):
                    text = f"{label}{text}"
                warnings.append(text)
    return warnings
