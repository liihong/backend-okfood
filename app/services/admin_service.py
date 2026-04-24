from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import and_, case, exists, func, literal, not_, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.security import verify_password
from app.core.timeutil import today_shanghai, tomorrow_shanghai
from app.models.admin_user import AdminUser
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, PlanType
from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.product_category import ProductCategory
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.schemas.admin import (
    CategoryAdminOut,
    CategoryCreateIn,
    DashboardMealSummaryOut,
    DishAdminOut,
    DishUpsertIn,
    MemberAdminOut,
    MemberListStatsOut,
    MenuScheduleAssignIn,
    RechargeIn,
    SettingsIn,
    WeeklySlotAssignIn,
    MenuDayTotalStockIn,
)
from app.services.member_address_service import (
    default_address_pick_subquery,
    delivery_region_name_map,
    routing_area_label,
)
from app.services.member_service import (
    _monday_of_week,
    effective_daily_meal_units,
    sql_effective_daily_meal_units_column,
)


def _dish_price_yuan_str(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(v, "f")


def _member_on_leave_today(m: Member, today: date) -> bool:
    if m.leave_range_start and m.leave_range_end:
        return m.leave_range_start <= today <= m.leave_range_end
    return False


def _escape_like_fragment(s: str) -> str:
    """避免用户输入 % / _ 放大 LIKE 匹配范围。"""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _apply_member_list_filters(
    stmt,
    *,
    q_phone: str | None,
    validity: str | None,
    inactive_only: bool = False,
    delivery_region_id: int | None = None,
    unassigned_region: bool = False,
):
    if q_phone:
        q = q_phone.strip()
        if q:
            esc = _escape_like_fragment(q)
            # 与列表页搜索框「姓名、电话、片区地址」提示一致：默认地址详细行
            dap = default_address_pick_subquery()
            ma = aliased(MemberAddress)
            addr_match = exists(
                select(1)
                .select_from(dap)
                .join(ma, ma.id == dap.c.addr_id)
                .where(dap.c.mid == Member.id)
                .where(ma.detail_address.like(f"%{esc}%", escape="\\"))
            )
            stmt = stmt.where(
                or_(
                    Member.phone.like(f"{esc}%", escape="\\"),
                    Member.name.like(f"%{esc}%", escape="\\"),
                    Member.wechat_name.like(f"%{esc}%", escape="\\"),
                    addr_match,
                )
            )
    if validity == "active":
        stmt = stmt.where(Member.balance > 0)
    elif validity == "expired":
        stmt = stmt.where(Member.balance == 0)
    if inactive_only:
        stmt = stmt.where(Member.is_active.is_(False))
    if unassigned_region:
        dap = default_address_pick_subquery()
        ma = aliased(MemberAddress)
        has_no_default = ~exists(select(1).select_from(dap).where(dap.c.mid == Member.id))
        has_null_region = exists(
            select(1)
            .select_from(dap)
            .join(ma, ma.id == dap.c.addr_id)
            .where(dap.c.mid == Member.id)
            .where(ma.delivery_region_id.is_(None))
        )
        stmt = stmt.where(or_(has_no_default, has_null_region))
    elif delivery_region_id is not None:
        dap = default_address_pick_subquery()
        ma = aliased(MemberAddress)
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(dap)
                .join(ma, ma.id == dap.c.addr_id)
                .where(dap.c.mid == Member.id)
                .where(ma.delivery_region_id == delivery_region_id)
            )
        )
    return stmt


def admin_login_user(db: Session, username: str, password: str) -> AdminUser:
    u = db.execute(select(AdminUser).where(AdminUser.username == username)).scalar_one_or_none()
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return u


def member_list_overview_counts(db: Session) -> MemberListStatsOut:
    """全库会员数：与列表 `validity=active|expired` 口径一致（仅按 balance，不受搜索/片区筛选影响）。"""
    row = db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(case((Member.balance > 0, 1), else_=0)), 0).label("active"),
            func.coalesce(func.sum(case((Member.balance == 0, 1), else_=0)), 0).label("expired"),
        ).select_from(Member)
    ).one()
    return MemberListStatsOut(
        total=int(row.total or 0),
        active=int(row.active or 0),
        expired=int(row.expired or 0),
    )


