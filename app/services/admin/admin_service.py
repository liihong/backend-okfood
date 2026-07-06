from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import and_, case, delete, exists, func, literal, or_, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased, load_only

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.security import verify_password
from app.core.tenant_subscription import assert_admin_tenant_subscription_active
from app.core.timeutil import beijing_now_naive, today_shanghai, tomorrow_shanghai
from app.models.admin_dashboard_biz_day_snapshot import AdminDashboardBizDaySnapshot
from app.models.admin_user import AdminUser
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, MealPeriod, PlanType
from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
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
    CategoryPatchIn,
    DashboardDayPrepMetricsOut,
    DashboardMealSummaryOut,
    DishAdminOut,
    DishUpsertIn,
    MemberAdminOut,
    MemberAnalyticsOut,
    MemberListStatsOut,
    MemberPlanStatsOut,
    MemberRenewPendingStatsOut,
    MemberUnconsumedMealsOut,
    MemberReorderStatsOut,
    MenuScheduleAssignIn,
    RechargeIn,
    SettingsIn,
    WeeklySlotAssignIn,
    MenuDayTotalStockIn,
)
from app.services.delivery.courier_service import (
    count_expire_one_unit_members_for_business_day,
    count_members_first_scheduled_delivery_day,
)
from app.services.delivery.delivery_sheet_service import (
    DeliverySheetDayMetrics,
    _store_card_reorder_stats,
    _store_membership_counts,
    delivery_sheet_metrics_for_date,
    delivery_sheet_metrics_pending_sql_for_future_date,
    delivery_sheet_metrics_via_sql_for_unlocked_date,
    meal_units_totals_for_delivery_dates,
)
from app.services.member.member_address_service import (
    default_address_pick_subquery,
    delivery_region_name_map,
    full_address_line,
    routing_area_label,
)
from app.services.member.member_service import (
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


def _member_exclude_on_leave_scope(*, today: date | None = None):
    """非请假中（与列表「请假中」状态互斥，待续费口径需排除）。"""
    biz_today = today or today_shanghai()
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
    return ~or_(in_leave_range, tomorrow_leave_active)


def _member_renew_pending_scope(*, threshold: int):
    """待续费：生效中、剩余次数 <= 阈值、非暂停/退款/请假（与前台状态标签一致）。"""
    t = int(threshold)
    return and_(
        Member.is_active.is_(True),
        Member.balance > 0,
        Member.balance <= t,
        Member.delivery_deferred.is_(False),
        Member.membership_refunded_at.is_(None),
        _member_exclude_on_leave_scope(),
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
    renew_pending_only: bool = False,
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
    if renew_pending_only:
        from app.core.config import get_settings

        threshold = int(get_settings().LOW_BALANCE_THRESHOLD)
        stmt = stmt.where(_member_renew_pending_scope(threshold=threshold))
    return stmt


def admin_login_user(db: Session, username: str, password: str) -> AdminUser:
    u = db.execute(select(AdminUser).where(AdminUser.username == username)).scalar_one_or_none()
    if not u or not u.is_active:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 非平台管理员：租户到期后禁止登录
    assert_admin_tenant_subscription_active(db, u)
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


def _member_filter_count(
    db: Session,
    *,
    store_id: int,
    inactive_only: bool = False,
    delivery_deferred_only: bool = False,
    on_leave_only: bool = False,
    unassigned_region: bool = False,
    store_pickup_active: bool = False,
    renew_pending_only: bool = False,
) -> int:
    """会员档案库筛选计数：与列表页各 Tab/筛选项口径一致。"""
    stmt = _apply_member_list_filters(
        select(func.count()).select_from(Member),
        q_phone=None,
        validity=None,
        inactive_only=inactive_only,
        delivery_deferred_only=delivery_deferred_only,
        on_leave_only=on_leave_only,
        unassigned_region=unassigned_region,
        store_id=int(store_id),
        renew_pending_only=renew_pending_only,
    )
    if store_pickup_active:
        stmt = stmt.where(Member.store_pickup.is_(True), Member.balance > 0)
    return int(db.execute(stmt).scalar() or 0)


def _reorder_rate_percent(reorder: int, base: int) -> Decimal:
    """续卡率百分比，分母为 0 时返回 0。"""
    if base <= 0:
        return Decimal("0")
    return (Decimal(reorder) * Decimal("100") / Decimal(base)).quantize(Decimal("0.01"))


def _member_unconsumed_meals_total(db: Session, *, store_id: int) -> MemberUnconsumedMealsOut:
    """档案库未消费餐次：午餐池 + 晚餐池；排除已退款，与档案库 scope 一致。"""
    sid = int(store_id)
    archive_scope = and_(
        Member.deleted_at.is_(None),
        _member_archive_scope(),
        Member.membership_refunded_at.is_(None),
        Member.store_id == sid,
    )

    dinner_state = aliased(MemberMealPeriodState)
    lunch_rem = func.greatest(Member.balance, 0)
    dinner_rem = func.coalesce(func.greatest(dinner_state.balance, 0), 0)

    row = db.execute(
        select(
            func.coalesce(func.sum(lunch_rem), 0).label("lunch_total"),
            func.coalesce(func.sum(dinner_rem), 0).label("dinner_total"),
        )
        .select_from(Member)
        .outerjoin(
            dinner_state,
            and_(
                dinner_state.member_id == Member.id,
                dinner_state.meal_period == MealPeriod.DINNER.value,
            ),
        )
        .where(archive_scope)
    ).one()

    lunch_total = int(row.lunch_total or 0)
    dinner_total = int(row.dinner_total or 0)
    return MemberUnconsumedMealsOut(
        total=lunch_total + dinner_total,
        lunch_total=lunch_total,
        dinner_total=dinner_total,
    )


def _member_renew_pending_counts(db: Session, *, store_id: int, active_total: int) -> MemberRenewPendingStatsOut:
    """待续费户数及剩余 1 次 / 阈值次分布（与前台「待续费」标签口径一致）。"""
    from app.core.config import get_settings

    threshold = int(get_settings().LOW_BALANCE_THRESHOLD)
    row = db.execute(
        select(
            func.count().label("total"),
            func.coalesce(func.sum(case((Member.balance == 1, 1), else_=0)), 0).label("b1"),
            func.coalesce(func.sum(case((Member.balance == threshold, 1), else_=0)), 0).label("bt"),
        )
        .select_from(Member)
        .where(Member.deleted_at.is_(None), _member_archive_scope(), Member.store_id == int(store_id))
        .where(_member_renew_pending_scope(threshold=threshold))
    ).one()
    count = int(row.total or 0)
    share = (
        (Decimal(count) * Decimal("100") / Decimal(active_total)).quantize(Decimal("0.01"))
        if active_total > 0
        else Decimal("0")
    )
    return MemberRenewPendingStatsOut(
        count=count,
        balance_1_count=int(row.b1 or 0),
        balance_threshold_count=int(row.bt or 0),
        threshold=threshold,
        share_of_active_percent=share,
    )


def member_analytics_summary(db: Session, *, store_id: int) -> MemberAnalyticsOut:
    """会员运营分析：档案库总览 + 周/月卡结构 + 续卡率 + 运营状态分布。"""
    sid = int(store_id)
    overview = member_list_overview_counts(db, store_id=sid)
    mem_kw = _dashboard_membership_kw(db, store_id=sid)
    active_weekly = int(mem_kw.get("active_weekly_members") or 0)
    active_monthly = int(mem_kw.get("active_monthly_members") or 0)
    active_plan_total = active_weekly + active_monthly
    if active_plan_total > 0:
        weekly_share = (Decimal(active_weekly) * Decimal("100") / Decimal(active_plan_total)).quantize(
            Decimal("0.01")
        )
        monthly_share = (Decimal("100") - weekly_share).quantize(Decimal("0.01"))
    else:
        weekly_share = Decimal("0")
        monthly_share = Decimal("0")
    total = overview.total
    active_rate = (
        (Decimal(overview.active) * Decimal("100") / Decimal(total)).quantize(Decimal("0.01"))
        if total > 0
        else Decimal("0")
    )
    week_reorder = int(mem_kw.get("weekly_card_reorder_members") or 0)
    week_base = int(mem_kw.get("weekly_card_reorder_base_members") or 0)
    month_reorder = int(mem_kw.get("monthly_card_reorder_members") or 0)
    month_base = int(mem_kw.get("monthly_card_reorder_base_members") or 0)
    renew_pending = _member_renew_pending_counts(db, store_id=sid, active_total=overview.active)
    unconsumed_meals = _member_unconsumed_meals_total(db, store_id=sid)
    return MemberAnalyticsOut(
        total=overview.total,
        active=overview.active,
        expired=overview.expired,
        refunded=overview.refunded,
        refund_rate_percent=overview.refund_rate_percent,
        active_rate_percent=active_rate,
        weekly=MemberPlanStatsOut(
            active=active_weekly,
            expired=int(mem_kw.get("expired_weekly_members") or 0),
        ),
        monthly=MemberPlanStatsOut(
            active=active_monthly,
            expired=int(mem_kw.get("expired_monthly_members") or 0),
        ),
        active_weekly_share_percent=weekly_share,
        active_monthly_share_percent=monthly_share,
        weekly_reorder=MemberReorderStatsOut(
            reorder_members=week_reorder,
            base_members=week_base,
            rate_percent=_reorder_rate_percent(week_reorder, week_base),
        ),
        monthly_reorder=MemberReorderStatsOut(
            reorder_members=month_reorder,
            base_members=month_base,
            rate_percent=_reorder_rate_percent(month_reorder, month_base),
        ),
        renew_pending=renew_pending,
        unconsumed_meals=unconsumed_meals,
        inactive_count=_member_filter_count(db, store_id=sid, inactive_only=True),
        paused_delivery_count=_member_filter_count(db, store_id=sid, delivery_deferred_only=True),
        on_leave_count=_member_filter_count(db, store_id=sid, on_leave_only=True),
        store_pickup_active_count=_member_filter_count(db, store_id=sid, store_pickup_active=True),
        unassigned_region_count=_member_filter_count(db, store_id=sid, unassigned_region=True),
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
    renew_pending_only: bool = False,
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
        renew_pending_only=renew_pending_only,
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
        renew_pending_only=renew_pending_only,
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
    member_rows: list[tuple[Member, MemberAddress | None]] = []
    for _total_col, m, addr in rows:
        if m is None:
            continue
        member_rows.append((m, addr))
        if addr and addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)
    member_ids = [int(m.id) for m, _addr in member_rows]
    from app.services.meal_period.card_eligibility import members_entitled_meal_periods_map
    from app.services.meal_period.plan_type_sync import format_plan_type_display, meal_scope_label_from_periods
    from app.services.meal_period.units import load_dinner_meal_period_states_map

    entitled_map = members_entitled_meal_periods_map(db, member_ids)
    dinner_state_map = load_dinner_meal_period_states_map(db, member_ids)
    for m, addr in member_rows:
        if addr:
            detail = full_address_line(addr.map_location_text, addr.door_detail)
            ar = routing_area_label(addr, id_to_name)
            ad_line = f"{ar} {detail}".strip() if detail else ar
        else:
            detail = ""
            ad_line = "（未设置默认配送地址）"
            ar = UNASSIGNED_DELIVERY_AREA
        dr_id = int(addr.delivery_region_id) if addr and addr.delivery_region_id is not None else None
        periods = entitled_map.get(int(m.id), frozenset())
        dinner_row = dinner_state_map.get(int(m.id))
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
                entitled_meal_periods=sorted(periods),
                meal_scope_label=meal_scope_label_from_periods(periods),
                plan_type_display=format_plan_type_display(m.plan_type, periods),
                dinner_balance=int(dinner_row.balance or 0) if dinner_row else 0,
                dinner_meal_quota_total=int(dinner_row.meal_quota_total or 0) if dinner_row else 0,
                dinner_is_leaved_tomorrow=bool(dinner_row.is_leaved_tomorrow) if dinner_row else False,
                dinner_tomorrow_leave_target_date=(
                    dinner_row.tomorrow_leave_target_date if dinner_row else None
                ),
                dinner_leave_range_start=dinner_row.leave_range_start if dinner_row else None,
                dinner_leave_range_end=dinner_row.leave_range_end if dinner_row else None,
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
    skip_plan_type_update: bool = False,
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
    from app.services.member.member_renew_subscribe_service import reset_renew_remind_on_recharge

    reset_renew_remind_on_recharge(m, balance_before=balance_before, balance_after=int(m.balance))
    if body.plan_type is not None and not skip_plan_type_update:
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
            meal_period=MealPeriod.LUNCH.value,
            change=body.amount,
            reason=BalanceReason.RECHARGE.value if body.amount > 0 else BalanceReason.REFUND.value,
            operator=operator,
            detail=detail,
        )
    )
    from app.services.meal_period.balance import sync_member_is_active_from_period_balances

    sync_member_is_active_from_period_balances(db, m)
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


