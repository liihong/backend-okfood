"""采购资料：只是备忘，筛选和门店隔离生效，坏链接不能保存。"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.packaging_schema import ensure_packaging_schema
from app.models.purchase_note import PurchaseNote
from app.services.packaging import purchase_note_service

STORE_ID = 1


def test_note_columns_do_not_point_at_other_business_rows() -> None:
    columns = {column.name for column in PurchaseNote.__table__.columns}
    assert columns.isdisjoint({"dish_id", "sku_id", "supplier_id", "stock_id"})


def test_create_list_filter_and_same_name_twice(db) -> None:
    purchase_note_service.create_note(
        db,
        store_id=STORE_ID,
        category="ingredient",
        name="螺旋意面",
        record_method="link",
        contact_value="https://e.tb.cn/example-pasta",
        platform="淘宝",
        supplier_label="安卡拉食品",
        remark="100g 装",
    )
    purchase_note_service.create_note(
        db,
        store_id=STORE_ID,
        category="ingredient",
        name="螺旋意面",
        record_method="wechat",
        contact_value="okfood_supplier_01",
        platform="微信",
        supplier_label=None,
        remark=None,
    )
    purchase_note_service.create_note(
        db,
        store_id=STORE_ID,
        category="consumable",
        name="800 安全扣汤碗",
        record_method="link",
        contact_value="https://e.tb.cn/example-bowl",
        platform="淘宝",
        supplier_label="餐盒耗材店",
        remark=None,
    )

    all_rows = purchase_note_service.list_notes(db, store_id=STORE_ID)
    assert len(all_rows) == 3
    foods = purchase_note_service.list_notes(db, store_id=STORE_ID, category="ingredient")
    assert len(foods) == 2
    wechat = purchase_note_service.list_notes(db, store_id=STORE_ID, record_method="wechat")
    assert [row.contact_value for row in wechat] == ["okfood_supplier_01"]
    found = purchase_note_service.list_notes(db, store_id=STORE_ID, q="100%")
    assert found == []
    found = purchase_note_service.list_notes(db, store_id=STORE_ID, q="100g")
    assert len(found) == 1
    found = purchase_note_service.list_notes(db, store_id=STORE_ID, q="okfood_supplier_01")
    assert len(found) == 1


def test_link_must_have_scheme_and_other_store_is_hidden(db) -> None:
    with pytest.raises(HTTPException) as caught:
        purchase_note_service.create_note(
            db,
            store_id=STORE_ID,
            category="ingredient",
            name="太阳蛋",
            record_method="link",
            contact_value="e.tb.cn/example-eggs",
            platform=None,
            supplier_label=None,
            remark=None,
        )
    assert caught.value.status_code == 400

    row = purchase_note_service.create_note(
        db,
        store_id=STORE_ID,
        category="ingredient",
        name="太阳蛋",
        record_method="phone",
        contact_value="13800002468",
        platform="电话",
        supplier_label="餐饮用蛋供应",
        remark="24 连",
    )
    assert purchase_note_service.list_notes(db, store_id=2) == []
    with pytest.raises(HTTPException) as missing:
        purchase_note_service.delete_note(db, int(row.id), store_id=2)
    assert missing.value.status_code == 404

    updated = purchase_note_service.patch_note(
        db,
        int(row.id),
        store_id=STORE_ID,
        record_method="link",
        contact_value="https://e.tb.cn/example-eggs",
        supplier_label="",
        supplier_label_set=True,
    )
    assert updated.record_method == "link"
    assert updated.supplier_label is None
    purchase_note_service.delete_note(db, int(row.id), store_id=STORE_ID)
    assert purchase_note_service.list_notes(db, store_id=STORE_ID) == []


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    ensure_packaging_schema(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
