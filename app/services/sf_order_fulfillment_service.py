"""顺丰同城「订单完成」回调触发：与同停靠点的智能配送大表标记送达对齐（到家扣次）；单点餐仅标履约。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, and_, case, cast, func, or_, select, text, true as sql_true
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.delivery_log import DeliveryLog
from app.models.enums import DeliveryStatus
from app.models.member import Member
from app.models.single_meal_order import SingleMealOrder
from app.models.sf_same_city_push import SfSameCityPush
from app.services.admin_delivery_fulfillment_service import subscription_fulfilled_try_sf_home_no_commit
from app.services.sf_same_city_service import aggs_for_delivery_date, load_agg_for_stop_id
from app.services.single_meal_order_service import (
    mark_single_meal_delivered_sf_completion_no_commit,
    mark_single_meal_sf_cancelled_no_commit,
    sf_push_create_succeeded,
    sf_push_is_terminal_cancel,
)

logger = logging.getLogger(__name__)

# 顺丰开放平台配送推送 order_status：17=配送员妥投完单（与后台监控文案一致）
SF_ORDER_STATUS_DELIVERED_TUOTOU = 17
# 2=订单取消、22=配送员撤单（与监控「取消订单」口径一致）
SF_ORDER_STATUS_CANCELLED = (2, 22)

SF_PUSH_KIND_DELIVERY_SHEET = "delivery_sheet"
SF_PUSH_KIND_SINGLE_MEAL_RETAIL = "single_meal_retail"


@dataclass(frozen=True)
class SfCallbackSideEffectJob:
    """顺丰回调落库后异步执行的扣次/取消同步任务（独立 DB Session）。"""

    push_id: int
    route_kind: str
    operator_tag: str
    action: str  # fulfillment | cancel_sync


def _flush_renew_reminds(db: Session, pending: list[tuple[Member, int]]) -> None:
    """扣次 commit 后再调微信，避免事务内 HTTP 占连接与行锁。"""
    if not pending:
        return
    from app.services.member_renew_subscribe_service import try_send_renew_remind_after_balance_change

    dirty = False
    for member, balance_before in pending:
        try:
            try_send_renew_remind_after_balance_change(db, member, balance_before=balance_before)
            dirty = True
        except Exception:
            logger.exception("续费提醒下发失败 member_id=%s", getattr(member, "id", None))
    if dirty and (db.new or db.dirty or db.deleted):
        db.commit()


def _sf_fulfillment_try_lock(db: Session, push_id: int) -> bool:
    bind = db.get_bind()
    if getattr(bind.dialect, "name", "") != "mysql":
        return True
    key = f"okf_sfff_{int(push_id)}"[:64]
    rc = db.execute(text("SELECT GET_LOCK(:k, 5)"), {"k": key}).scalar()
    return rc == 1


def _sf_fulfillment_release_lock(db: Session, push_id: int) -> None:
    bind = db.get_bind()
    if getattr(bind.dialect, "name", "") != "mysql":
        return
    key = f"okf_sfff_{int(push_id)}"[:64]
    db.execute(text("SELECT RELEASE_LOCK(:k)"), {"k": key})


def sf_push_fulfilled_quick_check(
    db: Session,
    pus: SfSameCityPush,
    *,
    ags_hint: dict | None = None,
) -> bool:
    """
    轻量判断推单是否已履约完毕：优先读推单快照，避免重复回调重建整张大表。
    返回 True 表示无需再跑扣次/标履约。
    """
    if not sf_push_create_succeeded(pus):
        return True
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return True

    kind = (getattr(pus, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        oid = oid_retail
        if oid is None:
            return False
        o = db.get(SingleMealOrder, oid)
        return o is not None and str(getattr(o, "fulfillment_status", "") or "").strip().lower() == "delivered"

    snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    if snap_mids or snap_oids:
        for mid in snap_mids:
            if not member_subscription_delivered_on_delivery_date(
                db, member_id=int(mid), delivery_date=pus.delivery_date
            ):
                return False
        for oid in snap_oids:
            o = db.get(SingleMealOrder, oid)
            if o is None or str(getattr(o, "fulfillment_status", "") or "").strip().lower() != "delivered":
                return False
        return True

    return sf_same_city_push_fully_fulfilled(db, pus, ags_hint=ags_hint)


def _retail_smo_order_id_from_stop(stop_id: str | None) -> int | None:
    """零售单次推单 stop_id 形如 retail-smo-{single_meal_orders.id}。"""
    s = (stop_id or "").strip()
    prefix = "retail-smo-"
    if not s.startswith(prefix):
        return None
    tail = s[len(prefix) :].strip()
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


def _single_meal_order_bound_to_push(db: Session, order_id: int, pus: SfSameCityPush) -> bool:
    """订单已绑定 push 时，回调/同步须 push.id 一致（防同址多单串单）。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None:
        return False
    if o.sf_same_city_push_id is None:
        return True
    if pus.id is None:
        return False
    return int(o.sf_same_city_push_id) == int(pus.id)