def _merge_dish_last_used_date(existing: date | None, candidate: date | None) -> date | None:
    """取两个供餐日中较晚的一天；任一为空则返回另一个。"""
    if candidate is None:
        return existing
    if existing is None:
        return candidate
    return candidate if candidate > existing else existing


def _dish_last_used_dates_batch(
    db: Session,
    dish_ids: list[int],
    *,
    store_id: int,
) -> dict[int, date | None]:
    """批量查询菜品上次排期供餐日：按日排期与周槽位取最大值，不含未来日期。"""
    if not dish_ids:
        return {}
    sid = int(store_id)
    today = today_shanghai()
    out: dict[int, date | None] = {int(did): None for did in dish_ids}

    sched_rows = db.execute(
        select(MenuSchedule.dish_id, func.max(MenuSchedule.menu_date)).where(
            MenuSchedule.store_id == sid,
            MenuSchedule.dish_id.in_(dish_ids),
            MenuSchedule.menu_date <= today,
        ).group_by(MenuSchedule.dish_id)
    ).all()
    for dish_id, max_date in sched_rows:
        out[int(dish_id)] = max_date

    slot_rows = db.execute(
        select(WeeklyMenuSlot.dish_id, WeeklyMenuSlot.week_start, WeeklyMenuSlot.slot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.dish_id.in_(dish_ids),
        )
    ).all()
    for dish_id, week_start, slot in slot_rows:
        serve_date = week_start + timedelta(days=int(slot) - 1)
        if serve_date > today:
            continue
        did = int(dish_id)
        out[did] = _merge_dish_last_used_date(out.get(did), serve_date)

    return out