def list_members_paged(
    db: Session,
    *,
    q_phone: str | None,
    page: int,
    page_size: int,
    validity: str | None = None,
    inactive_only: bool = False,
    delivery_region_id: int | None = None,
    unassigned_region: bool = False,
) -> tuple[list[MemberAdminOut], int]:
    # 每人至多一条「默认地址」：避免多条 is_default=1 时 JOIN 放大行数、拖慢 ORDER BY + LIMIT
    default_addr_pick = default_address_pick_subquery()

    # 单次往返：总计数子查询 + 分页 id 子查询 LEFT JOIN，避免 COUNT 与列表各查一次（高延迟库上可省一整轮 RTT）
    count_sq = _apply_member_list_filters(
        select(func.count().label("total")).select_from(Member),
        q_phone=q_phone,
        validity=validity,
        inactive_only=inactive_only,
        delivery_region_id=delivery_region_id,
        unassigned_region=unassigned_region,
    ).subquery("cnt")
    page_sq = _apply_member_list_filters(
        select(Member.id.label("pid")).select_from(Member),
        q_phone=q_phone,
        validity=validity,
        inactive_only=inactive_only,
        delivery_region_id=delivery_region_id,
        unassigned_region=unassigned_region,
    )
    page_sq = (
        page_sq.order_by(Member.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .subquery("page")
    )
    list_stmt = (
        select(count_sq.c.total, Member, MemberAddress)
        .select_from(count_sq)
        .outerjoin(page_sq, true())
        .outerjoin(Member, Member.id == page_sq.c.pid)
        .outerjoin(default_addr_pick, default_addr_pick.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == default_addr_pick.c.addr_id)
    )
    biz_today = today_shanghai()
    out: list[MemberAdminOut] = []
    rows = db.execute(list_stmt).all()
    if not rows:
        return [], 0
    total = int(rows[0][0] or 0)
    region_ids: set[int] = set()
    for _total_col, m, addr in rows:
        if m is None:
            continue
        if addr and addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)
    for _total_col, m, addr in rows:
        if m is None:
            continue
        if addr:
            detail = (addr.detail_address or "").strip()
            ar = routing_area_label(addr, id_to_name)
            ad_line = f"{ar} {detail}".strip() if detail else ar
        else:
            detail = ""
            ad_line = "（未设置默认配送地址）"
            ar = UNASSIGNED_DELIVERY_AREA
        out.append(
            MemberAdminOut(
                id=m.id,
                phone=m.phone,
                name=m.name,
                wechat_name=m.wechat_name,
                delivery_start_date=m.delivery_start_date,
                store_pickup=bool(m.store_pickup),
                address=ad_line,
                detail_address=detail,
                avatar_url=m.avatar_url,
                area=ar,
                remarks=m.remarks,
                balance=m.balance,
                daily_meal_units=effective_daily_meal_units(m),
                meal_quota_total=m.meal_quota_total,
                plan_type=m.plan_type,
                is_active=m.is_active,
                is_leaved_tomorrow=m.is_leaved_tomorrow,
                leave_range_start=m.leave_range_start,
                leave_range_end=m.leave_range_end,
                is_on_leave_today=_member_on_leave_today(m, biz_today),
                created_at=m.created_at.isoformat() if m.created_at else "",
            )
        )
    return out, total


def apply_member_recharge_delta(
    db: Session,
    body: RechargeIn,
    *,
    operator: str,
    log_detail: str | None = None,
) -> Member:
    """调整会员剩余次数并写入 balance_logs；由调用方 commit。"""
    if body.amount == 0:
        raise HTTPException(status_code=400, detail="调整幅度不能为 0")
    m = db.execute(select(Member).where(Member.phone == body.phone)).scalar_one_or_none()
    if not m:
        raise HTTPException(status_code=404, detail="用户不存在")
    m.balance += body.amount
    if m.balance < 0:
        raise HTTPException(status_code=400, detail="次数不足，无法扣减到负数")
    if body.plan_type is not None:
        m.plan_type = body.plan_type.value
    # 周卡/月卡正向入账：剩余次数与累计总次数同步增加（续卡叠加）
    if (
        body.amount > 0
        and body.plan_type is not None
        and body.plan_type in (PlanType.WEEK, PlanType.MONTH)
    ):
        m.meal_quota_total = int(m.meal_quota_total or 0) + body.amount
    detail = (log_detail or "").strip() or None
    if detail and len(detail) > 500:
        detail = detail[:500]
    db.add(
        BalanceLog(
            member_id=m.id,
            change=body.amount,
            reason=BalanceReason.RECHARGE.value if body.amount > 0 else BalanceReason.REFUND.value,
            operator=operator,
            detail=detail,
        )
    )
    return m