def _push_kind_label(kind: str | None) -> str:
    k = (kind or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    if k == SF_PUSH_KIND_SINGLE_MEAL_RETAIL:
        return "单次零售"
    return "大表合并"


def _members_from_retail_single_meal_order(db: Session, order_id: int) -> list[dict[str, Any]]:
    row = db.get(SingleMealOrder, int(order_id))
    if not row:
        return []
    m = db.get(Member, int(row.member_id)) if row.member_id else None
    return [
        {
            "member_id": int(row.member_id) if row.member_id is not None else None,
            "name": ((m.name or "").strip() if m else "") or "—",
            "phone": ((m.phone or "").strip() if m else "") or "—",
            "kind": "single_meal",
        }
    ]


def _sf_push_monitor_cancelled_clause():
    """商户已发起取消（本地标记）或顺丰回调已为取消/撤单终态；与监控页「取消订单」口径一致。"""
    return or_(
        SfSameCityPush.merchant_cancel_requested_at.isnot(None),
        SfSameCityPush.sf_callback_order_status.in_((2, 22)),
    )


def sf_monitor_create_status_label(
    *,
    error_code: int | None,
    sf_callback_order_status: int | None,
    merchant_cancel_requested_at: Any,
) -> str:
    """
    监控列表 / 导出「创单状态」列：顺丰确认取消优先于本地取消标记，其次创单 error_code。
    """
    cb = int(sf_callback_order_status) if sf_callback_order_status is not None else None
    if cb is not None and cb in (2, 22):
        return "取消订单"
    if merchant_cancel_requested_at is not None:
        return "取消订单"
    if error_code == 0:
        return "创单成功"
    if error_code is None:
        return "—"
    return f"失败 ({error_code})"


def _sf_push_monitor_where_clauses(
    *,
    delivery_date: date | None,
    store_id: int | None,
    sf_callback_order_status: int | None,
    callback_order_status_unknown: bool,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> list[Any]:
    """
    顺丰监控列表 / 导出共用 WHERE 条件。
    会员手机：在 request_snapshot JSON 文本中 LIKE（停靠点快照含 recv_phone 等）。
    顺丰单号：sf_order_id 模糊匹配。
    创单状态：ok=创单成功且未取消；fail=创单非成功；cancelled=取消订单（本地取消标记或回调 2/22）。
    """
    clauses: list[Any] = []
    if delivery_date is not None:
        clauses.append(SfSameCityPush.delivery_date == delivery_date)
    if store_id is not None:
        clauses.append(SfSameCityPush.store_id == int(store_id))
    if callback_order_status_unknown:
        clauses.append(SfSameCityPush.sf_callback_order_status.is_(None))
    elif sf_callback_order_status is not None:
        clauses.append(SfSameCityPush.sf_callback_order_status == int(sf_callback_order_status))

    st = (sf_create_status or "").strip().lower()
    if st in ("ok", "success"):
        clauses.append(SfSameCityPush.error_code == 0)
        clauses.append(~_sf_push_monitor_cancelled_clause())
    elif st in ("fail", "failed"):
        clauses.append(or_(SfSameCityPush.error_code.is_(None), SfSameCityPush.error_code != 0))
    elif st in ("cancelled", "canceled"):
        clauses.append(_sf_push_monitor_cancelled_clause())

    oid = (sf_order_id_contains or "").strip()
    if oid:
        clauses.append(SfSameCityPush.sf_order_id.isnot(None))
        clauses.append(SfSameCityPush.sf_order_id.like(f"%{oid}%"))

    ph = (member_phone_contains or "").strip()
    if ph:
        clauses.append(SfSameCityPush.request_snapshot.isnot(None))
        clauses.append(cast(SfSameCityPush.request_snapshot, String).like(f"%{ph}%"))

    pk = (push_kind or "").strip()
    if pk:
        clauses.append(SfSameCityPush.push_kind == pk)

    return clauses


def _iso_dt(x: Any) -> str | None:
    if x is None:
        return None
    if hasattr(x, "isoformat"):
        return x.isoformat()
    return str(x)


def _fallback_members_from_snapshot(snap: Any) -> list[dict[str, Any]]:
    """创单快照中的收件人姓名/电话（停靠点无法再解析时的回退）。"""
    if not isinstance(snap, dict):
        return []
    pr = snap.get("preview_row")
    if not isinstance(pr, dict):
        return []
    rname = (pr.get("recv_name") or "").strip()
    rphone = (pr.get("recv_phone") or "").strip()
    if rphone in ("—",):
        rphone = ""
    if not rname and not rphone:
        return []
    return [
        {
            "member_id": None,
            "name": rname or "—",
            "phone": rphone or "—",
            "kind": "snapshot",
        }
    ]


def _member_rows_from_agg(db: Session, agg: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for x in getattr(agg, "sub_lines", None) or []:
        mid = x.get("member_id")
        if mid is None:
            continue
        try:
            im = int(mid)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "member_id": im,
                "name": (x.get("name") or "").strip() or "—",
                "phone": (x.get("phone") or "").strip() or "—",
                "kind": "subscription",
            }
        )
    singles = getattr(agg, "singles", None) or []
    if singles:
        ids = []
        for sng in singles:
            try:
                ids.append(int(sng["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        oid_mid: dict[int, int] = {}
        if ids:
            rows = db.execute(
                select(SingleMealOrder.id, SingleMealOrder.member_id).where(SingleMealOrder.id.in_(ids))
            ).all()
            for oid, mid in rows:
                if mid is not None:
                    oid_mid[int(oid)] = int(mid)
        for sng in singles:
            try:
                oid = int(sng["id"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append(
                {
                    "member_id": oid_mid.get(oid),
                    "name": (sng.get("member_name") or "").strip() or "—",
                    "phone": (sng.get("member_phone") or "").strip() or "—",
                    "kind": "single_meal",
                }
            )
    return out


def _sf_push_monitor_row_dict(
    db: Session,
    r: SfSameCityPush,
    aggs: dict[str, Any],
) -> dict[str, Any]:
    agg = aggs.get(str(r.stop_id)) if aggs else None
    kind_raw = (getattr(r, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(r.stop_id or ""))

    members = _member_rows_from_agg(db, agg) if agg is not None else []
    if not members:
        members = _fallback_members_from_snapshot(r.request_snapshot)
    if oid_retail is not None and kind_raw == SF_PUSH_KIND_SINGLE_MEAL_RETAIL:
        alt = _members_from_retail_single_meal_order(db, oid_retail)
        if alt:
            members = alt

    return {
        "id": int(r.id),
        "store_id": int(r.store_id) if getattr(r, "store_id", None) is not None else 1,
        "delivery_date": r.delivery_date.isoformat() if r.delivery_date else "",
        "stop_id": str(r.stop_id),
        "push_kind": kind_raw,
        "push_kind_label": _push_kind_label(kind_raw),
        "shop_order_id": str(r.shop_order_id),
        "sf_order_id": str(r.sf_order_id) if r.sf_order_id else None,
        "sf_bill_id": str(r.sf_bill_id) if r.sf_bill_id else None,
        "error_code": int(r.error_code) if r.error_code is not None else None,
        "error_msg": (r.error_msg or "")[:500] if r.error_msg else None,
        "created_at": _iso_dt(r.created_at),
        "last_callback_at": _iso_dt(r.last_callback_at),
        "last_callback_kind": r.last_callback_kind,
        "sf_callback_order_status": int(r.sf_callback_order_status)
        if r.sf_callback_order_status is not None
        else None,
        "merchant_cancel_requested_at": _iso_dt(getattr(r, "merchant_cancel_requested_at", None)),
        "sf_create_status_label": sf_monitor_create_status_label(
            error_code=int(r.error_code) if r.error_code is not None else None,
            sf_callback_order_status=int(r.sf_callback_order_status)
            if r.sf_callback_order_status is not None
            else None,
            merchant_cancel_requested_at=getattr(r, "merchant_cancel_requested_at", None),
        ),
        "members": members,
    }


def _sf_push_skip_auto_fulfillment_due_to_cancel(pus: SfSameCityPush) -> bool:
    """商户已发起取消或顺丰侧已为取消流程/终态时，勿再自动扣次/标履约。"""
    if getattr(pus, "merchant_cancel_requested_at", None) is not None:
        return True
    st = pus.sf_callback_order_status
    if st is None:
        return False
    try:
        n = int(st)
    except (TypeError, ValueError):
        return False
    return n in (2, 22, 31)


def _sf_push_effective_order_status(pus: SfSameCityPush) -> int | None:
    st = pus.sf_callback_order_status
    if st is None:
        return None
    try:
        return int(st)
    except (TypeError, ValueError):
        return None


def should_run_sf_auto_fulfillment(*, route_kind: str, pus: SfSameCityPush) -> bool:
    """
    验签通过且命中推单后是否应尝试自动履约：
    - ``order_complete`` 回调（订单完成）
    - 或推送记录上顺丰状态已为妥投完单 (17)
    """
    if not sf_push_create_succeeded(pus):
        return False
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return False
    rk = (route_kind or "").strip()
    if rk == "order_complete":
        return True
    return _sf_push_effective_order_status(pus) == SF_ORDER_STATUS_DELIVERED_TUOTOU


def should_apply_sf_cancel_sync(*, pus: SfSameCityPush) -> bool:
    """创单成功且顺丰侧已为取消/撤单终态时，回写单次点餐履约状态。"""
    if not sf_push_create_succeeded(pus):
        return False
    return sf_push_is_terminal_cancel(pus)


def _apply_sf_cancel_to_single_meal_orders_for_push(
    db: Session, pus: SfSameCityPush
) -> dict[str, Any]:
    """单次零售或大表合并中的单次点餐：顺丰取消/撤单时标 ``sf_cancelled``。"""
    result: dict[str, Any] = {"single_meal_applied": 0, "single_meal_skipped": 0, "warnings": []}
    if not sf_push_create_succeeded(pus):
        result["warnings"].append("创单未成功，跳过取消同步")
        return result
    if not should_apply_sf_cancel_sync(pus=pus):
        st = _sf_push_effective_order_status(pus)
        result["warnings"].append(f"当前不满足顺丰取消同步条件 sf_callback_order_status={st!r}")
        return result

    kind = (getattr(pus, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        if oid_retail is not None:
            if not _single_meal_order_bound_to_push(db, oid_retail, pus):
                result["single_meal_skipped"] = 1
                result["warnings"].append(
                    f"单次订单#{oid_retail}绑定的推单与当前 push#{pus.id} 不一致，跳过取消同步"
                )
                return result
            prev = db.get(SingleMealOrder, oid_retail)
            before = str(getattr(prev, "fulfillment_status", "") or "").strip().lower() if prev else ""
            mark_single_meal_sf_cancelled_no_commit(db, oid_retail)
            after_row = db.get(SingleMealOrder, oid_retail)
            after = str(getattr(after_row, "fulfillment_status", "") or "").strip().lower() if after_row else ""
            if after == "sf_cancelled" and before != "sf_cancelled":
                result["single_meal_applied"] = 1
            else:
                result["single_meal_skipped"] = 1
        else:
            msg = f"顺丰零售推单无法解析订单号 push_kind={kind} stop_id={pus.stop_id}"
            result["warnings"].append(msg)
            logger.warning(msg)
        return result

    sid = int(pus.store_id) if getattr(pus, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
    _, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    agg = None
    if (
        "fulfillment_member_ids" not in (pus.request_snapshot or {})
        and "fulfillment_single_meal_order_ids" not in (pus.request_snapshot or {})
        and not snap_oids
    ):
        agg = load_agg_for_stop_id(db, pus.delivery_date, pus.stop_id, store_id=sid)
    for oid in _single_meal_order_ids_for_push(db, pus, agg):
        if not _single_meal_order_bound_to_push(db, oid, pus):
            result["single_meal_skipped"] += 1
            continue
        prev = db.get(SingleMealOrder, oid)
        before = str(getattr(prev, "fulfillment_status", "") or "").strip().lower() if prev else ""
        mark_single_meal_sf_cancelled_no_commit(db, oid)
        after_row = db.get(SingleMealOrder, oid)
        after = str(getattr(after_row, "fulfillment_status", "") or "").strip().lower() if after_row else ""
        if after == "sf_cancelled" and before != "sf_cancelled":
            result["single_meal_applied"] += 1
        else:
            result["single_meal_skipped"] += 1
    return result


def apply_sf_cancel_to_single_meal_orders_for_push(db: Session, pus: SfSameCityPush) -> dict[str, Any]:
    """``cancel_by_sf`` / ``rider_cancel`` 等回调写入取消终态后调用（同一事务 commit 前）。"""
    out = _apply_sf_cancel_to_single_meal_orders_for_push(db, pus)
    logger.info(
        "顺丰取消同步单次点餐 push_id=%s stop_id=%s applied=%s skipped=%s warnings=%s",
        getattr(pus, "id", None),
        pus.stop_id,
        out.get("single_meal_applied"),
        out.get("single_meal_skipped"),
        out.get("warnings"),
    )
    return out


def _member_id_by_phone(db: Session, phone: str, *, store_id: int) -> int | None:
    ph = (phone or "").strip()
    if not ph or ph in ("—", "-"):
        return None
    row = db.scalar(
        select(Member.id).where(
            Member.phone == ph,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    )
    return int(row) if row is not None else None


def _ids_from_push_snapshot(snap: Any) -> tuple[list[int], list[int]]:
    """创单快照中记录的待履约会员 / 单次订单（推单时写入；旧记录可能无此字段）。"""
    if not isinstance(snap, dict):
        return [], []
    mids: list[int] = []
    oids: list[int] = []
    for key, out in (("fulfillment_member_ids", mids), ("fulfillment_single_meal_order_ids", oids)):
        raw = snap.get(key)
        if not isinstance(raw, list):
            continue
        for x in raw:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                pass
    return mids, oids


def member_subscription_delivered_on_delivery_date(
    db: Session,
    *,
    member_id: int,
    delivery_date: date,
) -> bool:
    """订阅会员在指定配送业务日是否已在 delivery_logs 标记送达（与骑手/顺丰自动履约同源）。"""
    row = db.scalar(
        select(DeliveryLog.id)
        .where(
            DeliveryLog.member_id == int(member_id),
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .limit(1)
    )
    return row is not None


def _active_sf_push_base_filter(*, store_id: int, delivery_date: date):
    from app.services.sf_same_city_service import _sf_push_row_active_predicate

    return and_(
        SfSameCityPush.store_id == int(store_id),
        SfSameCityPush.delivery_date == delivery_date,
        SfSameCityPush.error_code == 0,
        _sf_push_row_active_predicate(),
    )


def store_has_active_sf_push_on_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """门店在指定业务日是否存在未取消的顺丰创单成功记录。"""
    row = db.scalar(
        select(SfSameCityPush.id)
        .where(_active_sf_push_base_filter(store_id=int(store_id), delivery_date=delivery_date))
        .limit(1)
    )
    return row is not None


def sf_same_city_push_fully_fulfilled(
    db: Session,
    pus: SfSameCityPush,
    *,
    ags_hint: dict | None = None,
) -> bool:
    """单条顺丰推单是否已履约完毕（订阅送达 + 单次订单完成）。"""
    if not sf_push_create_succeeded(pus):
        return True
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return True

    kind = (getattr(pus, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        oid = oid_retail
        if oid is None:
            return False
        o = db.get(SingleMealOrder, oid)
        return o is not None and str(getattr(o, "fulfillment_status", "") or "").strip().lower() == "delivered"

    sid = int(pus.store_id) if getattr(pus, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
    snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    agg = None
    if not snap_mids and not snap_oids:
        agg = load_agg_for_stop_id(
            db, pus.delivery_date, pus.stop_id, store_id=sid, ags_hint=ags_hint
        )

    mids = _subscription_member_ids_for_push(db, pus, agg)
    oids = _single_meal_order_ids_for_push(db, pus, agg)
    if not mids and not oids:
        return True

    for mid in mids:
        if not member_subscription_delivered_on_delivery_date(
            db, member_id=int(mid), delivery_date=pus.delivery_date
        ):
            return False
    for oid in oids:
        o = db.get(SingleMealOrder, oid)
        if o is None or str(getattr(o, "fulfillment_status", "") or "").strip().lower() != "delivered":
            return False
    return True


def store_all_sf_pushes_fulfilled_on_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """门店当日全部有效顺丰推单均已标记送达/履约完成。"""
    return not store_has_unfulfilled_sf_push_on_delivery_date(
        db, store_id=int(store_id), delivery_date=delivery_date
    )


def store_has_unfulfilled_sf_push_on_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """是否存在未履约完毕的有效顺丰推单（遇首条未履约即返回，避免重复重建配送大表）。"""
    rows = db.scalars(
        select(SfSameCityPush).where(
            _active_sf_push_base_filter(store_id=int(store_id), delivery_date=delivery_date)
        )
    ).all()
    if not rows:
        return False

    if all(_sf_push_effective_order_status(pus) == SF_ORDER_STATUS_DELIVERED_TUOTOU for pus in rows):
        return False

    ags_hint: dict | None = None
    for pus in rows:
        st = _sf_push_effective_order_status(pus)
        if st == SF_ORDER_STATUS_DELIVERED_TUOTOU:
            continue
        if st is not None:
            return True
        snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
        if snap_mids or snap_oids:
            if not sf_push_fulfilled_quick_check(db, pus):
                return True
            continue
        if ags_hint is None:
            ags_hint = aggs_for_delivery_date(db, delivery_date, store_id=int(store_id))
        if not sf_same_city_push_fully_fulfilled(db, pus, ags_hint=ags_hint):
            return True
    return False


def _db_dialect_name(db: Session) -> str:
    return getattr(db.get_bind().dialect, "name", "") or ""


def _snapshot_member_id_like_clauses(member_id: int) -> list[Any]:
    """SQLite 等：在 request_snapshot JSON 文本中精确匹配 fulfillment_member_ids 数组元素。"""
    mid = str(int(member_id))
    snap = cast(SfSameCityPush.request_snapshot, String)
    return [
        snap.like(f'%"fulfillment_member_ids": [{mid}]%'),
        snap.like(f'%"fulfillment_member_ids": [{mid},%'),
        snap.like(f'%"fulfillment_member_ids": [%, {mid}]%'),
        snap.like(f'%"fulfillment_member_ids": [%, {mid},%'),
    ]


def _snapshot_json_array_contains(column: Any, scalar: int | str, json_path: str) -> Any:
    """MySQL：JSON 数组是否包含标量元素（如 fulfillment_member_ids）。"""
    return func.json_contains(
        func.coalesce(func.json_extract(column, json_path), "[]"),
        str(scalar),
        "$",
    )


def _member_sf_push_snapshot_match_clauses(
    db: Session,
    *,
    member_id: int,
    member_phone: str | None,
    single_meal_order_ids: list[int],
) -> list[Any]:
    """
    按会员 id / 单次订单 id / 快照收货手机精确匹配顺丰 request_snapshot。
    MySQL 走 JSON 函数；SQLite 测试环境回退 LIKE，避免 ``%{phone}%`` 扫当日全量推单行。
    """
    mid = int(member_id)
    snap = SfSameCityPush.request_snapshot
    clauses: list[Any] = []

    if _db_dialect_name(db) == "mysql":
        clauses.append(_snapshot_json_array_contains(snap, mid, "$.fulfillment_member_ids"))
        for oid in single_meal_order_ids:
            clauses.append(
                _snapshot_json_array_contains(snap, int(oid), "$.fulfillment_single_meal_order_ids")
            )
        ph = (member_phone or "").strip()
        if ph:
            clauses.append(
                func.json_unquote(func.json_extract(snap, "$.preview_row.recv_phone")) == ph
            )
        return clauses

    clauses.extend(_snapshot_member_id_like_clauses(mid))
    snap_text = cast(snap, String)
    for oid in single_meal_order_ids:
        oid_s = str(int(oid))
        clauses.extend(
            [
                snap_text.like(f'%"fulfillment_single_meal_order_ids": [{oid_s}]%'),
                snap_text.like(f'%"fulfillment_single_meal_order_ids": [{oid_s},%'),
                snap_text.like(f'%"fulfillment_single_meal_order_ids": [%, {oid_s}]%'),
                snap_text.like(f'%"fulfillment_single_meal_order_ids": [%, {oid_s},%'),
            ]
        )
    ph = (member_phone or "").strip()
    if ph:
        clauses.append(snap_text.like(f'%"recv_phone": "{ph}"%'))
    return clauses


def _member_on_sf_push(
    db: Session,
    pus: SfSameCityPush,
    *,
    member_id: int,
    member_phone: str | None = None,
) -> bool:
    """推单快照/停靠点是否包含指定会员（订阅、单次零售或旧版手机号快照）。"""
    mid = int(member_id)
    snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    if mid in snap_mids:
        return True

    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if oid_retail is not None:
        o = db.get(SingleMealOrder, oid_retail)
        return o is not None and int(o.member_id) == mid

    for oid in snap_oids:
        o = db.get(SingleMealOrder, oid)
        if o is not None and int(o.member_id) == mid:
            return True

    ph = (member_phone or "").strip()
    if not ph:
        return False
    snap = pus.request_snapshot
    if not isinstance(snap, dict):
        return False
    pr = snap.get("preview_row")
    if not isinstance(pr, dict):
        return False
    return str(pr.get("recv_phone") or "").strip() == ph


def _member_active_sf_pushes_on_delivery_date(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    delivery_date: date,
    member_phone: str | None = None,
) -> list[SfSameCityPush]:
    """仅返回与指定会员相关的当日有效顺丰推单（不重建配送大表）。"""
    mid = int(member_id)
    sid = int(store_id)
    phone = (member_phone or "").strip()
    if not phone:
        member = db.get(Member, mid)
        phone = (member.phone or "").strip() if member else ""

    base = _active_sf_push_base_filter(store_id=sid, delivery_date=delivery_date)

    order_ids = [
        int(oid)
        for oid in db.scalars(
            select(SingleMealOrder.id).where(
                SingleMealOrder.member_id == mid,
                SingleMealOrder.delivery_date == delivery_date,
            )
        ).all()
    ]

    or_parts: list[Any] = _member_sf_push_snapshot_match_clauses(
        db,
        member_id=mid,
        member_phone=phone or None,
        single_meal_order_ids=order_ids,
    )
    if order_ids:
        or_parts.append(
            SfSameCityPush.stop_id.in_(f"retail-smo-{int(oid)}" for oid in order_ids)
        )

    if not or_parts:
        return []

    rows = db.scalars(select(SfSameCityPush).where(and_(base, or_(*or_parts)))).all()
    seen: set[int] = set()
    out: list[SfSameCityPush] = []
    for pus in rows:
        pid = int(pus.id)
        if pid in seen:
            continue
        if not _member_on_sf_push(db, pus, member_id=mid, member_phone=phone):
            continue
        seen.add(pid)
        out.append(pus)
    return out


def _member_sf_push_fulfilled_for_lock(db: Session, pus: SfSameCityPush, *, member_id: int) -> bool:
    """当前会员在该推单上是否已视为配送完成（顺丰妥投或内部已标送达）。"""
    if not sf_push_create_succeeded(pus):
        return True
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return True
    if _sf_push_effective_order_status(pus) == SF_ORDER_STATUS_DELIVERED_TUOTOU:
        return True

    mid = int(member_id)
    snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    if mid in snap_mids:
        return member_subscription_delivered_on_delivery_date(
            db, member_id=mid, delivery_date=pus.delivery_date
        )

    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if oid_retail is not None:
        o = db.get(SingleMealOrder, oid_retail)
        if o is None or int(o.member_id) != mid:
            return True
        return str(getattr(o, "fulfillment_status", "") or "").strip().lower() == "delivered"

    for oid in snap_oids:
        o = db.get(SingleMealOrder, oid)
        if o is not None and int(o.member_id) == mid:
            return str(getattr(o, "fulfillment_status", "") or "").strip().lower() == "delivered"

    return member_subscription_delivered_on_delivery_date(
        db, member_id=mid, delivery_date=pus.delivery_date
    )


def member_sf_self_service_locked_on_delivery_date(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    delivery_date: date,
    member_phone: str | None = None,
) -> bool:
    """
    当前会员当日命中顺丰推单且其配送尚未完成：锁定小程序自助改地址/份数/请假等。

    仅查与该会员相关的推单；门店其他会员的推单/履约状态不影响本会员。
    调用方应传入 ``member_phone`` 与 ``delivery_date``，避免为查手机再读 members 且用 JSON 精确匹配快照。
    """
    pushes = _member_active_sf_pushes_on_delivery_date(
        db,
        member_id=int(member_id),
        store_id=int(store_id),
        delivery_date=delivery_date,
        member_phone=member_phone,
    )
    if not pushes:
        return False
    for pus in pushes:
        if not _member_sf_push_fulfilled_for_lock(db, pus, member_id=int(member_id)):
            return True
    return False


def member_has_active_sf_push_on_delivery_date(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    delivery_date: date,
    member_phone: str | None = None,
) -> bool:
    """会员在指定业务日是否命中未取消的顺丰推单。"""
    return bool(
        _member_active_sf_pushes_on_delivery_date(
            db,
            member_id=int(member_id),
            store_id=int(store_id),
            delivery_date=delivery_date,
            member_phone=member_phone,
        )
    )


def _subscription_member_ids_for_push(db: Session, pus: SfSameCityPush, agg: Any | None) -> list[int]:
    """订阅待扣次会员：以创单快照 ``fulfillment_member_ids`` 为准，禁止用推单后重建的大表扩名单。"""
    snap = pus.request_snapshot
    if isinstance(snap, dict) and "fulfillment_member_ids" in snap:
        mids, _ = _ids_from_push_snapshot(snap)
        return mids

    seen: set[int] = set()
    out: list[int] = []

    def add(mid: int | None) -> None:
        if mid is None:
            return
        im = int(mid)
        if im in seen:
            return
        seen.add(im)
        out.append(im)

    if agg is not None:
        for sl in getattr(agg, "sub_lines", None) or []:
            if sl.get("is_delivered"):
                continue
            if int(sl.get("units") or 0) <= 0:
                continue
            try:
                add(int(sl["member_id"]))
            except (KeyError, TypeError, ValueError):
                pass

    snap_mids, _ = _ids_from_push_snapshot(snap)
    for mid in snap_mids:
        add(mid)

    if out:
        return out

    if isinstance(snap, dict):
        pr = snap.get("preview_row")
        if isinstance(pr, dict):
            sid = int(pus.store_id) if getattr(pus, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
            add(_member_id_by_phone(db, str(pr.get("recv_phone") or ""), store_id=sid))
    return out


def _preview_single_meal_count_from_push_snapshot(snap: Any) -> int | None:
    """推单快照 preview_row 中的单次份数；无 preview 时返回 None（旧数据）。"""
    if not isinstance(snap, dict):
        return None
    pr = snap.get("preview_row")
    if not isinstance(pr, dict):
        return None
    try:
        return int(pr.get("single_meal_count") or 0)
    except (TypeError, ValueError):
        return 0


def _single_meal_order_ids_for_push(db: Session, pus: SfSameCityPush, agg: Any | None) -> list[int]:
    """
    本推单应履约的单次订单 id。

    仅以创单快照为准；推单后新下的单次卡不得因「重建大表聚合」被误标送达。
    """
    snap = pus.request_snapshot
    if isinstance(snap, dict) and "fulfillment_single_meal_order_ids" in snap:
        _, oids = _ids_from_push_snapshot(snap)
        return oids

    preview_sq = _preview_single_meal_count_from_push_snapshot(snap)
    if preview_sq is not None and preview_sq <= 0:
        return []

    seen: set[int] = set()
    out: list[int] = []

    def add(oid: int | None) -> None:
        if oid is None:
            return
        io = int(oid)
        if io in seen:
            return
        seen.add(io)
        out.append(io)

    push_ts = getattr(pus, "created_at", None)
    if agg is not None:
        for sng in getattr(agg, "singles", None) or []:
            try:
                oid = int(sng["id"])
            except (KeyError, TypeError, ValueError):
                continue
            if push_ts is not None:
                row = db.get(SingleMealOrder, oid)
                if row is not None and row.created_at is not None and row.created_at > push_ts:
                    continue
            add(oid)

    _, snap_oids = _ids_from_push_snapshot(snap)
    for oid in snap_oids:
        add(oid)
    return out


def _apply_sf_same_city_stop_fulfillment(
    db: Session,
    pus: SfSameCityPush,
    *,
    operator_tag: str,
    ok_ids_home: set[int] | None = None,
    renew_pending: list[tuple[Member, int]] | None = None,
) -> dict[str, Any]:
    """
    同一停靠点的订阅扣次 + 单点餐履约标记；已由各类顺丰回调按需调用。

    ``single_meal_retail``（或 stop_id 为 retail-smo-*）仅处理对应单次订单，不走大表聚合。
    """
    result: dict[str, Any] = {
        "subscription_applied": 0,
        "subscription_skipped": 0,
        "single_meal_applied": 0,
        "single_meal_skipped": 0,
        "warnings": [],
    }
    if not sf_push_create_succeeded(pus):
        result["warnings"].append("创单未成功，跳过履约")
        return result
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        result["warnings"].append("订单已取消或取消中，跳过履约")
        return result
    kind = (getattr(pus, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        if oid_retail is not None:
            if not _single_meal_order_bound_to_push(db, oid_retail, pus):
                result["single_meal_skipped"] = 1
                result["warnings"].append(
                    f"单次订单#{oid_retail}绑定的推单与当前 push#{pus.id} 不一致，跳过标履约"
                )
                return result
            prev = db.get(SingleMealOrder, oid_retail)
            before = str(getattr(prev, "fulfillment_status", "") or "").strip().lower() if prev else ""
            mark_single_meal_delivered_sf_completion_no_commit(db, oid_retail)
            after_row = db.get(SingleMealOrder, oid_retail)
            after = str(getattr(after_row, "fulfillment_status", "") or "").strip().lower() if after_row else ""
            if after == "delivered" and before != "delivered":
                result["single_meal_applied"] = 1
            else:
                result["single_meal_skipped"] = 1
        else:
            msg = f"顺丰零售推单无法解析订单号 push_kind={kind} stop_id={pus.stop_id}"
            result["warnings"].append(msg)
            logger.warning(msg)
        return result

    sid = int(pus.store_id) if getattr(pus, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
    snap_mids, snap_oids = _ids_from_push_snapshot(pus.request_snapshot)
    home_ok_ids = ok_ids_home
    if home_ok_ids is None:
        from app.services.admin_delivery_fulfillment_service import _eligible_ids_home

        home_ok_ids = _eligible_ids_home(db, pus.delivery_date, store_id=sid)
    if snap_mids:
        home_ok_ids = set(home_ok_ids) | {int(x) for x in snap_mids}

    agg = None
    if not snap_mids and not snap_oids:
        agg = load_agg_for_stop_id(db, pus.delivery_date, pus.stop_id, store_id=sid)
        if agg is None:
            result["warnings"].append(
                f"未解析到停靠点聚合 stop_id={pus.stop_id} date={pus.delivery_date}，将尝试快照/收件人回退"
            )
            logger.warning(
                "顺丰履约未解析到停靠点 stop_id=%s date=%s store_id=%s，尝试快照回退",
                pus.stop_id,
                pus.delivery_date,
                sid,
            )

    for mid in _subscription_member_ids_for_push(db, pus, agg):
        sf_trusted_mids = {int(x) for x in snap_mids} | {int(mid)}
        member_ok_ids = set(home_ok_ids) | sf_trusted_mids
        try:
            renew = subscription_fulfilled_try_sf_home_no_commit(
                db,
                member_id=mid,
                delivery_date=pus.delivery_date,
                operator_tag=operator_tag,
                store_id=sid,
                ok_ids=member_ok_ids,
            )
            if renew is not None and renew_pending is not None:
                renew_pending.append(renew)
            result["subscription_applied"] += 1
        except HTTPException as e:
            result["subscription_skipped"] += 1
            logger.info(
                "顺丰自动履约跳过订阅 member_id=%s date=%s detail=%s",
                mid,
                pus.delivery_date,
                getattr(e, "detail", e),
            )

    for oid in _single_meal_order_ids_for_push(db, pus, agg):
        if not _single_meal_order_bound_to_push(db, oid, pus):
            result["single_meal_skipped"] += 1
            continue
        prev = db.get(SingleMealOrder, oid)
        before = str(getattr(prev, "fulfillment_status", "") or "").strip().lower() if prev else ""
        mark_single_meal_delivered_sf_completion_no_commit(db, oid)
        after_row = db.get(SingleMealOrder, oid)
        after = str(getattr(after_row, "fulfillment_status", "") or "").strip().lower() if after_row else ""
        if after == "delivered" and before != "delivered":
            result["single_meal_applied"] += 1
        else:
            result["single_meal_skipped"] += 1

    if (
        result["subscription_applied"] == 0
        and result["single_meal_applied"] == 0
        and not result["warnings"]
        and result["subscription_skipped"] == 0
        and result["single_meal_skipped"] == 0
    ):
        result["warnings"].append("未找到待履约的订阅会员或单次订单")
    return result


def apply_sf_order_complete_fulfillment(db: Session, pus: SfSameCityPush) -> dict[str, Any]:
    """
    ``route_kind=order_complete`` 且验签通过、已匹配推单记录时调用（由回调落库前写入，同一事务 commit）。

    - 仅处理 ``error_code == 0`` 的成功创单记录。
    - 订阅：按停靠点聚合内待送达会员逐条执行与 admin 大表「标记送达（到家）」相同扣次。
    - 单次点餐：标 ``fulfillment_status=delivered``（已付餐费，不扣次数）。
    """
    out = _apply_sf_same_city_stop_fulfillment(db, pus, operator_tag="sf:order_complete")
    logger.info(
        "顺丰 order_complete 自动履约 push_id=%s stop_id=%s subs=%s singles=%s warnings=%s",
        getattr(pus, "id", None),
        pus.stop_id,
        out.get("subscription_applied"),
        out.get("single_meal_applied"),
        out.get("warnings"),
    )
    return out


def apply_sf_delivery_status_tuotou(db: Session, pus: SfSameCityPush) -> dict[str, Any]:
    """
    顺丰状态为妥投完单 (17) 时调用（配送状态变更或订单完成回调均可）。

    按推单行上的业务配送日执行扣次 / 单次标履约（与 ``order_complete`` 路径一致）。
    妥投常在深夜回调，不再限制「须等于上海当日日期」，避免静默跳过；
    重复回调由送达流水幂等处理。
    """
    if pus.delivery_date is None:
        return {"warnings": ["缺少业务配送日，跳过履约"]}
    out = _apply_sf_same_city_stop_fulfillment(db, pus, operator_tag="sf:delivery_status")
    logger.info(
        "顺丰妥投(17) 自动履约 push_id=%s stop_id=%s subs=%s singles=%s warnings=%s",
        getattr(pus, "id", None),
        pus.stop_id,
        out.get("subscription_applied"),
        out.get("single_meal_applied"),
        out.get("warnings"),
    )
    return out


def apply_sf_auto_fulfillment_for_push(
    db: Session,
    pus: SfSameCityPush,
    *,
    operator_tag: str,
    route_kind: str = "",
    renew_pending: list[tuple[Member, int]] | None = None,
) -> dict[str, Any]:
    """回调 / 管理端补跑统一入口：按 operator_tag 执行幂等履约。"""
    if not should_run_sf_auto_fulfillment(route_kind=route_kind, pus=pus):
        st = _sf_push_effective_order_status(pus)
        return {
            "warnings": [
                f"当前不满足自动履约条件（创单失败/已取消/非妥投）；"
                f"route_kind={route_kind!r} sf_callback_order_status={st!r}"
            ]
        }
    if sf_push_fulfilled_quick_check(db, pus):
        return {"skipped": "already_fulfilled", "warnings": []}
    tag = (operator_tag or "sf:manual_retry").strip()[:50] or "sf:manual_retry"
    return _apply_sf_same_city_stop_fulfillment(
        db, pus, operator_tag=tag, renew_pending=renew_pending
    )


def run_sf_push_side_effect_for_callback(db: Session, job: SfCallbackSideEffectJob) -> dict[str, Any]:
    """
    顺丰回调异步任务：扣次/取消同步 + commit；续费提醒在 commit 后发送。
    同一 push_id 使用 MySQL advisory lock，避免 order_complete 与 status=17 并发双扣。
    """
    pus = db.get(SfSameCityPush, int(job.push_id))
    if pus is None:
        return {"warnings": ["推单记录不存在"]}

    locked = _sf_fulfillment_try_lock(db, int(job.push_id))
    if not locked:
        logger.info("顺丰异步履约跳过（同 push 正在处理） push_id=%s", job.push_id)
        return {"skipped": "lock_busy"}

    renew_pending: list[tuple[Member, int]] = []
    try:
        if job.action == "cancel_sync":
            out = _apply_sf_cancel_to_single_meal_orders_for_push(db, pus)
            db.commit()
            logger.info(
                "顺丰异步取消同步 push_id=%s applied=%s skipped=%s",
                job.push_id,
                out.get("single_meal_applied"),
                out.get("single_meal_skipped"),
            )
            return out

        if job.action != "fulfillment":
            return {"warnings": [f"未知 action={job.action!r}"]}

        if sf_push_fulfilled_quick_check(db, pus):
            logger.info("顺丰异步履约跳过（已履约） push_id=%s route_kind=%s", job.push_id, job.route_kind)
            return {"skipped": "already_fulfilled"}

        out = apply_sf_auto_fulfillment_for_push(
            db,
            pus,
            operator_tag=job.operator_tag,
            route_kind=job.route_kind,
            renew_pending=renew_pending,
        )
        db.commit()
        _flush_renew_reminds(db, renew_pending)
        logger.info(
            "顺丰异步履约完成 push_id=%s route_kind=%s subs=%s singles=%s warnings=%s",
            job.push_id,
            job.route_kind,
            out.get("subscription_applied"),
            out.get("single_meal_applied"),
            out.get("warnings"),
        )
        return out
    except Exception:
        db.rollback()
        raise
    finally:
        if locked:
            _sf_fulfillment_release_lock(db, int(job.push_id))


def admin_apply_sf_fulfillment_for_push_id(db: Session, *, push_id: int) -> dict[str, Any]:
    """管理端：对单条顺丰推单记录补跑标记送达/扣次（幂等）。"""
    pus = db.get(SfSameCityPush, int(push_id))
    if pus is None:
        raise ValueError("推单记录不存在")
    if not sf_push_create_succeeded(pus):
        raise ValueError("仅创单成功的记录可补跑履约")
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        raise ValueError("该单已取消或取消中，不可补跑履约")
    st = _sf_push_effective_order_status(pus)
    if st != SF_ORDER_STATUS_DELIVERED_TUOTOU:
        raise ValueError(
            f"顺丰回调状态须为妥投完单(17)，当前为 {st!r}。"
            "若监控已显示妥投但此处报错，请确认回调验签通过且状态已落库。"
        )
    renew_pending: list[tuple[Member, int]] = []
    out = apply_sf_auto_fulfillment_for_push(
        db,
        pus,
        operator_tag="admin:sf_fulfillment_retry",
        route_kind="order_complete",
        renew_pending=renew_pending,
    )
    db.commit()
    _flush_renew_reminds(db, renew_pending)
    parts = [
        f"订阅扣次 {out.get('subscription_applied', 0)} 人",
        f"跳过 {out.get('subscription_skipped', 0)} 人",
        f"单次标履约 {out.get('single_meal_applied', 0)} 单",
    ]
    warns = out.get("warnings") or []
    if warns:
        parts.append("提示：" + "；".join(str(w) for w in warns))
    out["summary"] = "；".join(parts)
    return out


def bulk_admin_resync_subscription_fulfilled_from_sf_monitor_for_delivery_day(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    max_pushes: int = 500,
) -> dict[str, Any]:
    """
    按配送业务日批量补跑：创单成功且顺丰回调已为妥投(17)的大表推单，逐停靠点幂等扣次/写 delivery_logs。
    """
    mx = max(1, min(500, int(max_pushes or 500)))
    rows = list(
        db.scalars(
            select(SfSameCityPush)
            .where(
                SfSameCityPush.store_id == int(store_id),
                SfSameCityPush.delivery_date == delivery_date,
                SfSameCityPush.error_code == 0,
                SfSameCityPush.sf_callback_order_status == SF_ORDER_STATUS_DELIVERED_TUOTOU,
                ~_sf_push_monitor_cancelled_clause(),
                or_(
                    SfSameCityPush.push_kind.is_(None),
                    SfSameCityPush.push_kind == "",
                    SfSameCityPush.push_kind == SF_PUSH_KIND_DELIVERY_SHEET,
                ),
            )
            .order_by(SfSameCityPush.id.asc())
            .limit(mx)
        ).all()
    )
    scanned = len(rows)
    subs_applied = 0
    subs_skipped = 0
    singles_applied = 0
    warnings: list[str] = []

    for pus in rows:
        renew_pending: list[tuple[Member, int]] = []
        out = apply_sf_auto_fulfillment_for_push(
            db,
            pus,
            operator_tag="admin:sf_bulk_resync",
            route_kind="order_complete",
            renew_pending=renew_pending,
        )
        subs_applied += int(out.get("subscription_applied") or 0)
        subs_skipped += int(out.get("subscription_skipped") or 0)
        singles_applied += int(out.get("single_meal_applied") or 0)
        for w in out.get("warnings") or []:
            ws = str(w).strip()
            if ws and ws not in warnings:
                warnings.append(ws)
        db.commit()
        _flush_renew_reminds(db, renew_pending)

    summary = (
        f"扫描 {scanned} 条大表推单；订阅扣次 {subs_applied} 人次；"
        f"跳过 {subs_skipped} 人次；单次标履约 {singles_applied} 单。"
        "（幂等；已送达会员不会重复扣次）"
    )
    return {
        "scanned": scanned,
        "subscription_applied": subs_applied,
        "subscription_skipped": subs_skipped,
        "single_meal_applied": singles_applied,
        "warnings": warnings[:20],
        "summary": summary,
    }


def list_sf_same_city_pushes_for_monitor(
    db: Session,
    *,
    delivery_date: date | None,
    page: int,
    page_size: int,
    sf_callback_order_status: int | None = None,
    callback_order_status_unknown: bool = False,
    store_id: int | None = None,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """按业务日、顺丰回调配送状态可选筛选，创建时间倒序分页。"""
    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    wc = _sf_push_monitor_where_clauses(
        delivery_date=delivery_date,
        store_id=store_id,
        sf_callback_order_status=sf_callback_order_status,
        callback_order_status_unknown=callback_order_status_unknown,
        sf_create_status=sf_create_status,
        sf_order_id_contains=sf_order_id_contains,
        member_phone_contains=member_phone_contains,
        push_kind=push_kind,
    )
    flt = and_(*wc) if wc else sql_true()
    fq = select(func.count()).select_from(SfSameCityPush).where(flt)
    total = int(db.scalar(fq) or 0)

    q = select(SfSameCityPush).where(flt).order_by(SfSameCityPush.id.desc())
    off = max(0, (page - 1) * page_size)
    rows = list(db.scalars(q.offset(off).limit(page_size)).all())

    agg_cache: dict[tuple[date, int], dict[str, Any]] = {}

    def _aggs_for_row(r: SfSameCityPush) -> dict[str, Any]:
        d0 = r.delivery_date
        if d0 is None:
            return {}
        sid = int(r.store_id) if getattr(r, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
        k = (d0, sid)
        if k not in agg_cache:
            agg_cache[k] = aggs_for_delivery_date(db, d0, store_id=sid)
        return agg_cache[k]

    out = [_sf_push_monitor_row_dict(db, r, _aggs_for_row(r)) for r in rows]
    return out, total


def list_sf_same_city_pushes_for_monitor_export(
    db: Session,
    *,
    delivery_date: date | None,
    sf_callback_order_status: int | None = None,
    callback_order_status_unknown: bool = False,
    store_id: int | None = None,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> list[dict[str, Any]]:
    """与监控列表同源筛选，不分页；用于 Excel 导出。"""
    if delivery_date is None:
        raise ValueError("导出须指定业务日 delivery_date")

    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    wc = _sf_push_monitor_where_clauses(
        delivery_date=delivery_date,
        store_id=store_id,
        sf_callback_order_status=sf_callback_order_status,
        callback_order_status_unknown=callback_order_status_unknown,
        sf_create_status=sf_create_status,
        sf_order_id_contains=sf_order_id_contains,
        member_phone_contains=member_phone_contains,
        push_kind=push_kind,
    )
    flt = and_(*wc) if wc else sql_true()
    q = select(SfSameCityPush).where(flt).order_by(SfSameCityPush.id.desc())
    rows = list(db.scalars(q).all())

    agg_cache: dict[tuple[date, int], dict[str, Any]] = {}

    def _aggs_for_row(r: SfSameCityPush) -> dict[str, Any]:
        d0 = r.delivery_date
        if d0 is None:
            return {}
        sid = int(r.store_id) if getattr(r, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
        k = (d0, sid)
        if k not in agg_cache:
            agg_cache[k] = aggs_for_delivery_date(db, d0, store_id=sid)
        return agg_cache[k]

    return [_sf_push_monitor_row_dict(db, r, _aggs_for_row(r)) for r in rows]


def _sf_push_monitor_normalized_kind_expr():
    return case(
        (SfSameCityPush.push_kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL, SF_PUSH_KIND_SINGLE_MEAL_RETAIL),
        else_=SF_PUSH_KIND_DELIVERY_SHEET,
    )


def count_sf_same_city_pushes_for_delivery_date(
    db: Session,
    *,
    store_id: int | None,
    delivery_date: date,
) -> dict[str, Any]:
    """按推送记录上的配送业务日 ``delivery_date`` 统计创单成功 / 失败 / 取消（与列表筛选口径一致）。"""
    conds = [SfSameCityPush.delivery_date == delivery_date]
    if store_id is not None:
        conds.append(SfSameCityPush.store_id == int(store_id))

    flt = and_(*conds)
    cancelled_flt = _sf_push_monitor_cancelled_clause()
    success_case = case(
        (and_(SfSameCityPush.error_code == 0, ~cancelled_flt), 1),
        else_=0,
    )
    failed_case = case(
        (or_(SfSameCityPush.error_code.is_(None), SfSameCityPush.error_code != 0), 1),
        else_=0,
    )
    cancelled_case = case((cancelled_flt, 1), else_=0)
    kind_expr = _sf_push_monitor_normalized_kind_expr()

    rows = db.execute(
        select(
            kind_expr.label("push_kind"),
            func.count().label("total"),
            func.sum(success_case).label("success"),
            func.sum(failed_case).label("failed"),
            func.sum(cancelled_case).label("cancelled"),
        )
        .select_from(SfSameCityPush)
        .where(flt)
        .group_by(kind_expr)
    ).all()

    empty_stats = {"total": 0, "success": 0, "failed": 0, "cancelled": 0}
    by_kind: dict[str, dict[str, int]] = {
        SF_PUSH_KIND_DELIVERY_SHEET: dict(empty_stats),
        SF_PUSH_KIND_SINGLE_MEAL_RETAIL: dict(empty_stats),
    }
    for row in rows:
        k = row.push_kind or SF_PUSH_KIND_DELIVERY_SHEET
        by_kind[k] = {
            "total": int(row.total or 0),
            "success": int(row.success or 0),
            "failed": int(row.failed or 0),
            "cancelled": int(row.cancelled or 0),
        }

    overall = dict(empty_stats)
    for stats in by_kind.values():
        for key in overall:
            overall[key] += stats[key]

    return {
        **overall,
        "delivery_sheet": by_kind[SF_PUSH_KIND_DELIVERY_SHEET],
        "single_meal_retail": by_kind[SF_PUSH_KIND_SINGLE_MEAL_RETAIL],
    }

