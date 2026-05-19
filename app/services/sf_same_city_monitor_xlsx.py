"""顺丰订单监控页：创单落地记录导出为 Excel（与列表筛选同源）。"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

_SF_ORDER_STATUS_ZH: dict[int, str] = {
    1: "订单创建",
    2: "订单取消",
    10: "配送员接单/配送员改派",
    12: "配送员到店",
    15: "配送员配送中（已取货）",
    17: "配送员妥投完单",
    22: "配送员撤单",
    31: "取消中",
    91: "骑士上报异常",
}

_SF_CALLBACK_KIND_ZH: dict[str, str] = {
    "delivery_status": "配送状态变更",
    "order_complete": "订单完成",
    "cancel_by_sf": "顺丰取消",
    "merchant_cancel": "商家取消配送",
    "delivery_exception": "配送异常",
    "rider_cancel": "骑士取消",
    "auto_shop": "自动店铺",
    "oauth_callback": "OAuth 授权",
    "oauth_revoke": "OAuth 撤销",
}


def _fmt_wall_datetime(raw: str | None) -> str:
    if not raw:
        return "—"
    s = str(raw).strip()
    if not s:
        return "—"
    return s.replace("T", " ")[:19]


def _sf_create_status_zh(code: Any) -> str:
    if code == 0 or code == "0":
        return "创单成功"
    if code is None:
        return "—"
    return f"失败 ({code})"


def _sf_order_status_label(code: Any) -> str:
    if code is None or code == "":
        return "—"
    try:
        n = int(code)
    except (TypeError, ValueError):
        return str(code)
    zh = _SF_ORDER_STATUS_ZH.get(n)
    if zh:
        return f"{zh}（{n}）"
    return f"未识别（{n}）"


def _sf_callback_kind_label(kind: Any) -> str:
    k = str(kind or "").strip()
    if not k:
        return "—"
    zh = _SF_CALLBACK_KIND_ZH.get(k)
    return f"{zh}（{k}）" if zh else k


def _member_join(row: dict[str, Any], field: str) -> str:
    members = row.get("members")
    if not isinstance(members, list) or not members:
        return "—"
    parts: list[str] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        v = str(m.get(field) or "").strip()
        parts.append(v or "—")
    return "；".join(parts) if parts else "—"


def build_sf_push_monitor_xlsx(rows: list[dict[str, Any]]) -> bytes:
    """将 ``list_sf_same_city_pushes_for_monitor_export`` 返回的行写成 xlsx。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "顺丰订单监控"

    headers = (
        "系统ID",
        "业务日",
        "停靠点",
        "商家订单号",
        "顺丰单号",
        "运单号",
        "会员姓名",
        "会员手机",
        "创单状态",
        "回调订单状态",
        "回调状态码",
        "最近回调类型",
        "最近回调时间",
        "创单时间",
        "创单错误码",
        "创单错误信息",
    )
    ws.append(list(headers))

    for r in rows:
        if not isinstance(r, dict):
            continue
        err_code = r.get("error_code")
        cb_code = r.get("sf_callback_order_status")
        create_zh = (r.get("sf_create_status_label") or "").strip() or _sf_create_status_zh(err_code)
        ws.append(
            [
                r.get("id"),
                r.get("delivery_date") or "",
                r.get("stop_id") or "",
                r.get("shop_order_id") or "",
                r.get("sf_order_id") or "",
                r.get("sf_bill_id") or "",
                _member_join(r, "name"),
                _member_join(r, "phone"),
                create_zh,
                _sf_order_status_label(cb_code),
                cb_code if cb_code is not None else "",
                _sf_callback_kind_label(r.get("last_callback_kind")),
                _fmt_wall_datetime(r.get("last_callback_at")),
                _fmt_wall_datetime(r.get("created_at")),
                err_code if err_code is not None else "",
                (r.get("error_msg") or "")[:1024],
            ]
        )

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
