"""采购资料的增删改查。

每条记录独立存在，不读取、不写入菜品、库存或供应商档案。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.purchase_note import PurchaseNote

CATEGORIES = {"ingredient", "consumable"}
RECORD_METHODS = {"link", "wechat", "phone", "other"}


def list_notes(
    db: Session,
    *,
    store_id: int,
    q: str | None = None,
    category: str | None = None,
    record_method: str | None = None,
) -> list[PurchaseNote]:
    if category:
        _require_category(category)
    if record_method:
        _require_method(record_method)
    stmt = select(PurchaseNote).where(PurchaseNote.store_id == int(store_id))
    if category:
        stmt = stmt.where(PurchaseNote.category == category)
    if record_method:
        stmt = stmt.where(PurchaseNote.record_method == record_method)
    keyword = (q or "").strip()
    if keyword:
        # 转义 LIKE 通配符，避免客服搜索「100%」时把别的记录也带出来。
        pattern = f"%{_escape_like(keyword)}%"
        stmt = stmt.where(
            or_(
                PurchaseNote.name.like(pattern, escape="\\"),
                PurchaseNote.contact_value.like(pattern, escape="\\"),
                PurchaseNote.platform.like(pattern, escape="\\"),
                PurchaseNote.supplier_label.like(pattern, escape="\\"),
                PurchaseNote.remark.like(pattern, escape="\\"),
            )
        )
    stmt = stmt.order_by(PurchaseNote.updated_at.desc(), PurchaseNote.id.desc())
    return list(db.scalars(stmt).all())


def create_note(
    db: Session,
    *,
    store_id: int,
    category: str,
    name: str,
    record_method: str,
    contact_value: str,
    platform: str | None,
    supplier_label: str | None,
    remark: str | None,
) -> PurchaseNote:
    cleaned_category = _require_category(category)
    cleaned_method = _require_method(record_method)
    cleaned_name = _require_text(name, "请填写名称")
    cleaned_contact = _require_contact(cleaned_method, contact_value)
    row = PurchaseNote(
        store_id=int(store_id),
        category=cleaned_category,
        name=cleaned_name,
        record_method=cleaned_method,
        contact_value=cleaned_contact,
        platform=_blank_to_none(platform),
        supplier_label=_blank_to_none(supplier_label),
        remark=_blank_to_none(remark),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def patch_note(
    db: Session,
    note_id: int,
    *,
    store_id: int,
    category: str | None = None,
    name: str | None = None,
    record_method: str | None = None,
    contact_value: str | None = None,
    platform: str | None = None,
    platform_set: bool = False,
    supplier_label: str | None = None,
    supplier_label_set: bool = False,
    remark: str | None = None,
    remark_set: bool = False,
) -> PurchaseNote:
    row = _require_note(db, note_id, store_id=store_id)
    if category is not None:
        row.category = _require_category(category)
    if name is not None:
        row.name = _require_text(name, "请填写名称")
    if record_method is not None:
        row.record_method = _require_method(record_method)
    if contact_value is not None:
        row.contact_value = contact_value.strip()
    # 方式和内容可能只改了其中一个，保存前按最终组合再验一次。
    row.contact_value = _require_contact(row.record_method, row.contact_value)
    if platform_set:
        row.platform = _blank_to_none(platform)
    if supplier_label_set:
        row.supplier_label = _blank_to_none(supplier_label)
    if remark_set:
        row.remark = _blank_to_none(remark)
    db.commit()
    db.refresh(row)
    return row


def delete_note(db: Session, note_id: int, *, store_id: int) -> None:
    row = _require_note(db, note_id, store_id=store_id)
    db.delete(row)
    db.commit()


def note_to_dict(row: PurchaseNote) -> dict:
    return {
        "id": int(row.id),
        "category": row.category,
        "name": row.name,
        "record_method": row.record_method,
        "contact_value": row.contact_value,
        "platform": row.platform or "",
        "supplier_label": row.supplier_label or "",
        "remark": row.remark or "",
    }


def _require_note(db: Session, note_id: int, *, store_id: int) -> PurchaseNote:
    row = db.get(PurchaseNote, int(note_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="采购资料不存在")
    return row


def _require_category(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned not in CATEGORIES:
        raise HTTPException(status_code=400, detail="分类只能是食材类或耗材类")
    return cleaned


def _require_method(value: str) -> str:
    cleaned = (value or "").strip()
    if cleaned not in RECORD_METHODS:
        raise HTTPException(status_code=400, detail="记录方式无效")
    return cleaned


def _require_text(value: str, message: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=message)
    return cleaned


def _require_contact(method: str, value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="请填写采购信息")
    if method == "link" and not cleaned.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="采购链接需要以 http:// 或 https:// 开头")
    return cleaned


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