def _format_dish_last_used_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _dish_admin_out_from_row(
    row: MenuDish,
    *,
    include_sop: bool = True,
    lite: bool = False,
    last_used_date: date | None = None,
) -> DishAdminOut:
    return DishAdminOut(
        id=row.id,
        name=row.name,
        description=None if lite else row.description,
        image_url=None if lite else row.image_url,
        is_enabled=row.is_enabled,
        category_id=row.category_id,
        meat_category_id=row.meat_category_id,
        dish_type_category_id=row.dish_type_category_id,
        single_order_price_yuan=_dish_price_yuan_str(row.single_order_price_yuan),
        spice_level=_dish_spice_level_out(row.spice_level),
        internal_view_sop=row.internal_view_sop if include_sop else None,
        created_at=row.created_at.isoformat() if row.created_at else "",
        last_used_date=None if lite else _format_dish_last_used_date(last_used_date),
    )


def get_dish_admin(db: Session, dish_id: int, *, store_id: int) -> DishAdminOut:
    sid = int(store_id)
    row = db.get(MenuDish, dish_id)
    if not row or int(row.store_id) != sid:
        raise HTTPException(status_code=404, detail="菜品不存在")
    return _dish_admin_out_from_row(row, include_sop=True)


def _validate_dish_leaf_category(
    db: Session,
    *,
    category_id: int | None,
    store_id: int,
    parent_code: str,
    field_label: str,
) -> int | None:
    if category_id is None:
        return None
    cat = db.get(ProductCategory, int(category_id))
    sid = int(store_id)
    if cat is None or int(cat.store_id) != sid:
        raise HTTPException(status_code=400, detail=f"{field_label}不存在")
    if not cat.is_active:
        raise HTTPException(status_code=400, detail=f"{field_label}已停用")
    if _category_has_children(db, category_id=int(cat.id), store_id=sid):
        raise HTTPException(status_code=400, detail=f"请选择{field_label}下的具体子类")
    if cat.parent_id is None:
        raise HTTPException(status_code=400, detail=f"请选择{field_label}下的具体子类")
    parent = db.get(ProductCategory, int(cat.parent_id))
    if parent is None or parent.code != parent_code:
        raise HTTPException(status_code=400, detail=f"{field_label}类型不匹配")
    return int(cat.id)