def upsert_dish(db: Session, body: DishUpsertIn) -> DishAdminOut:
    if body.category_id is not None and db.get(ProductCategory, body.category_id) is None:
        raise HTTPException(status_code=400, detail="分类不存在")
    if body.id is not None:
        row = db.get(MenuDish, body.id)
        if not row:
            raise HTTPException(status_code=404, detail="菜品不存在")
        row.name = body.name
        row.description = body.description
        row.image_url = body.image_url
        row.is_enabled = body.is_enabled
        row.category_id = body.category_id
        row.single_order_price_yuan = body.single_order_price_yuan
    else:
        row = MenuDish(
            name=body.name,
            description=body.description,
            image_url=body.image_url,
            is_enabled=body.is_enabled,
            category_id=body.category_id,
            single_order_price_yuan=body.single_order_price_yuan,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return DishAdminOut(
        id=row.id,
        name=row.name,
        description=row.description,
        image_url=row.image_url,
        is_enabled=row.is_enabled,
        category_id=row.category_id,
        single_order_price_yuan=_dish_price_yuan_str(row.single_order_price_yuan),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def list_dishes_admin(db: Session, *, enabled_only: bool, q: str | None = None) -> list[DishAdminOut]:
    stmt = select(MenuDish).order_by(MenuDish.id.desc())
    if enabled_only:
        stmt = stmt.where(MenuDish.is_enabled.is_(True))
    if q and q.strip():
        stmt = stmt.where(MenuDish.name.contains(q.strip()))
    rows = db.scalars(stmt).all()
    return [
        DishAdminOut(
            id=r.id,
            name=r.name,
            description=r.description,
            image_url=r.image_url,
            is_enabled=r.is_enabled,
            category_id=r.category_id,
            single_order_price_yuan=_dish_price_yuan_str(r.single_order_price_yuan),
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


def delete_dish(db: Session, dish_id: int) -> None:
    row = db.get(MenuDish, dish_id)
    if not row:
        raise HTTPException(status_code=404, detail="菜品不存在")
    try:
        db.delete(row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="该菜品仍被周菜单槽位或按日排期引用，请先解除关联后再删除",
        )


def assign_menu_schedule(db: Session, body: MenuScheduleAssignIn) -> None:
    dish = db.get(MenuDish, body.dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    existing = db.scalar(select(MenuSchedule).where(MenuSchedule.menu_date == body.date))
    try:
        if existing:
            existing.dish_id = body.dish_id
        else:
            db.add(MenuSchedule(menu_date=body.date, dish_id=body.dish_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="该菜品在本自然月已排在其他日期（一个月不重样），请换菜或调整日期",
        )


def list_categories_admin(db: Session) -> list[CategoryAdminOut]:
    rows = db.scalars(select(ProductCategory).order_by(ProductCategory.sort_order, ProductCategory.id)).all()
    return [
        CategoryAdminOut(
            id=r.id,
            code=r.code,
            name=r.name,
            sort_order=r.sort_order,
            is_active=r.is_active,
        )
        for r in rows
    ]


def create_category_admin(db: Session, body: CategoryCreateIn) -> CategoryAdminOut:
    row = ProductCategory(code=body.code, name=body.name, sort_order=body.sort_order, is_active=True)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="分类编码已存在")
    db.refresh(row)
    return CategoryAdminOut(
        id=row.id,
        code=row.code,
        name=row.name,
        sort_order=row.sort_order,
        is_active=row.is_active,
    )


def _weekly_slots_payload(db: Session, anchor: date) -> list[dict]:
    rows = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(WeeklyMenuSlot.week_start == anchor)
        .order_by(WeeklyMenuSlot.slot)
    ).all()
    from app.services.menu_day_stock_service import weekly_slot_stock_extras

    raw: list[dict] = [
        {
            "slot": w.slot,
            "dish_id": d.id,
            "name": d.name,
            "is_enabled": d.is_enabled,
            "category_id": d.category_id,
            "single_order_price_yuan": _dish_price_yuan_str(d.single_order_price_yuan),
            "total_stock": int(w.total_stock) if w.total_stock is not None else None,
        }
        for w, d in rows
    ]
    return weekly_slot_stock_extras(db, anchor, raw)


def admin_weekly_menu_preview(db: Session, week_start: date | None) -> dict:
    """不传 week_start 时返回本周 + 下周槽位，便于预告维护。"""
    t = today_shanghai()
    this_a = _monday_of_week(t)
    next_a = this_a + timedelta(days=7)
    if week_start is not None:
        anchor = _monday_of_week(week_start)
        return {
            "week_start": anchor.isoformat(),
            "slots": _weekly_slots_payload(db, anchor),
        }
    return {
        "this_week_start": this_a.isoformat(),
        "next_week_start": next_a.isoformat(),
        "this_week": _weekly_slots_payload(db, this_a),
        "next_week": _weekly_slots_payload(db, next_a),
    }


def assign_weekly_menu_slot(db: Session, body: WeeklySlotAssignIn) -> None:
    anchor = _monday_of_week(body.week_start)
    if body.dish_id is None:
        row = db.scalar(
            select(WeeklyMenuSlot).where(
                WeeklyMenuSlot.week_start == anchor,
                WeeklyMenuSlot.slot == body.slot,
            )
        )
        if row:
            db.delete(row)
            db.commit()
        return
    if db.get(MenuDish, body.dish_id) is None:
        raise HTTPException(status_code=404, detail="菜品不存在")
    row = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == body.slot,
        )
    )
    try:
        if row:
            if int(row.dish_id) != int(body.dish_id):
                row.total_stock = None
            row.dish_id = body.dish_id
        else:
            db.add(WeeklyMenuSlot(week_start=anchor, slot=body.slot, dish_id=body.dish_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="该菜品在本自然月已排在其他日期（周槽位与按日排期共用「一月不重样」规则），请换菜或调整槽位",
        )


def set_weekly_slot_menu_total_stock(db: Session, body: MenuDayTotalStockIn) -> None:
    from app.services.menu_day_stock_service import set_weekly_slot_total_stock

    set_weekly_slot_total_stock(
        db, _monday_of_week(body.week_start), body.slot, body.total_stock
    )


def update_settings(db: Session, body: SettingsIn) -> None:
    from app.services.store_config_service import ensure_app_settings_row

    row = ensure_app_settings_row(db)
    row.leave_deadline_time = body.leave_deadline_time
    db.commit()


def dashboard_meal_summary(db: Session) -> DashboardMealSummaryOut:
    """
    今日/明日请假人数与备餐份数。
    口径与 `list_today_tasks` 一致：is_active 且 balance>=当日应付份数 且已达起送日；缺席含区间请假与「仅明天请假」（仅对配送日为明天生效）。
    周日与法定节假日无订阅备餐，对应日期的请假人数与份数均记 0。
    """
    anchor_today = today_shanghai()
    tomorrow_as_date = tomorrow_shanghai()
    units_sql = sql_effective_daily_meal_units_column()

    def counts_for_delivery_day(d: date) -> tuple[int, int]:
        if not is_subscription_delivery_day(d):
            return 0, 0
        in_leave_range = and_(
            Member.leave_range_start.is_not(None),
            Member.leave_range_end.is_not(None),
            Member.leave_range_start <= d,
            Member.leave_range_end >= d,
        )
        tomorrow_leave_hit = and_(
            Member.is_leaved_tomorrow.is_(True),
            literal(d) == literal(tomorrow_as_date),
        )
        absent = or_(in_leave_range, tomorrow_leave_hit)
        started = or_(
            Member.delivery_start_date.is_(None),
            Member.delivery_start_date <= d,
        )
        base = and_(Member.is_active.is_(True), Member.balance >= units_sql, started)
        leave_n = int(db.scalar(select(func.count()).select_from(Member).where(base, absent)) or 0)
        prep_n = int(
            db.scalar(
                select(func.coalesce(func.sum(units_sql), 0)).select_from(Member).where(base, not_(absent))
            )
            or 0
        )
        return leave_n, prep_n

    tl, tp = counts_for_delivery_day(anchor_today)
    nl, np = counts_for_delivery_day(tomorrow_as_date)
    return DashboardMealSummaryOut(
        today_leave_members=tl,
        today_meals_to_prepare=tp,
        tomorrow_leave_members=nl,
        tomorrow_meals_to_prepare=np,
    )
