"""随餐饮饮品库。和零售果蔬汁分开，只给菜品配餐饮选用。"""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.menu_dish import MenuDish
from app.models.menu_drink import MenuDrink
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.schemas.menu_drink import DrinkAdminOut, DrinkUpsertIn


def _drink_out(row: MenuDrink) -> DrinkAdminOut:
    return DrinkAdminOut(
        id=int(row.id),
        name=row.name,
        description=row.description,
        image_url=row.image_url,
        is_enabled=bool(row.is_enabled),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def drink_name_map(db: Session, drink_ids: set[int]) -> dict[int, str]:
    """批量取饮品名。已删除的 id 不出现在结果里。"""
    if not drink_ids:
        return {}
    rows = db.scalars(select(MenuDrink).where(MenuDrink.id.in_(drink_ids))).all()
    return {int(row.id): row.name for row in rows}


def assert_store_drink(db: Session, *, drink_id: int | None, store_id: int) -> int | None:
    """配餐饮必须是本店饮品。空表示这一餐不配饮。停用的仍可保留在已选菜品上。"""
    if drink_id is None:
        return None
    row = db.get(MenuDrink, int(drink_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=400, detail="配餐饮不存在或不属于本店")
    return int(row.id)


def list_drinks_admin(db: Session, *, store_id: int, enabled_only: bool = False) -> list[DrinkAdminOut]:
    stmt = select(MenuDrink).where(MenuDrink.store_id == int(store_id)).order_by(MenuDrink.id.desc())
    if enabled_only:
        stmt = stmt.where(MenuDrink.is_enabled.is_(True))
    return [_drink_out(row) for row in db.scalars(stmt).all()]


def get_drink_admin(db: Session, drink_id: int, *, store_id: int) -> DrinkAdminOut:
    row = db.get(MenuDrink, int(drink_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="饮品不存在")
    return _drink_out(row)


def upsert_drink(db: Session, body: DrinkUpsertIn, *, store_id: int) -> DrinkAdminOut:
    sid = int(store_id)
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写饮品名称")
    if body.id is not None:
        row = db.get(MenuDrink, int(body.id))
        if row is None or int(row.store_id) != sid:
            raise HTTPException(status_code=404, detail="饮品不存在")
        row.name = name
        row.description = body.description
        row.image_url = body.image_url
        row.is_enabled = body.is_enabled
    else:
        row = MenuDrink(
            store_id=sid,
            name=name,
            description=body.description,
            image_url=body.image_url,
            is_enabled=body.is_enabled,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _drink_out(row)


def delete_drink(db: Session, drink_id: int, *, store_id: int) -> None:
    sid = int(store_id)
    row = db.get(MenuDrink, int(drink_id))
    if row is None or int(row.store_id) != sid:
        raise HTTPException(status_code=404, detail="饮品不存在")
    used_on_dish = db.scalar(
        select(func.count())
        .select_from(MenuDish)
        .where(MenuDish.store_id == sid, MenuDish.paired_drink_id == int(row.id))
    )
    used_on_slot = db.scalar(
        select(func.count())
        .select_from(WeeklyMenuSlot)
        .where(WeeklyMenuSlot.store_id == sid, WeeklyMenuSlot.paired_drink_id == int(row.id))
    )
    if used_on_dish or used_on_slot:
        raise HTTPException(status_code=400, detail="仍有本周菜单或菜品在用这款饮品，请先改掉再删除")
    db.delete(row)
    db.commit()
