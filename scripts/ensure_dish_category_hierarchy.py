"""
菜品分类二级层级：补 parent_id 列并为各门店幂等写入标准分类树。

可重复执行。运行：
  python scripts/ensure_dish_category_hierarchy.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.session import engine
from app.models.product_category import ProductCategory
from app.models.store import Store

# (code, name, sort_order, parent_code or None)
CATEGORY_SEED: list[tuple[str, str, int, str | None]] = [
    ("weekly", "每周餐品", 0, None),
    ("meat", "肉类", 10, None),
    ("meat_chicken", "鸡肉", 11, "meat"),
    ("meat_fish", "鱼肉", 12, "meat"),
    ("meat_duck", "鸭肉", 13, "meat"),
    ("meat_beef", "牛肉", 14, "meat"),
    ("meat_seafood", "海鲜", 15, "meat"),
    ("dish_type", "菜品分类", 20, None),
    ("dish_rice_bowl", "米饭能量碗", 21, "dish_type"),
    ("dish_salad", "沙拉类", 22, "dish_type"),
    ("dish_noodle", "面类", 23, "dish_type"),
    ("dish_rice_noodle", "粉类", 24, "dish_type"),
]


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
            """
        ),
        {"t": table, "c": column},
    )
    return int(r.scalar() or 0) > 0


def _ensure_parent_id_column(conn) -> None:
    if _column_exists(conn, "product_category", "parent_id"):
        print("product_category.parent_id 已存在，跳过 DDL")
        return
    conn.execute(
        text(
            """
            ALTER TABLE `product_category`
              ADD COLUMN `parent_id` BIGINT UNSIGNED NULL COMMENT '上级分类，空为一级' AFTER `store_id`,
              ADD KEY `idx_product_category_parent` (`parent_id`),
              ADD CONSTRAINT `fk_product_category_parent`
                FOREIGN KEY (`parent_id`) REFERENCES `product_category` (`id`)
                ON DELETE RESTRICT ON UPDATE CASCADE
            """
        )
    )
    print("已添加 product_category.parent_id")


def _upsert_categories_for_store(db: Session, store_id: int) -> None:
    sid = int(store_id)
    by_code: dict[str, ProductCategory] = {}

    # 停用旧版扁平分类
    old_staple = db.scalar(
        select(ProductCategory).where(ProductCategory.store_id == sid, ProductCategory.code == "staple")
    )
    if old_staple is not None and old_staple.is_active:
        old_staple.is_active = False
        print(f"  门店 {sid}: 已停用旧分类 staple")

    for code, name, sort_order, parent_code in CATEGORY_SEED:
        row = db.scalar(
            select(ProductCategory).where(ProductCategory.store_id == sid, ProductCategory.code == code)
        )
        parent_id = None
        if parent_code:
            parent = by_code.get(parent_code)
            if parent is None:
                parent = db.scalar(
                    select(ProductCategory).where(
                        ProductCategory.store_id == sid, ProductCategory.code == parent_code
                    )
                )
            if parent is None:
                raise RuntimeError(f"门店 {sid} 缺少父分类 {parent_code}，无法创建 {code}")
            parent_id = int(parent.id)

        if row is None:
            row = ProductCategory(
                store_id=sid,
                parent_id=parent_id,
                code=code,
                name=name,
                sort_order=sort_order,
                is_active=True,
            )
            db.add(row)
            db.flush()
            print(f"  门店 {sid}: 新建 {code} ({name})")
        else:
            row.parent_id = parent_id
            row.name = name
            row.sort_order = sort_order
            if code != "staple":
                row.is_active = True
        by_code[code] = row


def main() -> None:
    with engine.begin() as conn:
        _ensure_parent_id_column(conn)

    with Session(engine) as db:
        store_ids = list(db.scalars(select(Store.id).order_by(Store.id)))
        if not store_ids:
            store_ids = [1]
            print("未找到 stores 记录，仅处理 store_id=1（若不存在将跳过）")
        for sid in store_ids:
            try:
                _upsert_categories_for_store(db, int(sid))
            except Exception as e:
                db.rollback()
                print(f"门店 {sid} 处理失败: {e}")
                raise
        db.commit()
        print("菜品分类层级初始化完成")


if __name__ == "__main__":
    main()
