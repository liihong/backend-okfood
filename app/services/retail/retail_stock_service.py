"""商城零售：库存占用与已售统计。"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.models.store_retail_product import StoreRetailProduct

# 占用库存的订单：未取消且未退款
_COMMITTED_PAY_STATUSES = ("未支付", "已支付")


@dataclass(frozen=True)
class RetailProductStockSnapshot:
    """单个 SKU 的库存快照。"""

    product_id: int
    stock_quantity: int | None
    sold_count: int
    reserved_count: int

    @property
    def available(self) -> int | None:
        """剩余可售；None 表示不限库存。"""
        if self.stock_quantity is None:
            return None
        left = int(self.stock_quantity) - int(self.sold_count) - int(self.reserved_count)
        return max(0, left)


def _committed_qty_by_product(
    db: Session,
    product_ids: list[int],
    *,
    exclude_order_id: int | None = None,
) -> dict[int, tuple[int, int]]:
    """
    返回 product_id -> (paid_qty, unpaid_qty)。
    已售 = 已支付；占用 = 未支付且未取消。
    exclude_order_id：支付前复检时排除本单占用，避免把自身未支付量重复扣减。
    """
    if not product_ids:
        return {}
    filters = [
        StoreRetailOrderItem.retail_product_id.in_([int(x) for x in product_ids]),
        StoreRetailOrder.fulfillment_status != "cancelled",
        StoreRetailOrder.pay_status.in_(_COMMITTED_PAY_STATUSES),
    ]
    if exclude_order_id is not None:
        filters.append(StoreRetailOrder.id != int(exclude_order_id))
    rows = db.execute(
        select(
            StoreRetailOrderItem.retail_product_id,
            StoreRetailOrder.pay_status,
            func.coalesce(func.sum(StoreRetailOrderItem.quantity), 0),
        )
        .join(StoreRetailOrder, StoreRetailOrder.id == StoreRetailOrderItem.order_id)
        .where(*filters)
        .group_by(StoreRetailOrderItem.retail_product_id, StoreRetailOrder.pay_status)
    ).all()
    out: dict[int, tuple[int, int]] = {int(pid): (0, 0) for pid in product_ids}
    for pid, pay_status, qty in rows:
        paid, unpaid = out.get(int(pid), (0, 0))
        n = int(qty or 0)
        if str(pay_status or "").strip() == "已支付":
            paid += n
        else:
            unpaid += n
        out[int(pid)] = (paid, unpaid)
    return out


def get_retail_stock_snapshots(
    db: Session,
    product_ids: list[int],
    *,
    exclude_order_id: int | None = None,
) -> dict[int, RetailProductStockSnapshot]:
    """批量获取库存快照（含已售、未支付占用）。"""
    ids = [int(x) for x in product_ids if int(x) > 0]
    if not ids:
        return {}
    products = {
        int(p.id): p
        for p in db.scalars(select(StoreRetailProduct).where(StoreRetailProduct.id.in_(ids))).all()
    }
    committed = _committed_qty_by_product(db, ids, exclude_order_id=exclude_order_id)
    out: dict[int, RetailProductStockSnapshot] = {}
    for pid in ids:
        prod = products.get(pid)
        stock_q = int(prod.stock_quantity) if prod and prod.stock_quantity is not None else None
        paid, unpaid = committed.get(pid, (0, 0))
        out[pid] = RetailProductStockSnapshot(
            product_id=pid,
            stock_quantity=stock_q,
            sold_count=int(paid),
            reserved_count=int(unpaid),
        )
    return out


def assert_retail_stock_available(
    db: Session,
    *,
    product_id: int,
    need_qty: int,
    exclude_order_id: int | None = None,
) -> None:
    """
    校验库存是否足够（含未支付占用）。
    exclude_order_id：支付前复检时传入当前订单 id，排除本单未支付占用。
    """
    from fastapi import HTTPException

    snap = get_retail_stock_snapshots(
        db, [int(product_id)], exclude_order_id=exclude_order_id
    ).get(int(product_id))
    if snap is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    if snap.available is None:
        return
    avail = int(snap.available)
    if int(need_qty) > avail:
        from app.models.store_retail_spu import StoreRetailSpu
        from app.services.retail.retail_display import retail_sku_display_title

        prod = db.get(StoreRetailProduct, int(product_id))
        name = "商品"
        if prod:
            spu = db.get(StoreRetailSpu, int(prod.spu_id))
            if spu:
                name = retail_sku_display_title(spu_title=spu.title, spec_label=prod.spec_label)
        raise HTTPException(status_code=400, detail=f"「{name}」库存不足，剩余 {avail} 件")
