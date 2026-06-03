from datetime import date, datetime, timedelta
from decimal import Decimal
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import and_, case, delete, exists, func, literal, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, load_only

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.security import verify_password
from app.core.timeutil import beijing_now_naive, today_shanghai, tomorrow_shanghai
from app.models.admin_dashboard_biz_day_snapshot import AdminDashboardBizDaySnapshot
from app.models.admin_user import AdminUser
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, PlanType
from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_operation_log import MemberOperationLog
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.product_category import ProductCategory
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.utils.sql_like import escape_like_fragment
from app.schemas.admin import (
    CategoryAdminOut,
    CategoryCreateIn,
    DashboardDayPrepMetricsOut,
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
from app.services.courier_service import (
    count_expire_one_unit_members_for_business_day,
    count_members_first_scheduled_delivery_day,
)
from app.services.delivery_sheet_service import (
    DeliverySheetDayMetrics,
    _store_card_reorder_stats,
    _store_membership_counts,
    delivery_sheet_metrics_for_date,
    delivery_sheet_metrics_pending_sql_for_future_date,
    delivery_sheet_metrics_via_sql_for_unlocked_date,
    meal_units_totals_for_delivery_dates,
)
from app.services.member_address_service import (
    default_address_pick_subquery,
    delivery_region_name_map,
    full_address_line,
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


def _dish_spice_level_out(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip().lower()
    if s in ("none", "mild", "medium", "hot"):
        return s
    return None


def _member_on_leave_today(m: Member, today: date) -> bool:
    if m.leave_range_start and m.leave_range_end:
        if m.leave_range_start <= today <= m.leave_range_end:
            return True
    if m.tomorrow_leave_target_date is not None and m.is_leaved_tomorrow:
        return today <= m.tomorrow_leave_target_date
    return False


def _member_archive_scope():
    """会员档案库：仅周卡/月卡；次卡及未标注套餐不在库内展示。"""
    return Member.plan_type.in_((PlanType.WEEK.value, PlanType.MONTH.value))


def _member_refunded_scope():
    """已办理退卡退款。"""
    return Member.membership_refunded_at.isnot(None)


def _member_card_expired_scope():
    """周/月卡次数用尽：balance=0 且曾有起送日、累计总次数或仍标记为活跃；不含已退款。"""
    return and_(
        Member.balance == 0,
        Member.membership_refunded_at.is_(None),
        or_(
            Member.delivery_start_date.isnot(None),
            func.coalesce(Member.meal_quota_total, 0) > 0,
            Member.is_active.is_(True),
        ),
    )


def _apply_member_list_filters(
    stmt,
    *,
    q_phone: str | None,
    validity: str | None,
    inactive_only: bool = False,
    delivery_deferred_only: bool = False,
    delivery_region_id: int | None = None,
    unassigned_region: bool = False,
    plan_type: str | None = None,
    on_leave_only: bool = False,
    store_id: int | None = None,
):
    stmt = stmt.where(Member.deleted_at.is_(None)).where(_member_archive_scope())
    if store_id is not None:
        stmt = stmt.where(Member.store_id == int(store_id))
    if q_phone:
        q = q_phone.strip()
        if q:
            esc = escape_like_fragment(q)
            # 与列表页搜索框「姓名、电话、片区地址」提示一致：默认地址详细行
            dap = default_address_pick_subquery()
            ma = aliased(MemberAddress)
            addr_match = exists(
                select(1)
                .select_from(dap)
                .join(ma, ma.id == dap.c.addr_id)
                .where(dap.c.mid == Member.id)
                .where(
                    or_(
                        ma.map_location_text.like(f"%{esc}%", escape="\\"),
                        ma.door_detail.like(f"%{esc}%", escape="\\"),
                    )
                )
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
        stmt = stmt.where(_member_card_expired_scope())
    elif validity == "refunded":
        stmt = stmt.where(_member_refunded_scope())
    if plan_type:
        stmt = stmt.where(Member.plan_type == plan_type)
    if inactive_only:
        # 与前台「未开卡」一致：排除暂停配送与次数已用尽的已过期档案
        stmt = stmt.where(
            and_(
                Member.is_active.is_(False),
                Member.delivery_deferred.is_(False),
                ~_member_card_expired_scope(),
            ),
        )
    if delivery_deferred_only:
        stmt = stmt.where(
            and_(Member.is_active.is_(False), Member.delivery_deferred.is_(True)),
        )
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
    if on_leave_only:
        # 与 `_member_on_leave_today` / 列表「请假中」状态一致（上海当前业务日）
        biz_today = today_shanghai()
        in_leave_range = and_(
            Member.leave_range_start.isnot(None),
            Member.leave_range_end.isnot(None),
            Member.leave_range_start <= biz_today,
            Member.leave_range_end >= biz_today,
        )
        tomorrow_leave_active = and_(
            Member.is_leaved_tomorrow.is_(True),
            Member.tomorrow_leave_target_date.isnot(None),
            biz_today <= Member.tomorrow_leave_target_date,
        )
        stmt = stmt.where(or_(in_leave_range, tomorrow_leave_active))
    return stmt


def admin_login_user(db: Session, username: str, password: str) -> AdminUser:
    u = db.execute(select(AdminUser).where(AdminUser.username == username)).scalar_one_or_none()
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return u


def member_list_overview_counts(db: Session, *, store_id: int | None = None) -> MemberListStatsOut:
    """档案库户数：与列表 `_member_archive_scope` + validity 筛选口径一致。"""
    expired_scope = _member_card_expired_scope()
    refunded_scope = _member_refunded_scope()
    base = select(
        func.count().label("total"),
        func.coalesce(func.sum(case((Member.balance > 0, 1), else_=0)), 0).label("active"),
        func.coalesce(func.sum(case((expired_scope, 1), else_=0)), 0).label("expired"),
        func.coalesce(func.sum(case((refunded_scope, 1), else_=0)), 0).label("refunded"),
    ).select_from(Member).where(Member.deleted_at.is_(None)).where(_member_archive_scope())
    if store_id is not None:
        base = base.where(Member.store_id == int(store_id))
    row = db.execute(base).one()
    total = int(row.total or 0)
    refunded = int(row.refunded or 0)
    rate = (Decimal(refunded) * Decimal("100") / Decimal(total)).quantize(Decimal("0.01")) if total > 0 else Decimal("0")
    return MemberListStatsOut(
        total=total,
        active=int(row.active or 0),
        expired=int(row.expired or 0),
        refunded=refunded,
        refund_rate_percent=rate,
    )


def list_members_paged(
    db: Session,
    *,
    q_phone: str | None,
    page: int,
    page_size: int,
    validity: str | None = None,
    inactive_only: bool = False,
    delivery_deferred_only: bool = False,
    delivery_region_id: int | None = None,
    unassigned_region: bool = False,
    plan_type: str | None = None,
    on_leave_only: bool = False,
    store_id: int | None = None,
) -> tuple[list[MemberAdminOut], int]:
    # 每人至多一条「默认地址」：避免多条 is_default=1 时 JOIN 放大行数、拖慢 ORDER BY + LIMIT
    default_addr_pick = default_address_pick_subquery()

    # 单次往返：总计数子查询 + 分页 id 子查询 LEFT JOIN，避免 COUNT 与列表各查一次（高延迟库上可省一整轮 RTT）
    count_sq = _apply_member_list_filters(
        select(func.count().label("total")).select_from(Member),
        q_phone=q_phone,
        validity=validity,
        inactive_only=inactive_only,
        delivery_deferred_only=delivery_deferred_only,
        delivery_region_id=delivery_region_id,
        unassigned_region=unassigned_region,
        plan_type=plan_type,
        on_leave_only=on_leave_only,
        store_id=store_id,
    ).subquery("cnt")
    page_sq = _apply_member_list_filters(
        select(Member.id.label("pid")).select_from(Member),
        q_phone=q_phone,
        validity=validity,
        inactive_only=inactive_only,
        delivery_deferred_only=delivery_deferred_only,
        delivery_region_id=delivery_region_id,
        unassigned_region=unassigned_region,
        plan_type=plan_type,
        on_leave_only=on_leave_only,
        store_id=store_id,
    )
    page_sq = (
        # 用户操作时间：members.updated_at（小程序/管理端档案变更时刷新，微信仅同步 openid 不刷新）
        page_sq.order_by(func.coalesce(Member.updated_at, Member.created_at).desc())
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
            detail = full_address_line(addr.map_location_text, addr.door_detail)
            ar = routing_area_label(addr, id_to_name)
            ad_line = f"{ar} {detail}".strip() if detail else ar
        else:
            detail = ""
            ad_line = "（未设置默认配送地址）"
            ar = UNASSIGNED_DELIVERY_AREA
        dr_id = int(addr.delivery_region_id) if addr and addr.delivery_region_id is not None else None
        out.append(
            MemberAdminOut(
                id=m.id,
                phone=m.phone,
                name=m.name,
                wechat_name=m.wechat_name,
                delivery_start_date=m.delivery_start_date,
                store_pickup=bool(m.store_pickup),
                skip_subscription_saturday=bool(m.skip_subscription_saturday),
                address=ad_line,
                map_location_text=(addr.map_location_text or "").strip() if addr else "",
                door_detail=(addr.door_detail or "").strip() if addr else "",
                avatar_url=m.avatar_url,
                area=ar,
                delivery_region_id=dr_id,
                remarks=m.remarks,
                balance=m.balance,
                daily_meal_units=effective_daily_meal_units(m),
                meal_quota_total=m.meal_quota_total,
                plan_type=m.plan_type,
                is_active=m.is_active,
                delivery_deferred=bool(m.delivery_deferred),
                is_leaved_tomorrow=m.is_leaved_tomorrow,
                tomorrow_leave_target_date=m.tomorrow_leave_target_date,
                leave_range_start=m.leave_range_start,
                leave_range_end=m.leave_range_end,
                is_on_leave_today=_member_on_leave_today(m, biz_today),
                membership_refunded_at=(
                    m.membership_refunded_at.isoformat() if m.membership_refunded_at else None
                ),
                created_at=m.created_at.isoformat() if m.created_at else "",
                updated_at=m.updated_at.isoformat() if m.updated_at else "",
            )
        )
    return out, total


def apply_member_recharge_delta(
    db: Session,
    body: RechargeIn,
    *,
    operator: str,
    log_detail: str | None = None,
    member_id: int | None = None,
) -> Member:
    """调整会员剩余次数并写入 balance_logs；由调用方 commit。"""
    if body.amount == 0:
        raise HTTPException(status_code=400, detail="调整幅度不能为 0")
    if member_id is not None:
        m = db.get(Member, int(member_id))
        if not m or m.deleted_at is not None:
            raise HTTPException(status_code=404, detail="用户不存在")
        if (m.phone or "").strip() != (body.phone or "").strip():
            raise HTTPException(status_code=400, detail="手机号与会员档案不一致")
    else:
        m = db.execute(select(Member).where(Member.phone == body.phone, Member.deleted_at.is_(None))).scalar_one_or_none()
        if not m:
            raise HTTPException(status_code=404, detail="用户不存在")
    balance_before = int(m.balance)
    m.balance += body.amount
    if m.balance < 0:
        raise HTTPException(status_code=400, detail="次数不足，无法扣减到负数")
    from app.services.member_renew_subscribe_service import reset_renew_remind_on_recharge

    reset_renew_remind_on_recharge(m, balance_before=balance_before, balance_after=int(m.balance))
    if body.plan_type is not None:
        m.plan_type = body.plan_type.value
    # 周卡/月卡正向入账：剩余次数与累计总次数同步增加（续卡叠加）
    if body.amount > 0 and body.plan_type is not None:
        bump_q = body.plan_type in (PlanType.WEEK, PlanType.MONTH) or bool(body.bump_meal_quota_total)
        if bump_q:
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


def admin_delete_member(db: Session, member_id: int) -> dict[str, str]:
    """无关联业务流水时可物理删除；否则逻辑删除并释放手机号。"""
    m = db.get(Member, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="会员不存在")
    if m.deleted_at is not None:
        raise HTTPException(status_code=400, detail="该会员已删除")
    mid = int(member_id)
    n_bal = int(db.scalar(select(func.count()).select_from(BalanceLog).where(BalanceLog.member_id == mid)) or 0)
    n_del = int(db.scalar(select(func.count()).select_from(DeliveryLog).where(DeliveryLog.member_id == mid)) or 0)
    n_smo = int(
        db.scalar(select(func.count()).select_from(SingleMealOrder).where(SingleMealOrder.member_id == mid)) or 0
    )
    n_card = int(
        db.scalar(select(func.count()).select_from(MemberCardOrder).where(MemberCardOrder.member_id == mid)) or 0
    )
    can_hard = n_bal == 0 and n_del == 0 and n_smo == 0 and n_card == 0
    if can_hard:
        db.execute(delete(MemberOperationLog).where(MemberOperationLog.member_id == mid))
        db.delete(m)
        db.commit()
        return {"mode": "hard", "msg": "已物理删除（无余额流水、配送记录、单次点餐与开卡工单）"}
    m.deleted_at = beijing_now_naive()
    m.wx_mini_openid = None
    m.phone = ("z" + uuid.uuid4().hex[:18])[:20]
    db.commit()
    return {
        "mode": "soft",
        "msg": "已逻辑删除：余额/配送等业务记录仍关联保留以便追溯；手机号已释放，用户可重新注册",
    }


def _dish_admin_out_from_row(
    row: MenuDish,
    *,
    include_sop: bool = True,
    lite: bool = False,
) -> DishAdminOut:
    return DishAdminOut(
        id=row.id,
        name=row.name,
        description=None if lite else row.description,
        image_url=None if lite else row.image_url,
        is_enabled=row.is_enabled,
        category_id=row.category_id,
        single_order_price_yuan=_dish_price_yuan_str(row.single_order_price_yuan),
        spice_level=_dish_spice_level_out(row.spice_level),
        internal_view_sop=row.internal_view_sop if include_sop else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def get_dish_admin(db: Session, dish_id: int, *, store_id: int) -> DishAdminOut:
    sid = int(store_id)
    row = db.get(MenuDish, dish_id)
    if not row or int(row.store_id) != sid:
        raise HTTPException(status_code=404, detail="菜品不存在")
    return _dish_admin_out_from_row(row, include_sop=True)


def upsert_dish(db: Session, body: DishUpsertIn, *, store_id: int) -> DishAdminOut:
    sid = int(store_id)
    if body.category_id is not None:
        cat = db.get(ProductCategory, body.category_id)
        if cat is None or int(cat.store_id) != sid:
            raise HTTPException(status_code=400, detail="分类不存在")
    if body.id is not None:
        row = db.get(MenuDish, body.id)
        if not row:
            raise HTTPException(status_code=404, detail="菜品不存在")
        if int(row.store_id) != sid:
            raise HTTPException(status_code=404, detail="菜品不存在")
        row.name = body.name
        row.description = body.description
        row.image_url = body.image_url
        row.is_enabled = body.is_enabled
        row.category_id = body.category_id
        row.single_order_price_yuan = body.single_order_price_yuan
        row.spice_level = body.spice_level
        row.internal_view_sop = body.internal_view_sop
    else:
        row = MenuDish(
            store_id=sid,
            name=body.name,
            description=body.description,
            image_url=body.image_url,
            is_enabled=body.is_enabled,
            category_id=body.category_id,
            single_order_price_yuan=body.single_order_price_yuan,
            spice_level=body.spice_level,
            internal_view_sop=body.internal_view_sop,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _dish_admin_out_from_row(row, include_sop=True)


def list_dishes_admin(
    db: Session,
    *,
    enabled_only: bool,
    q: str | None = None,
    store_id: int,
    lite: bool = False,
) -> list[DishAdminOut]:
    sid = int(store_id)
    load_cols = [
        MenuDish.id,
        MenuDish.name,
        MenuDish.is_enabled,
        MenuDish.category_id,
        MenuDish.single_order_price_yuan,
        MenuDish.spice_level,
        MenuDish.created_at,
    ]
    if not lite:
        load_cols.extend([MenuDish.description, MenuDish.image_url])
    stmt = (
        select(MenuDish)
        .options(load_only(*load_cols))
        .where(MenuDish.store_id == sid)
        .order_by(MenuDish.id.desc())
    )
    if enabled_only:
        stmt = stmt.where(MenuDish.is_enabled.is_(True))
    if q and q.strip():
        stmt = stmt.where(MenuDish.name.contains(q.strip()))
    rows = db.scalars(stmt).all()
    return [_dish_admin_out_from_row(r, include_sop=False, lite=lite) for r in rows]


def delete_dish(db: Session, dish_id: int, *, store_id: int) -> None:
    sid = int(store_id)
    row = db.get(MenuDish, dish_id)
    if not row or int(row.store_id) != sid:
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


def assign_menu_schedule(db: Session, body: MenuScheduleAssignIn, *, store_id: int) -> None:
    sid = int(store_id)
    dish = db.get(MenuDish, body.dish_id)
    if not dish:
        raise HTTPException(status_code=404, detail="菜品不存在")
    if int(dish.store_id) != sid:
        raise HTTPException(status_code=404, detail="菜品不存在")
    existing = db.scalar(select(MenuSchedule).where(MenuSchedule.menu_date == body.date, MenuSchedule.store_id == sid))
    try:
        if existing:
            existing.dish_id = body.dish_id
        else:
            db.add(MenuSchedule(store_id=sid, menu_date=body.date, dish_id=body.dish_id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="保存排期失败：数据冲突（例如该日期已有其他记录）",
        )


def list_categories_admin(db: Session, *, store_id: int) -> list[CategoryAdminOut]:
    sid = int(store_id)
    rows = db.scalars(
        select(ProductCategory).where(ProductCategory.store_id == sid).order_by(ProductCategory.sort_order, ProductCategory.id)
    ).all()
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


def create_category_admin(db: Session, body: CategoryCreateIn, *, store_id: int) -> CategoryAdminOut:
    sid = int(store_id)
    row = ProductCategory(
        store_id=sid, code=body.code, name=body.name, sort_order=body.sort_order, is_active=True
    )
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


def _weekly_slots_raw(rows: list) -> list[dict]:
    return [
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


def _weekly_slots_payload(db: Session, anchor: date, store_id: int) -> list[dict]:
    sid = int(store_id)
    rows = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(WeeklyMenuSlot.week_start == anchor, WeeklyMenuSlot.store_id == sid)
        .order_by(WeeklyMenuSlot.slot)
    ).all()
    from app.services.menu_day_stock_service import weekly_slot_stock_extras

    return weekly_slot_stock_extras(db, anchor, _weekly_slots_raw(rows), store_id=sid)


def _weekly_dual_preview(db: Session, this_a: date, next_a: date, *, store_id: int) -> dict[str, list[dict]]:
    """本周+下周槽位：仅本周算应配送/单次余；下周只返回槽位与总份配置。"""
    sid = int(store_id)
    anchors = [this_a, next_a]
    this_dates = [this_a + timedelta(days=i) for i in range(7)]
    from app.services.menu_day_stock_service import (
        _paid_sums_for_dates_dishes,
        resolve_dishes_for_dates_batch,
        subscription_total_meals_by_dates,
        weekly_slot_stock_extras,
    )

    sub_by_date = subscription_total_meals_by_dates(db, this_dates, store_id=sid)
    scheduled_by_date = resolve_dishes_for_dates_batch(db, this_dates, store_id=sid)
    rows = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(WeeklyMenuSlot.store_id == sid, WeeklyMenuSlot.week_start.in_(anchors))
        .order_by(WeeklyMenuSlot.week_start, WeeklyMenuSlot.slot)
    ).all()
    by_anchor: dict[date, list] = {this_a: [], next_a: []}
    this_dish_ids: set[int] = set()
    for w, d in rows:
        by_anchor.setdefault(w.week_start, []).append((w, d))
        if w.week_start == this_a:
            this_dish_ids.add(int(d.id))
    paid = _paid_sums_for_dates_dishes(db, this_dates, this_dish_ids, store_id=sid)
    return {
        "this_week": weekly_slot_stock_extras(
            db,
            this_a,
            _weekly_slots_raw(by_anchor.get(this_a, [])),
            store_id=sid,
            sub_by_date=sub_by_date,
            scheduled_by_date=scheduled_by_date,
            paid=paid,
        ),
        "next_week": weekly_slot_stock_extras(
            db,
            next_a,
            _weekly_slots_raw(by_anchor.get(next_a, [])),
            store_id=sid,
            skip_subscription_stats=True,
        ),
    }


def admin_weekly_menu_preview(db: Session, week_start: date | None, *, store_id: int) -> dict:
    """不传 week_start 时返回本周 + 下周槽位，便于预告维护。"""
    t = today_shanghai()
    this_a = _monday_of_week(t)
    next_a = this_a + timedelta(days=7)
    if week_start is not None:
        anchor = _monday_of_week(week_start)
        return {
            "week_start": anchor.isoformat(),
            "slots": _weekly_slots_payload(db, anchor, store_id),
        }
    dual = _weekly_dual_preview(db, this_a, next_a, store_id=store_id)
    return {
        "this_week_start": this_a.isoformat(),
        "next_week_start": next_a.isoformat(),
        **dual,
    }


def assign_weekly_menu_slot(db: Session, body: WeeklySlotAssignIn, *, store_id: int) -> None:
    anchor = _monday_of_week(body.week_start)
    sid = int(store_id)
    if body.dish_id is None:
        row = db.scalar(
            select(WeeklyMenuSlot).where(
                WeeklyMenuSlot.store_id == sid,
                WeeklyMenuSlot.week_start == anchor,
                WeeklyMenuSlot.slot == body.slot,
            )
        )
        if row:
            db.delete(row)
            db.commit()
        return
    dish = db.get(MenuDish, body.dish_id)
    if dish is None or int(dish.store_id) != sid:
        raise HTTPException(status_code=404, detail="菜品不存在")
    row = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
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
            db.add(
                WeeklyMenuSlot(
                    store_id=sid,
                    week_start=anchor,
                    slot=body.slot,
                    dish_id=body.dish_id,
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="保存周菜单槽位失败：数据冲突（例如槽位或关联约束）",
        )


def set_weekly_slot_menu_total_stock(db: Session, body: MenuDayTotalStockIn, *, store_id: int) -> None:
    from app.services.menu_day_stock_service import set_weekly_slot_total_stock

    set_weekly_slot_total_stock(
        db,
        _monday_of_week(body.week_start),
        body.slot,
        body.total_stock,
        store_id=int(store_id),
    )


def update_settings(db: Session, body: SettingsIn, *, store_id: int) -> None:
    from app.models.store import Store

    st = db.get(Store, int(store_id))
    if not st:
        raise HTTPException(status_code=404, detail="门店不存在")
    st.leave_deadline_time = body.leave_deadline_time
    db.commit()


def count_leave_members_for_delivery_day(db: Session, d: date, *, store_id: int | None = None) -> int:
    from app.core.config import get_settings

    sid = int(store_id) if store_id is not None else int(get_settings().DEFAULT_STORE_ID)
    if not is_subscription_delivery_day(d):
        return 0
    tomorrow_as_date = tomorrow_shanghai()
    units_sql = sql_effective_daily_meal_units_column()
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= d,
        Member.leave_range_end >= d,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == d,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(d) == literal(tomorrow_as_date),
    )
    tomorrow_leave_hit = or_(target_hit, legacy_tomorrow)
    absent = or_(in_leave_range, tomorrow_leave_hit)
    started = or_(
        Member.delivery_start_date.is_(None),
        Member.delivery_start_date <= d,
    )
    base = and_(Member.is_active.is_(True), Member.balance >= units_sql, started)
    if d.weekday() == 5:
        base = and_(base, Member.skip_subscription_saturday.is_(False))
    active_only = Member.deleted_at.is_(None)
    store_scope = Member.store_id == sid
    return int(
        db.scalar(
            select(func.count()).select_from(Member).where(active_only, store_scope, base, absent)
        )
        or 0
    )


def count_paid_single_retail_portions_for_delivery_day(
    db: Session, delivery_date: date, *, store_id: int
) -> int:
    """锚定业务日已支付单次零售份数合计（与周菜单「单次零售」列同源）。"""
    m = _paid_single_retail_portions_by_dates(db, [delivery_date], store_id=store_id)
    return int(m.get(delivery_date, 0))


def _paid_single_retail_portions_by_dates(
    db: Session, dates: list[date], *, store_id: int
) -> dict[date, int]:
    """批量查询多日已支付单次零售份数，减少 dashboard 重复扫描 single_meal_orders。"""
    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}
    sid = int(store_id)
    rows = db.execute(
        select(
            SingleMealOrder.delivery_date,
            func.coalesce(func.sum(SingleMealOrder.quantity), 0),
        )
        .where(
            SingleMealOrder.delivery_date.in_(uniq),
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.store_id == sid,
        )
        .group_by(SingleMealOrder.delivery_date)
    ).all()
    out = {d: 0 for d in uniq}
    for d, qty in rows:
        if d is not None:
            out[d] = int(qty or 0)
    return out


def _dashboard_day_prep_metrics_out(m: DeliverySheetDayMetrics) -> DashboardDayPrepMetricsOut:
    return DashboardDayPrepMetricsOut(
        home_pending_meal_total=int(m.home_pending_meal_total),
        home_delivered_meal_total=int(m.home_delivered_meal_total),
        pickup_meal_total=int(m.pickup_meal_total),
        pickup_pending_meal_total=int(m.pickup_pending_meal_total),
        pickup_delivered_meal_total=int(m.pickup_delivered_meal_total),
        home_stop_count=int(m.home_stop_count),
    )


def _dashboard_meals_week_over_week_caption(*, meals: int, baseline_meals: int) -> str:
    """备餐份数相对「上周同日」baseline 的差值文案。"""
    delta = int(meals) - int(baseline_meals)
    if delta == 0:
        return "较上周持平"
    return f"较上周{delta:+d}"


def _dashboard_snapshot_meal_totals(
    db: Session,
    *,
    store_id: int,
    dates: list[date],
) -> dict[date, int]:
    """批量读取历史锚日归档中的「当日备餐份数」，避免同比基线重复跑大表。"""
    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}
    rows = db.scalars(
        select(AdminDashboardBizDaySnapshot).where(
            AdminDashboardBizDaySnapshot.store_id == int(store_id),
            AdminDashboardBizDaySnapshot.business_anchor_date.in_(uniq),
        )
    ).all()
    return {row.business_anchor_date: int(row.today_meals_to_prepare) for row in rows}


def _dashboard_cached_sheet_metrics(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    metrics_cache: dict[date, DeliverySheetDayMetrics],
) -> DeliverySheetDayMetrics:
    """同一 dashboard-summary 请求内，每个业务日最多算一次大表拆分指标。"""
    if delivery_date not in metrics_cache:
        cal_today = today_shanghai()
        if delivery_date > cal_today:
            metrics_cache[delivery_date] = delivery_sheet_metrics_pending_sql_for_future_date(
                db,
                delivery_date=delivery_date,
                store_id=store_id,
            )
        else:
            from app.services.delivery_day_lock_service import (
                is_delivery_day_sheet_frozen_after_sf_push,
            )

            if is_delivery_day_sheet_frozen_after_sf_push(
                db, store_id=store_id, delivery_date=delivery_date
            ):
                metrics_cache[delivery_date] = delivery_sheet_metrics_for_date(
                    db,
                    delivery_date=delivery_date,
                    store_id=store_id,
                    metrics_cache=metrics_cache,
                )
            else:
                metrics_cache[delivery_date] = delivery_sheet_metrics_via_sql_for_unlocked_date(
                    db,
                    delivery_date=delivery_date,
                    store_id=store_id,
                )
    return metrics_cache[delivery_date]


# 地图会员库/续卡率与锚定日无关，短 TTL 复用，避免换日时重复扫 member 表
_dashboard_membership_kw_cache: dict[int, tuple[float, dict[str, int]]] = {}
_DASHBOARD_MEMBERSHIP_KW_TTL_SEC = 90.0


def _dashboard_membership_kw(db: Session, *, store_id: int) -> dict[str, int]:
    sid = int(store_id)
    cached = _dashboard_membership_kw_cache.get(sid)
    if cached is not None:
        ts, payload = cached
        if time.time() - ts < _DASHBOARD_MEMBERSHIP_KW_TTL_SEC:
            return payload
    payload = {**_store_membership_counts(db, store_id=sid), **_store_card_reorder_stats(db, store_id=sid)}
    _dashboard_membership_kw_cache[sid] = (time.time(), payload)
    return payload


# 按门店 + 锚定日缓存概览结果（进程内，单 worker 有效）
_dashboard_anchor_summary_cache: dict[tuple[int, date], tuple[float, DashboardMealSummaryOut]] = {}
_DASHBOARD_ANCHOR_SUMMARY_TTL_TODAY_SEC = 90.0
_DASHBOARD_ANCHOR_SUMMARY_TTL_OTHER_SEC = 300.0


def invalidate_dashboard_live_summary_cache(store_id: int | None = None) -> None:
    """供餐日数据变更后可按需清缓存；store_id 为空则清空全部门店。"""
    if store_id is None:
        _dashboard_membership_kw_cache.clear()
        _dashboard_anchor_summary_cache.clear()
        return
    sid = int(store_id)
    _dashboard_membership_kw_cache.pop(sid, None)
    for key in list(_dashboard_anchor_summary_cache):
        if key[0] == sid:
            _dashboard_anchor_summary_cache.pop(key, None)


def dashboard_meal_summary(
    db: Session,
    *,
    business_anchor_date: date | None = None,
    force_recompute: bool = False,
    store_id: int | None = None,
) -> DashboardMealSummaryOut:
    """
    今日/明日请假人数与备餐份数。
    备餐份数与 ``build_delivery_sheet``（智能配送大表）各分组合计一致；周日与法定节假日为 0。
    锚定日早于当前上海日时：优先读 ``admin_dashboard_biz_day_snapshots``，无则按当前库计算并落库（之后不变），
    ``force_recompute=true`` 时管理员可强制按当前库重算并覆盖归档。
    """
    from app.core.config import get_settings

    sid = int(store_id) if store_id is not None else int(get_settings().DEFAULT_STORE_ID)
    anchor = business_anchor_date or today_shanghai()
    day_after = date.fromordinal(anchor.toordinal() + 1)
    cal_today = today_shanghai()

    if not force_recompute:
        cache_key = (sid, anchor)
        cached = _dashboard_anchor_summary_cache.get(cache_key)
        if cached is not None:
            ts, payload = cached
            ttl = (
                _DASHBOARD_ANCHOR_SUMMARY_TTL_TODAY_SEC
                if anchor == cal_today
                else _DASHBOARD_ANCHOR_SUMMARY_TTL_OTHER_SEC
            )
            if time.time() - ts < ttl:
                return payload

    wow_prev_anchor = date.fromordinal(anchor.toordinal() - 7)
    wow_prev_day_after = date.fromordinal(day_after.toordinal() - 7)
    mem_kw = _dashboard_membership_kw(db, store_id=sid)
    from app.services.menu_day_stock_service import weekly_menu_day_total_stock

    today_menu_day_total_stock = weekly_menu_day_total_stock(db, anchor, store_id=sid)
    tomorrow_menu_day_total_stock = weekly_menu_day_total_stock(db, day_after, store_id=sid)
    metrics_cache: dict[date, DeliverySheetDayMetrics] = {}
    snapshot_meal_totals = _dashboard_snapshot_meal_totals(
        db,
        store_id=sid,
        dates=[d for d in (wow_prev_anchor, wow_prev_day_after) if d < cal_today],
    )

    if anchor < cal_today and not force_recompute:
        row = db.get(
            AdminDashboardBizDaySnapshot,
            {"store_id": sid, "business_anchor_date": anchor},
        )
        if row is not None:
            # 快照已含锚日/次日备餐；环比文案仍按需重算两周前两日份数总和
            wow_only = meal_units_totals_for_delivery_dates(
                db,
                dates=[wow_prev_anchor, wow_prev_day_after],
                store_id=sid,
                metrics_cache=metrics_cache,
                snapshot_meal_totals=snapshot_meal_totals,
                sql_sum_only=True,
            )
            baseline_meals_anchor_week = wow_only[wow_prev_anchor]
            baseline_meals_day_after_week = wow_only[wow_prev_day_after]
            tp_snap = int(row.today_meals_to_prepare)
            np_snap = int(row.tomorrow_meals_to_prepare)
            t_first = count_members_first_scheduled_delivery_day(db, delivery_date=day_after, store_id=sid)
            today_wow_cap = _dashboard_meals_week_over_week_caption(
                meals=tp_snap, baseline_meals=baseline_meals_anchor_week
            )
            tomorrow_wow_cap = _dashboard_meals_week_over_week_caption(
                meals=np_snap, baseline_meals=baseline_meals_day_after_week
            )
            today_metrics = _dashboard_day_prep_metrics_out(
                _dashboard_cached_sheet_metrics(
                    db, delivery_date=anchor, store_id=sid, metrics_cache=metrics_cache
                )
            )
            tomorrow_metrics = _dashboard_day_prep_metrics_out(
                _dashboard_cached_sheet_metrics(
                    db, delivery_date=day_after, store_id=sid, metrics_cache=metrics_cache
                )
            )
            today_single_retail = _paid_single_retail_portions_by_dates(
                db, [anchor, day_after], store_id=sid
            )
            snap_out = DashboardMealSummaryOut(
                shanghai_today=cal_today,
                business_anchor_date=anchor,
                today_leave_members=int(row.today_leave_members),
                today_meals_to_prepare=tp_snap,
                tomorrow_leave_members=int(row.tomorrow_leave_members),
                tomorrow_meals_to_prepare=np_snap,
                today_expire_one_unit_members=int(row.today_expire_one_unit_members),
                today_single_retail_total_quantity=int(today_single_retail.get(anchor, 0)),
                tomorrow_single_retail_total_quantity=int(today_single_retail.get(day_after, 0)),
                **mem_kw,
                tomorrow_first_meal_new_members=t_first,
                today_meals_week_over_week_caption=today_wow_cap,
                tomorrow_meals_week_over_week_caption=tomorrow_wow_cap,
                today_menu_day_total_stock=today_menu_day_total_stock,
                tomorrow_menu_day_total_stock=tomorrow_menu_day_total_stock,
                today_prep_metrics=today_metrics,
                tomorrow_prep_metrics=tomorrow_metrics,
                from_snapshot=True,
                snapshot_recorded_at=row.recorded_at,
            )
            if not force_recompute:
                _dashboard_anchor_summary_cache[(sid, anchor)] = (time.time(), snap_out)
            return snap_out

    wow_bundle = meal_units_totals_for_delivery_dates(
        db,
        dates=[wow_prev_anchor, wow_prev_day_after],
        store_id=sid,
        metrics_cache=metrics_cache,
        snapshot_meal_totals=snapshot_meal_totals,
        sql_sum_only=True,
    )
    baseline_meals_anchor_week = wow_bundle[wow_prev_anchor]
    baseline_meals_day_after_week = wow_bundle[wow_prev_day_after]

    # 锚定日/次日：一次 delivery_sheet_metrics 同时产出 tp/np 与 prep 拆分，避免再跑 6 次 SQL SUM
    today_m = _dashboard_cached_sheet_metrics(
        db, delivery_date=anchor, store_id=sid, metrics_cache=metrics_cache
    )
    tomorrow_m = _dashboard_cached_sheet_metrics(
        db, delivery_date=day_after, store_id=sid, metrics_cache=metrics_cache
    )
    tp = int(today_m.meal_total)
    np = int(tomorrow_m.meal_total)
    today_metrics = _dashboard_day_prep_metrics_out(today_m)
    tomorrow_metrics = _dashboard_day_prep_metrics_out(tomorrow_m)

    tl = count_leave_members_for_delivery_day(db, anchor, store_id=sid)
    nl = count_leave_members_for_delivery_day(db, day_after, store_id=sid)
    te = count_expire_one_unit_members_for_business_day(db, delivery_date=anchor, store_id=sid)
    t_first = count_members_first_scheduled_delivery_day(db, delivery_date=day_after, store_id=sid)
    today_wow_cap = _dashboard_meals_week_over_week_caption(meals=tp, baseline_meals=baseline_meals_anchor_week)
    tomorrow_wow_cap = _dashboard_meals_week_over_week_caption(meals=np, baseline_meals=baseline_meals_day_after_week)
    single_retail_map = _paid_single_retail_portions_by_dates(db, [anchor, day_after], store_id=sid)

    out = DashboardMealSummaryOut(
        shanghai_today=cal_today,
        business_anchor_date=anchor,
        today_leave_members=tl,
        today_meals_to_prepare=tp,
        tomorrow_leave_members=nl,
        tomorrow_meals_to_prepare=np,
        today_expire_one_unit_members=te,
        today_single_retail_total_quantity=int(single_retail_map.get(anchor, 0)),
        tomorrow_single_retail_total_quantity=int(single_retail_map.get(day_after, 0)),
        **mem_kw,
        tomorrow_first_meal_new_members=t_first,
        today_meals_week_over_week_caption=today_wow_cap,
        tomorrow_meals_week_over_week_caption=tomorrow_wow_cap,
        today_menu_day_total_stock=today_menu_day_total_stock,
        tomorrow_menu_day_total_stock=tomorrow_menu_day_total_stock,
        today_prep_metrics=today_metrics,
        tomorrow_prep_metrics=tomorrow_metrics,
        from_snapshot=False,
        snapshot_recorded_at=None,
    )

    if anchor < cal_today:
        now = beijing_now_naive()
        row = db.get(
            AdminDashboardBizDaySnapshot,
            {"store_id": sid, "business_anchor_date": anchor},
        )
        if row is None:
            row = AdminDashboardBizDaySnapshot(
                store_id=sid,
                business_anchor_date=anchor,
                today_leave_members=tl,
                today_meals_to_prepare=tp,
                tomorrow_leave_members=nl,
                tomorrow_meals_to_prepare=np,
                today_expire_one_unit_members=te,
                recorded_at=now,
            )
            db.add(row)
        else:
            row.today_leave_members = tl
            row.today_meals_to_prepare = tp
            row.tomorrow_leave_members = nl
            row.tomorrow_meals_to_prepare = np
            row.today_expire_one_unit_members = te
            row.recorded_at = now
        db.commit()
        out = DashboardMealSummaryOut(
            shanghai_today=out.shanghai_today,
            business_anchor_date=out.business_anchor_date,
            today_leave_members=out.today_leave_members,
            today_meals_to_prepare=out.today_meals_to_prepare,
            tomorrow_leave_members=out.tomorrow_leave_members,
            tomorrow_meals_to_prepare=out.tomorrow_meals_to_prepare,
            today_expire_one_unit_members=out.today_expire_one_unit_members,
            today_single_retail_total_quantity=out.today_single_retail_total_quantity,
            tomorrow_single_retail_total_quantity=out.tomorrow_single_retail_total_quantity,
            total_members=out.total_members,
            active_weekly_members=out.active_weekly_members,
            expired_weekly_members=out.expired_weekly_members,
            active_monthly_members=out.active_monthly_members,
            expired_monthly_members=out.expired_monthly_members,
            weekly_card_reorder_members=out.weekly_card_reorder_members,
            weekly_card_reorder_base_members=out.weekly_card_reorder_base_members,
            monthly_card_reorder_members=out.monthly_card_reorder_members,
            monthly_card_reorder_base_members=out.monthly_card_reorder_base_members,
            tomorrow_first_meal_new_members=out.tomorrow_first_meal_new_members,
            today_meals_week_over_week_caption=out.today_meals_week_over_week_caption,
            tomorrow_meals_week_over_week_caption=out.tomorrow_meals_week_over_week_caption,
            today_menu_day_total_stock=today_menu_day_total_stock,
            tomorrow_menu_day_total_stock=tomorrow_menu_day_total_stock,
            today_prep_metrics=out.today_prep_metrics,
            tomorrow_prep_metrics=out.tomorrow_prep_metrics,
            from_snapshot=False,
            snapshot_recorded_at=row.recorded_at,
        )

    if not force_recompute:
        _dashboard_anchor_summary_cache[(sid, anchor)] = (time.time(), out)

    return out