def upsert_dish(db: Session, body: DishUpsertIn, *, store_id: int) -> DishAdminOut:
    sid = int(store_id)
    meat_category_id = _validate_dish_leaf_category(
        db, category_id=body.meat_category_id, store_id=sid, parent_code="meat", field_label="肉类分类"
    )
    dish_type_category_id = _validate_dish_leaf_category(
        db,
        category_id=body.dish_type_category_id,
        store_id=sid,
        parent_code="dish_type",
        field_label="菜品分类",
    )
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
        row.category_id = None
        row.meat_category_id = meat_category_id
        row.dish_type_category_id = dish_type_category_id
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
            category_id=None,
            meat_category_id=meat_category_id,
            dish_type_category_id=dish_type_category_id,
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
    category_id: int | None = None,
    store_id: int,
    lite: bool = False,
) -> list[DishAdminOut]:
    sid = int(store_id)
    load_cols = [
        MenuDish.id,
        MenuDish.name,
        MenuDish.is_enabled,
        MenuDish.category_id,
        MenuDish.meat_category_id,
        MenuDish.dish_type_category_id,
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
    if category_id is not None:
        if int(category_id) == 0:
            stmt = stmt.where(
                MenuDish.meat_category_id.is_(None),
                MenuDish.dish_type_category_id.is_(None),
            )
        else:
            ids = _category_descendant_ids(db, category_id=int(category_id), store_id=sid)
            stmt = stmt.where(
                or_(MenuDish.meat_category_id.in_(ids), MenuDish.dish_type_category_id.in_(ids))
            )
    rows = db.scalars(stmt).all()
    last_used_map: dict[int, date | None] = {}
    if not lite and rows:
        last_used_map = _dish_last_used_dates_batch(
            db,
            [int(r.id) for r in rows],
            store_id=sid,
        )
    return [
        _dish_admin_out_from_row(
            r,
            include_sop=False,
            lite=lite,
            last_used_date=last_used_map.get(int(r.id)),
        )
        for r in rows
    ]


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


def _category_admin_out(row: ProductCategory) -> CategoryAdminOut:
    return CategoryAdminOut(
        id=row.id,
        parent_id=row.parent_id,
        code=row.code,
        name=row.name,
        sort_order=row.sort_order,
        is_active=row.is_active,
    )


def _category_has_children(db: Session, *, category_id: int, store_id: int) -> bool:
    cnt = db.scalar(
        select(func.count())
        .select_from(ProductCategory)
        .where(ProductCategory.store_id == int(store_id), ProductCategory.parent_id == int(category_id))
    )
    return int(cnt or 0) > 0


def _category_descendant_ids(db: Session, *, category_id: int, store_id: int) -> list[int]:
    """含自身及全部下级分类 id（当前为二级树，一层子级即可）。"""
    sid = int(store_id)
    cid = int(category_id)
    root = db.get(ProductCategory, cid)
    if not root or int(root.store_id) != sid:
        return [cid]
    child_ids = list(
        db.scalars(
            select(ProductCategory.id).where(ProductCategory.store_id == sid, ProductCategory.parent_id == cid)
        ).all()
    )
    return [cid, *[int(x) for x in child_ids]]


def _validate_category_parent(
    db: Session,
    *,
    store_id: int,
    parent_id: int | None,
    category_id: int | None = None,
) -> int | None:
    if parent_id is None:
        return None
    pid = int(parent_id)
    if category_id is not None and pid == int(category_id):
        raise HTTPException(status_code=400, detail="上级分类不能为自身")
    parent = db.get(ProductCategory, pid)
    if parent is None or int(parent.store_id) != int(store_id):
        raise HTTPException(status_code=400, detail="上级分类不存在")
    if parent.parent_id is not None:
        raise HTTPException(status_code=400, detail="仅支持二级分类，请选择一级分类作为上级")
    if category_id is not None:
        child_cnt = db.scalar(
            select(func.count())
            .select_from(ProductCategory)
            .where(ProductCategory.store_id == int(store_id), ProductCategory.parent_id == int(category_id))
        )
        if int(child_cnt or 0) > 0 and pid != int(category_id):
            raise HTTPException(status_code=400, detail="该分类下仍有子分类，请先调整子分类后再变更上级")
    return pid


def list_categories_admin(db: Session, *, store_id: int) -> list[CategoryAdminOut]:
    sid = int(store_id)
    rows = db.scalars(
        select(ProductCategory).where(ProductCategory.store_id == sid).order_by(ProductCategory.sort_order, ProductCategory.id)
    ).all()
    return [_category_admin_out(r) for r in rows]


def create_category_admin(db: Session, body: CategoryCreateIn, *, store_id: int) -> CategoryAdminOut:
    sid = int(store_id)
    code = body.code.strip()
    name = body.name.strip()
    if not code or not name:
        raise HTTPException(status_code=400, detail="分类编码与名称不能为空")
    parent_id = _validate_category_parent(db, store_id=sid, parent_id=body.parent_id)
    row = ProductCategory(
        store_id=sid,
        parent_id=parent_id,
        code=code,
        name=name,
        sort_order=body.sort_order,
        is_active=True,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="分类编码已存在")
    db.refresh(row)
    return _category_admin_out(row)


def _get_category_for_store(db: Session, *, category_id: int, store_id: int) -> ProductCategory:
    row = db.get(ProductCategory, int(category_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="分类不存在")
    return row


def patch_category_admin(
    db: Session, *, category_id: int, body: CategoryPatchIn, store_id: int
) -> CategoryAdminOut:
    row = _get_category_for_store(db, category_id=category_id, store_id=store_id)
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="分类名称不能为空")
        row.name = name
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    if "parent_id" in body.model_fields_set:
        row.parent_id = _validate_category_parent(
            db, store_id=int(store_id), parent_id=body.parent_id, category_id=int(category_id)
        )
    db.commit()
    db.refresh(row)
    return _category_admin_out(row)


def delete_category_admin(db: Session, *, category_id: int, store_id: int) -> None:
    row = _get_category_for_store(db, category_id=category_id, store_id=store_id)
    child_cnt = db.scalar(
        select(func.count())
        .select_from(ProductCategory)
        .where(ProductCategory.store_id == int(store_id), ProductCategory.parent_id == int(category_id))
    )
    if int(child_cnt or 0) > 0:
        raise HTTPException(status_code=400, detail="该分类下仍有子分类，无法删除")
    cnt = db.scalar(
        select(func.count())
        .select_from(MenuDish)
        .where(
            MenuDish.store_id == int(store_id),
            or_(
                MenuDish.category_id == int(category_id),
                MenuDish.meat_category_id == int(category_id),
                MenuDish.dish_type_category_id == int(category_id),
            ),
        )
    )
    if int(cnt or 0) > 0:
        raise HTTPException(status_code=400, detail="该分类下仍有菜品，无法删除")
    db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="分类仍被引用，无法删除")


