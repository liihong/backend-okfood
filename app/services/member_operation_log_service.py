"""会员自助操作审计日志服务：暂停/恢复配送、修改配送份数、修改地址等关键操作留痕。

本模块只负责把操作记录写入 `member_operation_logs`，不做业务校验；
调用方在业务处理前后采集 before/after 字典后交由 ``record_member_operation`` 落库。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.member_operation_log import MemberOperationLog

# 操作类型枚举（与 models/member_operation_log.operation_type 对应）
OP_PAUSE_DELIVERY = "pause_delivery"             # 暂停配送
OP_RESUME_DELIVERY = "resume_delivery"           # 恢复配送（设置起送日或切换到配送/自提）
OP_UPDATE_DAILY_UNITS = "update_daily_meal_units"  # 修改每日配送份数
OP_UPDATE_STORE_PICKUP = "update_store_pickup"   # 门店自提切换
OP_UPDATE_DELIVERY_START = "update_delivery_start_date"  # 仅修改起送日
OP_ADDRESS_CREATE = "address_create"
OP_ADDRESS_UPDATE = "address_update"
OP_ADDRESS_DELETE = "address_delete"
OP_ADDRESS_SET_DEFAULT = "address_set_default"
OP_LEAVE_TOMORROW = "leave_tomorrow"           # 明天请假
OP_LEAVE_RANGE = "leave_range"                  # 区间请假
OP_LEAVE_CLEAR_TOMORROW = "leave_clear_tomorrow"  # 仅取消明天请假
OP_LEAVE_CANCEL = "leave_cancel"                # 取消全部请假标记

_OPERATION_LABELS: dict[str, str] = {
    OP_PAUSE_DELIVERY: "暂停配送",
    OP_RESUME_DELIVERY: "恢复配送",
    OP_UPDATE_DAILY_UNITS: "修改每日送达份数",
    OP_UPDATE_STORE_PICKUP: "切换自提/配送",
    OP_UPDATE_DELIVERY_START: "修改起送日",
    OP_ADDRESS_CREATE: "新增配送地址",
    OP_ADDRESS_UPDATE: "修改配送地址",
    OP_ADDRESS_DELETE: "删除配送地址",
    OP_ADDRESS_SET_DEFAULT: "设为默认配送地址",
    OP_LEAVE_TOMORROW: "明天请假",
    OP_LEAVE_RANGE: "区间请假",
    OP_LEAVE_CLEAR_TOMORROW: "取消明天请假",
    OP_LEAVE_CANCEL: "取消请假",
}


def operation_label(op: str) -> str:
    return _OPERATION_LABELS.get(op, op)


def _dump_json(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)[:4000]
    except (TypeError, ValueError):
        return None


def record_member_operation(
    db: Session,
    *,
    member_id: int,
    operation_type: str,
    summary: str,
    before: Any = None,
    after: Any = None,
    ip_address: str | None = None,
    operator: str | None = None,
    source: str = "miniprogram",
) -> None:
    """追加一条操作日志；不 commit（由上层事务一并提交）。"""

    row = MemberOperationLog(
        member_id=int(member_id),
        source=(source or "miniprogram")[:20],
        operation_type=(operation_type or "")[:50],
        summary=(summary or "")[:200],
        before_json=_dump_json(before),
        after_json=_dump_json(after),
        ip_address=(ip_address or None) and str(ip_address)[:64],
        operator=(operator or f"member:{member_id}")[:100],
    )
    db.add(row)


def list_member_operations(
    db: Session,
    *,
    member_id: int,
    page: int = 1,
    page_size: int = 20,
    operation_type: str | None = None,
) -> tuple[list[MemberOperationLog], int]:
    """按会员倒序分页查询操作日志。"""

    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 20)))

    stmt = select(MemberOperationLog).where(MemberOperationLog.member_id == int(member_id))
    if operation_type:
        stmt = stmt.where(MemberOperationLog.operation_type == operation_type)

    from sqlalchemy import func

    total = int(
        db.scalar(
            select(func.count()).select_from(MemberOperationLog).where(
                MemberOperationLog.member_id == int(member_id)
            ).where(
                *( [MemberOperationLog.operation_type == operation_type] if operation_type else [] )
            )
        )
        or 0
    )

    items = list(
        db.scalars(
            stmt.order_by(desc(MemberOperationLog.id)).limit(page_size).offset((page - 1) * page_size)
        ).all()
    )
    return items, total


def operation_log_to_dict(row: MemberOperationLog) -> dict[str, Any]:
    """转为管理端展示用字典。"""

    def _loads(s: str | None) -> Any:
        if not s:
            return None
        try:
            return json.loads(s)
        except (TypeError, ValueError):
            return s

    return {
        "id": int(row.id),
        "member_id": int(row.member_id),
        "source": row.source,
        "operation_type": row.operation_type,
        "operation_label": operation_label(row.operation_type),
        "summary": row.summary,
        "before": _loads(row.before_json),
        "after": _loads(row.after_json),
        "ip_address": row.ip_address,
        "operator": row.operator,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
