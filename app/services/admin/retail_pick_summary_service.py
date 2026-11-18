"""管理端：商城零售 SKU 备货汇总（已接单 · 待发货，全 SKU）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_product import StoreRetailProduct
from app.schemas.retail_pick_summary import RetailPickSummaryOut, RetailPickSummarySkuOut
from app.services.admin.store_retail_order_admin_service import apply_retail_pick_summary_order_filters
from app.services.retail.retail_display import retail_sku_display_title
from app.services.retail.retail_order_item_repo import load_order_items_map

_SCOPE_LABEL = "已支付 · 已接单 · 待发货"


@dataclass
class _AggBucket:
    total_boxes: int = 0
    order_ids: set[int] = field(default_factory=set)
    pickup_boxes: int = 0
    delivery_boxes: int = 0
    spu_title: str | None = None
    spec_label: str | None = None
    product_title: str | None = None
    category_id: int | None = None


def _add_line(
    buckets: dict[int, _AggBucket],
    *,
    order_id: int,
    retail_product_id: int,
    quantity: int,
    store_pickup: bool,
    spu_title: str | None,
    spec_label: str | None,
    product_title: str | None,
    category_id: int | None,
) -> None:
    pid = int(retail_product_id)
    qty = max(0, int(quantity))
    if pid <= 0 or qty <= 0:
        return
    bucket = buckets.setdefault(pid, _AggBucket())
    bucket.total_boxes += qty
    bucket.order_ids.add(int(order_id))
    if store_pickup:
        bucket.pickup_boxes += qty
    else:
        bucket.delivery_boxes += qty
    if spu_title and not bucket.spu_title:
        bucket.spu_title = spu_title.strip() or None
    if spec_label and not bucket.spec_label:
        bucket.spec_label = spec_label.strip() or None
    if product_title and not bucket.product_title:
        bucket.product_title = product_title.strip() or None
    if category_id is not None and bucket.category_id is None:
        bucket.category_id = int(category_id)


def build_retail_pick_summary(db: Session, *, store_id: int) -> RetailPickSummaryOut:
    """汇总当前门店待备货队列内全部 SKU 盒数。"""
    sid = int(store_id)
    filters: list = []
    apply_retail_pick_summary_order_filters(filters)
    filters.insert(0, StoreRetailOrder.store_id == sid)

    order_rows = list(db.scalars(select(StoreRetailOrder).where(*filters)).all())
    order_count = len(order_rows)
    if not order_rows:
        return RetailPickSummaryOut(
            scope_label=_SCOPE_LABEL,
            order_count=0,
            sku_count=0,
            grand_total_boxes=0,
            items=[],
        )

    order_ids = [int(o.id) for o in order_rows]
    order_by_id = {int(o.id): o for o in order_rows}
    pickup_by_order = {int(o.id): bool(o.store_pickup) for o in order_rows}
    items_map = load_order_items_map(db, order_ids)

    buckets: dict[int, _AggBucket] = {}
    for oid in order_ids:
        lines = items_map.get(oid, [])
        pickup = pickup_by_order.get(oid, False)
        if lines:
            for line in lines:
                _add_line(
                    buckets,
                    order_id=oid,
                    retail_product_id=int(line.retail_product_id),
                    quantity=int(line.quantity or 1),
                    store_pickup=pickup,
                    spu_title=str(line.spu_title) if line.spu_title else None,
                    spec_label=str(line.spec_label) if line.spec_label else None,
                    product_title=str(line.product_title or ""),
                    category_id=int(line.category_id) if line.category_id is not None else None,
                )
            continue
        o = order_by_id.get(oid)
        if o is None:
            continue
        _add_line(
            buckets,
            order_id=oid,
            retail_product_id=int(o.retail_product_id),
            quantity=int(o.quantity or 1),
            store_pickup=pickup,
            spu_title=None,
            spec_label=None,
            product_title=str(o.product_title or ""),
            category_id=None,
        )

    product_ids = list(buckets.keys())
    sku_codes: dict[int, str | None] = {}
    sort_order: dict[int, int] = {}
    if product_ids:
        for p in db.scalars(
            select(StoreRetailProduct).where(
                StoreRetailProduct.store_id == sid,
                StoreRetailProduct.id.in_(product_ids),
            ),
        ).all():
            code = (p.sku_code or "").strip() or None
            sku_codes[int(p.id)] = code
            sort_order[int(p.id)] = int(p.sort_order or 0)

    items: list[RetailPickSummarySkuOut] = []
    grand_total = 0
    for pid, bucket in buckets.items():
        spu_t = bucket.spu_title
        spec = bucket.spec_label
        if not spu_t and bucket.product_title:
            display = bucket.product_title
        else:
            display = retail_sku_display_title(
                spu_title=spu_t or bucket.product_title or "商品",
                spec_label=spec,
            )
        grand_total += bucket.total_boxes
        items.append(
            RetailPickSummarySkuOut(
                retail_product_id=pid,
                display_title=display,
                spu_title=spu_t,
                spec_label=spec,
                sku_code=sku_codes.get(pid),
                category_id=bucket.category_id,
                total_boxes=bucket.total_boxes,
                order_count=len(bucket.order_ids),
                pickup_boxes=bucket.pickup_boxes,
                delivery_boxes=bucket.delivery_boxes,
            )
        )

    items.sort(
        key=lambda row: (-row.total_boxes, sort_order.get(row.retail_product_id, 0), row.display_title),
    )

    return RetailPickSummaryOut(
        scope_label=_SCOPE_LABEL,
        order_count=order_count,
        sku_count=len(items),
        grand_total_boxes=grand_total,
        items=items,
    )