def _weekly_slots_raw(rows: list) -> list[dict]:
    return [
        {
            "slot": w.slot,
            "dish_id": d.id,
            "name": d.name,
            "is_enabled": d.is_enabled,
            "category_id": d.category_id,
            "meat_category_id": d.meat_category_id,
            "dish_type_category_id": d.dish_type_category_id,
            "single_order_price_yuan": _dish_price_yuan_str(d.single_order_price_yuan),
            "total_stock": int(w.total_stock) if w.total_stock is not None else None,
        }
        for w, d in rows
    ]


def _weekly_menu_day_stats_by_dates(
    db: Session,
    dates: list[date],
    *,
    store_id: int,
    meal_period: str = "lunch",
    metrics_cache: dict | None = None,
) -> tuple[dict[date, int], dict[date, int]]:
    """本周菜单统计：与单次卡库存、dashboard-summary 共用 menu_day_stock 聚合。"""
    from app.services.admin.menu_day_stock_service import (
        dashboard_meal_totals_by_dates,
        paid_single_retail_portions_by_dates,
    )

    uniq = list(dict.fromkeys(dates))
    return (
        dashboard_meal_totals_by_dates(
            db,
            uniq,
            store_id=int(store_id),
            meal_period=meal_period,
            metrics_cache=metrics_cache,
        ),
        paid_single_retail_portions_by_dates(db, uniq, store_id=int(store_id), meal_period=meal_period),
    )


