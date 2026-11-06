"""人工改结存：期初、入库、每周校对。

自动领用不走这里。结存和流水在同一个事务里写，避免只有一边成功。
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.packaging_sku import PackagingSku
from app.models.packaging_stock import PackagingStock
from app.models.packaging_stock_txn import PackagingStockTxn
from app.services.packaging.constants import (
    TXN_LABELS,
    TXN_OPENING,
    TXN_PURCHASE_IN,
    TXN_STOCKTAKE,
)
from app.services.packaging.sku_service import _require_sku


def list_stocks(db: Session, *, store_id: int) -> list[dict]:
    skus = db.scalars(
        select(PackagingSku)
        .where(PackagingSku.store_id == int(store_id))
        .order_by(PackagingSku.id.asc())
    ).all()
    stocks = {
        int(row.sku_id): row
        for row in db.scalars(select(PackagingStock).where(PackagingStock.store_id == int(store_id))).all()
    }
    initialized = _initialized_sku_ids(db, store_id=store_id)
    result = []
    for sku in skus:
        stock = stocks.get(int(sku.id))
        qty = int(stock.qty) if stock is not None else 0
        ready = int(sku.id) in initialized
        result.append(
            {
                "sku_id": int(sku.id),
                "name": sku.name,
                "usage_note": sku.usage_note or "",
                "supplier_name": sku.supplier_name or "",
                "unit": sku.unit,
                "safety_stock": sku.safety_stock,
                "is_meal_bag": sku.bag_flag == 1,
                "is_active": bool(sku.is_active),
                "qty": qty,
                "initialized": ready,
                "low": _is_low(qty, sku.safety_stock, ready),
            }
        )
    return result


def purchase_in(
    db: Session,
    *,
    store_id: int,
    sku_id: int,
    qty: int,
    operator: str,
    remark: str | None,
    biz_date: date | None = None,
) -> dict:
    if int(qty) < 1:
        raise HTTPException(status_code=400, detail="入库数量至少为 1")
    sku = _require_sku(db, sku_id, store_id=store_id)
    if not sku.is_active:
        raise HTTPException(status_code=400, detail="耗材已停用，不能入库")
    stock = _lock_stock(db, sku)
    stock.qty = int(stock.qty) + int(qty)
    db.add(
        PackagingStockTxn(
            store_id=int(store_id),
            sku_id=int(sku.id),
            txn_type=TXN_PURCHASE_IN,
            qty_delta=int(qty),
            qty_after=int(stock.qty),
            biz_date=biz_date or today_shanghai(),
            meal_period=None,
            operator=(operator or "")[:100],
            remark=_remark(remark),
        )
    )
    db.commit()
    db.refresh(stock)
    return {"sku_id": int(sku.id), "qty": int(stock.qty)}


def stocktake(
    db: Session,
    *,
    store_id: int,
    lines: list[tuple[int, int]],
    operator: str,
    biz_date: date | None = None,
) -> list[dict]:
    """按实盘改结存。差额写成盘点流水；第一次校对同时完成期初。"""
    if not lines:
        raise HTTPException(status_code=400, detail="请填写实盘数量")
    day = biz_date or today_shanghai()
    changed: list[dict] = []
    seen: set[int] = set()
    for sku_id, actual in lines:
        if int(sku_id) in seen:
            raise HTTPException(status_code=400, detail="同一耗材不能校对两次")
        seen.add(int(sku_id))
        if int(actual) < 0:
            raise HTTPException(status_code=400, detail="实盘数量不能为负")
        sku = _require_sku(db, sku_id, store_id=store_id)
        stock = _lock_stock(db, sku)
        delta = int(actual) - int(stock.qty)
        initialized = _sku_initialized(db, sku.id)
        if delta == 0 and initialized:
            changed.append({"sku_id": int(sku.id), "qty": int(stock.qty), "delta": 0})
            continue
        txn_type = TXN_STOCKTAKE if initialized else TXN_OPENING
        stock.qty = int(actual)
        db.add(
            PackagingStockTxn(
                store_id=int(store_id),
                sku_id=int(sku.id),
                txn_type=txn_type,
                qty_delta=delta,
                qty_after=int(actual),
                biz_date=day,
                meal_period=None,
                operator=(operator or "")[:100],
                remark="每周校对" if txn_type == TXN_STOCKTAKE else "期初盘点",
            )
        )
        changed.append({"sku_id": int(sku.id), "qty": int(actual), "delta": delta})
    db.commit()
    return changed


def list_txns(
    db: Session,
    *,
    store_id: int,
    sku_id: int | None,
    biz_date_from: date | None,
    biz_date_to: date | None,
    limit: int = 200,
) -> list[dict]:
    query = select(PackagingStockTxn).where(PackagingStockTxn.store_id == int(store_id))
    if sku_id is not None:
        query = query.where(PackagingStockTxn.sku_id == int(sku_id))
    if biz_date_from is not None:
        query = query.where(PackagingStockTxn.biz_date >= biz_date_from)
    if biz_date_to is not None:
        query = query.where(PackagingStockTxn.biz_date <= biz_date_to)
    rows = db.scalars(query.order_by(PackagingStockTxn.id.desc()).limit(min(max(int(limit), 1), 500))).all()
    names = {}
    if rows:
        sku_rows = db.scalars(
            select(PackagingSku).where(PackagingSku.id.in_({int(row.sku_id) for row in rows}))
        ).all()
        names = {int(row.id): row.name for row in sku_rows}
    return [
        {
            "id": int(row.id),
            "sku_id": int(row.sku_id),
            "sku_name": names.get(int(row.sku_id), ""),
            "txn_type": row.txn_type,
            "txn_label": TXN_LABELS.get(row.txn_type, row.txn_type),
            "qty_delta": int(row.qty_delta),
            "qty_after": int(row.qty_after),
            "biz_date": row.biz_date.isoformat(),
            "meal_period": row.meal_period or "",
            "operator": row.operator,
            "remark": row.remark or "",
            "created_at": row.created_at.isoformat(sep=" ", timespec="minutes") if row.created_at else "",
        }
        for row in rows
    ]


def _lock_stock(db: Session, sku: PackagingSku) -> PackagingStock:
    stock = db.get(PackagingStock, int(sku.id))
    if stock is None:
        stock = PackagingStock(sku_id=int(sku.id), store_id=int(sku.store_id), qty=0)
        db.add(stock)
        db.flush()
    return stock


def _initialized_sku_ids(db: Session, *, store_id: int) -> set[int]:
    rows = db.scalars(
        select(PackagingStockTxn.sku_id).where(PackagingStockTxn.store_id == int(store_id)).distinct()
    ).all()
    return {int(sku_id) for sku_id in rows}


def _sku_initialized(db: Session, sku_id: int) -> bool:
    found = db.scalar(
        select(PackagingStockTxn.id).where(PackagingStockTxn.sku_id == int(sku_id)).limit(1)
    )
    return found is not None


def _is_low(qty: int, safety_stock: int | None, initialized: bool) -> bool:
    """没做期初的不报警。没填最低库存时，只有已经欠货才提醒。"""
    if not initialized:
        return False
    if int(qty) < 0:
        return True
    if safety_stock is None:
        return False
    return int(qty) <= int(safety_stock)


def _remark(remark: str | None) -> str | None:
    if remark is None:
        return None
    cleaned = remark.strip()
    if not cleaned:
        return None
    return cleaned[:200]
