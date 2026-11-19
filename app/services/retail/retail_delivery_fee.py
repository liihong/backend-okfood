"""商城零售：分类可配置配送费（仅普通商品；默认 included 不影响现网）。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_category import StoreRetailCategory
from app.services.retail.retail_order_lines import ResolvedRetailLine

_TWO = Decimal("0.01")
MODE_INCLUDED = "included"
MODE_EXTRA_RULE = "extra_rule"
RULE_QTY_THRESHOLD = "qty_threshold_fee"


@dataclass(frozen=True)
class RetailDeliveryFeeBreakdownItem:
    """单分类配送费明细（对账 / 前台展示）。"""

    category_id: int
    category_name: str
    total_qty: int
    fee_yuan: Decimal
    rule_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": int(self.category_id),
            "category_name": str(self.category_name),
            "total_qty": int(self.total_qty),
            "fee_yuan": f"{Decimal(self.fee_yuan).quantize(_TWO):.2f}",
            "rule_type": str(self.rule_type),
        }


def _parse_qty_threshold_rule(raw: dict | None) -> dict[str, Any] | None:
    if not raw or not isinstance(raw, dict):
        return None
    if str(raw.get("rule_type") or "").strip() != RULE_QTY_THRESHOLD:
        return None
    fee = Decimal(str(raw.get("fee_yuan") or "0")).quantize(_TWO)
    max_q = int(raw.get("max_qty_inclusive") or 0)
    if max_q < 1:
        return None
    label = str(raw.get("qty_unit_label") or "件").strip() or "件"
    return {"fee_yuan": fee, "max_qty_inclusive": max_q, "qty_unit_label": label}


def category_delivery_mode(cat: StoreRetailCategory | None) -> str:
    if not cat:
        return MODE_INCLUDED
    mode = str(getattr(cat, "delivery_pricing_mode", None) or MODE_INCLUDED).strip()
    return mode if mode in (MODE_INCLUDED, MODE_EXTRA_RULE) else MODE_INCLUDED


def build_category_delivery_hint(cat: StoreRetailCategory | None) -> str | None:
    """C 端菜单分类提示文案。"""
    if not cat or category_delivery_mode(cat) != MODE_EXTRA_RULE:
        return None
    parsed = _parse_qty_threshold_rule(cat.delivery_rule if isinstance(cat.delivery_rule, dict) else None)
    if not parsed:
        return None
    unit = parsed["qty_unit_label"]
    fee = parsed["fee_yuan"]
    max_q = int(parsed["max_qty_inclusive"])
    return f"{max_q}{unit}内配送费¥{fee:.2f}，满{max_q + 1}{unit}免配送"


def _fee_for_qty_threshold(total_qty: int, rule: dict[str, Any]) -> Decimal:
    max_q = int(rule["max_qty_inclusive"])
    if total_qty <= max_q:
        return Decimal(rule["fee_yuan"]).quantize(_TWO)
    return Decimal("0.00")


def compute_retail_delivery_fee(
    db: Session,
    *,
    lines: list[ResolvedRetailLine],
    store_pickup: bool,
    store_id: int,
) -> tuple[Decimal, list[RetailDeliveryFeeBreakdownItem]]:
    """
    计算商城订单配送费。
    - 自提：恒为 0
    - 仅对 delivery_pricing_mode=extra_rule 的分类汇总数量后计一次费
    """
    _ = db
    if store_pickup or not lines:
        return Decimal("0.00"), []

    qty_by_cat: dict[int, int] = {}
    cat_ids: set[int] = set()
    for ln in lines:
        cid = int(ln.spu.category_id) if ln.spu.category_id is not None else None
        if cid is None:
            continue
        cat_ids.add(cid)
        qty_by_cat[cid] = qty_by_cat.get(cid, 0) + int(ln.quantity)

    if not cat_ids:
        return Decimal("0.00"), []

    cats = {
        int(c.id): c
        for c in db.scalars(
            select(StoreRetailCategory).where(
                StoreRetailCategory.id.in_(sorted(cat_ids)),
                StoreRetailCategory.store_id == int(store_id),
            )
        ).all()
    }

    total_fee = Decimal("0.00")
    breakdown: list[RetailDeliveryFeeBreakdownItem] = []
    for cid in sorted(qty_by_cat.keys()):
        cat = cats.get(cid)
        if category_delivery_mode(cat) != MODE_EXTRA_RULE:
            continue
        rule_raw = cat.delivery_rule if cat and isinstance(cat.delivery_rule, dict) else None
        parsed = _parse_qty_threshold_rule(rule_raw)
        if not parsed:
            continue
        qty = int(qty_by_cat[cid])
        fee = _fee_for_qty_threshold(qty, parsed)
        if fee <= 0 and qty > int(parsed["max_qty_inclusive"]):
            breakdown.append(
                RetailDeliveryFeeBreakdownItem(
                    category_id=cid,
                    category_name=str(cat.name if cat else ""),
                    total_qty=qty,
                    fee_yuan=Decimal("0.00"),
                    rule_type=RULE_QTY_THRESHOLD,
                )
            )
            continue
        if fee > 0:
            total_fee += fee
            breakdown.append(
                RetailDeliveryFeeBreakdownItem(
                    category_id=cid,
                    category_name=str(cat.name if cat else ""),
                    total_qty=qty,
                    fee_yuan=fee,
                    rule_type=RULE_QTY_THRESHOLD,
                )
            )
    return total_fee.quantize(_TWO), breakdown


def retail_category_api_fields(cat: StoreRetailCategory) -> dict[str, Any]:
    """管理端分类序列化（含配送配置）。"""
    mode = category_delivery_mode(cat)
    rule = cat.delivery_rule if isinstance(cat.delivery_rule, dict) else None
    hint = build_category_delivery_hint(cat)
    return {
        "id": int(cat.id),
        "store_id": int(cat.store_id),
        "name": cat.name,
        "sort_order": int(cat.sort_order),
        "is_active": bool(cat.is_active),
        "delivery_pricing_mode": mode,
        "delivery_rule": rule,
        "delivery_hint": hint,
    }