def _weekly_slots_payload(db: Session, anchor: date, store_id: int, *, meal_period: str = "lunch") -> list[dict]:
    from app.services.meal_period.normalize import normalize_meal_period

    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    rows = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.meal_period == period,
        )
        .order_by(WeeklyMenuSlot.slot)
    ).all()
    from app.services.admin.menu_day_stock_service import weekly_slot_stock_extras

    dates = [anchor + timedelta(days=i) for i in range(7)]
    metrics_cache: dict = {}
    sub_by_date, paid_by_date = _weekly_menu_day_stats_by_dates(
        db, dates, store_id=sid, meal_period=period, metrics_cache=metrics_cache
    )
    return weekly_slot_stock_extras(
        db,
        anchor,
        _weekly_slots_raw(rows),
        store_id=sid,
        meal_period=period,
        sub_by_date=sub_by_date,
        paid_by_date=paid_by_date,
    )


def _weekly_dual_preview(
    db: Session, this_a: date, next_a: date, *, store_id: int, meal_period: str = "lunch"
) -> dict[str, list[dict]]:
    """本周+下周槽位：仅本周算应配送/单次余；下周只返回槽位与总份配置（同 meal_period 隔离）。"""
    from app.services.meal_period.normalize import normalize_meal_period

    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    anchors = [this_a, next_a]
    this_dates = [this_a + timedelta(days=i) for i in range(7)]
    from app.services.admin.menu_day_stock_service import weekly_slot_stock_extras

    metrics_cache: dict = {}
    sub_by_date, paid_by_date = _weekly_menu_day_stats_by_dates(
        db, this_dates, store_id=sid, meal_period=period, metrics_cache=metrics_cache
    )
    rows = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start.in_(anchors),
            WeeklyMenuSlot.meal_period == period,
        )
        .order_by(WeeklyMenuSlot.week_start, WeeklyMenuSlot.slot)
    ).all()
    by_anchor: dict[date, list] = {this_a: [], next_a: []}
    for w, d in rows:
        by_anchor.setdefault(w.week_start, []).append((w, d))
    return {
        "this_week": weekly_slot_stock_extras(
            db,
            this_a,
            _weekly_slots_raw(by_anchor.get(this_a, [])),
            store_id=sid,
            meal_period=period,
            sub_by_date=sub_by_date,
            paid_by_date=paid_by_date,
        ),
        "next_week": weekly_slot_stock_extras(
            db,
            next_a,
            _weekly_slots_raw(by_anchor.get(next_a, [])),
            store_id=sid,
            meal_period=period,
            skip_subscription_stats=True,
        ),
    }


def admin_weekly_menu_preview(
    db: Session, week_start: date | None, *, store_id: int, meal_period: str = "lunch"
) -> dict:
    """不传 week_start 时返回本周 + 下周槽位，便于预告维护；meal_period 区分午/晚餐。"""
    from app.services.meal_period.normalize import normalize_meal_period

    t = today_shanghai()
    this_a = _monday_of_week(t)
    next_a = this_a + timedelta(days=7)
    period = normalize_meal_period(meal_period)
    if week_start is not None:
        anchor = _monday_of_week(week_start)
        return {
            "week_start": anchor.isoformat(),
            "meal_period": period,
            "slots": _weekly_slots_payload(db, anchor, store_id, meal_period=period),
        }
    dual = _weekly_dual_preview(db, this_a, next_a, store_id=store_id, meal_period=period)
    return {
        "this_week_start": this_a.isoformat(),
        "next_week_start": next_a.isoformat(),
        "meal_period": period,
        **dual,
    }


def assign_weekly_menu_slot(db: Session, body: WeeklySlotAssignIn, *, store_id: int) -> None:
    from app.services.meal_period.normalize import normalize_meal_period

    anchor = _monday_of_week(body.week_start)
    sid = int(store_id)
    # 午餐/晚餐槽位独立存储，须显式指定 meal_period
    period = normalize_meal_period(body.meal_period)
    if body.dish_id is None:
        row = db.scalar(
            select(WeeklyMenuSlot).where(
                WeeklyMenuSlot.store_id == sid,
                WeeklyMenuSlot.week_start == anchor,
                WeeklyMenuSlot.slot == body.slot,
                WeeklyMenuSlot.meal_period == period,
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
            WeeklyMenuSlot.meal_period == period,
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
                    meal_period=period,
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
    from app.services.meal_period.normalize import normalize_meal_period
    from app.services.admin.menu_day_stock_service import set_weekly_slot_total_stock

    # 严格区分午/晚餐：dinner 写入不得落入 lunch 槽位
    period = normalize_meal_period(body.meal_period)
    set_weekly_slot_total_stock(
        db,
        _monday_of_week(body.week_start),
        body.slot,
        body.total_stock,
        store_id=int(store_id),
        meal_period=period,
    )


def update_settings(db: Session, body: SettingsIn, *, store_id: int) -> None:
    from app.models.store import Store

    st = db.get(Store, int(store_id))
    if not st:
        raise HTTPException(status_code=404, detail="门店不存在")
    st.leave_deadline_time = body.leave_deadline_time
    db.commit()


def count_leave_members_for_delivery_day(db: Session, d: date, *, store_id: int | None = None) -> int:
    from app.core.tenant_scope import require_store_id_for_service

    sid = require_store_id_for_service(store_id, operation="请假人数统计")
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
    """锚定业务日午餐单次零售份数（today_single_retail_total_quantity 口径，meal_period=lunch）。"""
    from app.models.enums import MealPeriod

    m = _paid_single_retail_portions_by_dates(
        db, [delivery_date], store_id=store_id, meal_period=MealPeriod.LUNCH.value
    )
    return int(m.get(delivery_date, 0))


def _paid_single_retail_portions_by_dates(
    db: Session, dates: list[date], *, store_id: int, meal_period: str = "lunch"
) -> dict[date, int]:
    """批量查询多日已支付单次零售份数；须显式 meal_period，避免午/晚餐零售混计。"""
    from app.services.admin.menu_day_stock_service import paid_single_retail_portions_by_dates
    from app.services.meal_period.normalize import normalize_meal_period

    period = normalize_meal_period(meal_period)
    return paid_single_retail_portions_by_dates(db, dates, store_id=int(store_id), meal_period=period)


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
    meal_period: str = "lunch",
) -> dict[date, int]:
    """批量读取历史锚日归档中的「当日备餐份数」，避免同比基线重复跑大表；按 meal_period 分档。"""
    from app.services.meal_period.normalize import normalize_meal_period

    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}
    period = normalize_meal_period(meal_period)
    rows = db.scalars(
        select(AdminDashboardBizDaySnapshot).where(
            AdminDashboardBizDaySnapshot.store_id == int(store_id),
            AdminDashboardBizDaySnapshot.business_anchor_date.in_(uniq),
            AdminDashboardBizDaySnapshot.meal_period == period,
        )
    ).all()
    return {row.business_anchor_date: int(row.today_meals_to_prepare) for row in rows}


def _dashboard_meal_period_stock_fields(
    db: Session,
    *,
    store_id: int,
    anchor: date,
    day_after: date,
    day_after_tomorrow: date,
) -> dict:
    """顶卡午/晚餐库存扩展字段（损耗、剩余、晚餐 metrics）；午餐/晚餐 total_stock 分字段读取，互不覆盖。"""
    from app.models.enums import MealPeriod
    from app.services.admin.day_stock_service import get_day_stock_breakdown
    from app.services.delivery.delivery_sheet_service import delivery_sheet_metrics_for_period
    from app.services.admin.menu_day_stock_service import (
        paid_single_retail_portions_by_dates,
        weekly_menu_dinner_day_total_stock,
    )

    sid = int(store_id)
    metrics_cache: dict = {}
    lunch_bd = get_day_stock_breakdown(db, store_id=sid, business_date=anchor, meal_period=MealPeriod.LUNCH.value)
    dinner_bd = get_day_stock_breakdown(db, store_id=sid, business_date=anchor, meal_period=MealPeriod.DINNER.value)
    today_dinner_m = delivery_sheet_metrics_for_period(
        db,
        delivery_date=anchor,
        store_id=sid,
        meal_period=MealPeriod.DINNER.value,
        metrics_cache=metrics_cache,
    )
    tomorrow_dinner_m = delivery_sheet_metrics_for_period(
        db,
        delivery_date=day_after,
        store_id=sid,
        meal_period=MealPeriod.DINNER.value,
        metrics_cache=metrics_cache,
    )
    tomorrow_dinner_retail = paid_single_retail_portions_by_dates(
        db, [day_after], store_id=sid, meal_period=MealPeriod.DINNER.value
    )
    return {
        "today_lunch_waste_total": lunch_bd.waste_total,
        "today_lunch_remaining": lunch_bd.remaining,
        # 晚餐顶卡「后厨产出量」：today_dinner_menu_day_total_stock（勿与午餐 today_menu_day_total_stock 混读）
        "today_dinner_menu_day_total_stock": weekly_menu_dinner_day_total_stock(
            db, anchor, store_id=sid
        ),
        "tomorrow_dinner_menu_day_total_stock": weekly_menu_dinner_day_total_stock(
            db, day_after, store_id=sid
        ),
        "day_after_tomorrow_dinner_menu_day_total_stock": weekly_menu_dinner_day_total_stock(
            db, day_after_tomorrow, store_id=sid
        ),
        "today_dinner_single_retail_total_quantity": dinner_bd.single_retail_total,
        "tomorrow_dinner_single_retail_total_quantity": int(tomorrow_dinner_retail.get(day_after, 0)),
        "today_dinner_waste_total": dinner_bd.waste_total,
        "today_dinner_remaining": dinner_bd.remaining,
        "today_dinner_prep_metrics": _dashboard_day_prep_metrics_out(today_dinner_m),
        "tomorrow_dinner_prep_metrics": _dashboard_day_prep_metrics_out(tomorrow_dinner_m),
    }


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
            from app.services.delivery.delivery_day_lock_service import (
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
    from app.models.enums import MealPeriod

    from app.core.tenant_scope import require_store_id_for_service

    sid = require_store_id_for_service(store_id, operation="仪表盘备餐汇总")
    cal_today = today_shanghai()
    # 未传 business_anchor_date 时默认锚定上海当日
    anchor = business_anchor_date or cal_today
    day_after = date.fromordinal(anchor.toordinal() + 1)
    day_after_tomorrow = date.fromordinal(day_after.toordinal() + 1)

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
    from app.services.admin.menu_day_stock_service import weekly_menu_lunch_day_total_stock

    # 午餐顶卡「后厨产出量」→ today_menu_day_total_stock（meal_period=lunch，与晚餐字段严格分离）
    today_menu_day_total_stock = weekly_menu_lunch_day_total_stock(db, anchor, store_id=sid)
    tomorrow_menu_day_total_stock = weekly_menu_lunch_day_total_stock(db, day_after, store_id=sid)
    day_after_tomorrow_menu_day_total_stock = weekly_menu_lunch_day_total_stock(
        db, day_after_tomorrow, store_id=sid
    )
    period_stock_kw = _dashboard_meal_period_stock_fields(
        db, store_id=sid, anchor=anchor, day_after=day_after, day_after_tomorrow=day_after_tomorrow
    )
    metrics_cache: dict[date, DeliverySheetDayMetrics] = {}
    snapshot_meal_totals = _dashboard_snapshot_meal_totals(
        db,
        store_id=sid,
        dates=[d for d in (wow_prev_anchor, wow_prev_day_after) if d < cal_today],
    )

    if anchor < cal_today and not force_recompute:
        row = db.get(
            AdminDashboardBizDaySnapshot,
            {"store_id": sid, "business_anchor_date": anchor, "meal_period": "lunch"},
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
                db,
                [anchor, day_after],
                store_id=sid,
                meal_period=MealPeriod.LUNCH.value,
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
                day_after_tomorrow_menu_day_total_stock=day_after_tomorrow_menu_day_total_stock,
                today_prep_metrics=today_metrics,
                tomorrow_prep_metrics=tomorrow_metrics,
                **period_stock_kw,
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
    single_retail_map = _paid_single_retail_portions_by_dates(
        db, [anchor, day_after], store_id=sid, meal_period=MealPeriod.LUNCH.value
    )

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
        day_after_tomorrow_menu_day_total_stock=day_after_tomorrow_menu_day_total_stock,
        today_prep_metrics=today_metrics,
        tomorrow_prep_metrics=tomorrow_metrics,
        **period_stock_kw,
        from_snapshot=False,
        snapshot_recorded_at=None,
    )

    if anchor < cal_today:
        now = beijing_now_naive()
        row = db.get(
            AdminDashboardBizDaySnapshot,
            {"store_id": sid, "business_anchor_date": anchor, "meal_period": "lunch"},
        )
        if row is None:
            row = AdminDashboardBizDaySnapshot(
                store_id=sid,
                business_anchor_date=anchor,
                meal_period="lunch",
                today_leave_members=tl,
                today_meals_to_prepare=tp,
                kitchen_output_total=today_menu_day_total_stock,
                tomorrow_leave_members=nl,
                tomorrow_meals_to_prepare=np,
                today_expire_one_unit_members=te,
                recorded_at=now,
            )
            db.add(row)
        else:
            row.today_leave_members = tl
            row.today_meals_to_prepare = tp
            row.kitchen_output_total = today_menu_day_total_stock
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
            day_after_tomorrow_menu_day_total_stock=day_after_tomorrow_menu_day_total_stock,
            today_prep_metrics=out.today_prep_metrics,
            tomorrow_prep_metrics=out.tomorrow_prep_metrics,
            today_lunch_waste_total=out.today_lunch_waste_total,
            today_lunch_remaining=out.today_lunch_remaining,
            today_dinner_menu_day_total_stock=out.today_dinner_menu_day_total_stock,
            tomorrow_dinner_menu_day_total_stock=out.tomorrow_dinner_menu_day_total_stock,
            day_after_tomorrow_dinner_menu_day_total_stock=out.day_after_tomorrow_dinner_menu_day_total_stock,
            today_dinner_single_retail_total_quantity=out.today_dinner_single_retail_total_quantity,
            tomorrow_dinner_single_retail_total_quantity=out.tomorrow_dinner_single_retail_total_quantity,
            today_dinner_waste_total=out.today_dinner_waste_total,
            today_dinner_remaining=out.today_dinner_remaining,
            today_dinner_prep_metrics=out.today_dinner_prep_metrics,
            tomorrow_dinner_prep_metrics=out.tomorrow_dinner_prep_metrics,
            from_snapshot=False,
            snapshot_recorded_at=row.recorded_at,
        )

    if not force_recompute:
        _dashboard_anchor_summary_cache[(sid, anchor)] = (time.time(), out)

    return out
