from collections import defaultdict
from datetime import date
from decimal import Decimal
import re

from fastapi import HTTPException
from sqlalchemy import and_, func, literal, not_, or_, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units
from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.balance_log import BalanceLog
from app.models.courier import Courier
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.courier import CourierTaskMemberOut
from app.services.admin.courier_admin_service import regions_for_courier
from app.services.delivery.courier_task_sorting import (
    centroid_from_task_rows,
    distance_from_anchor_m,
    order_task_rows_by_nearest_neighbor,
    reference_lng_lat_for_task_sorting,
)
from app.services.shared.store_config_service import load_store_coordinates_for_sorting
from app.services.member.leave import is_absent_on_delivery_date
from app.services.member.member_address_service import (
    default_address_pick_subquery,
    full_address_line,
    load_default_address_map,
)
from app.services.member.member_service import effective_daily_meal_units, sql_effective_daily_meal_units_column
from app.services.order.single_meal_order_service import list_courier_single_order_tasks


def _member_scope_clause(*, tenant_id: int | None, store_id: int | None):
    """会员名单范围：委托 ``tenant_scope.sql_member_scope_clause``，禁止双空回落主租户。"""
    from app.core.tenant_scope import sql_member_scope_clause

    return sql_member_scope_clause(tenant_id=tenant_id, store_id=store_id)


def _member_not_skip_subscription_saturday(delivery_date: date):
    """普通周六剔除「固定周六不履约」会员；非周六不加条件。"""
    if delivery_date.weekday() == 5:
        return Member.skip_subscription_saturday.is_(False)
    return literal(True)


def member_on_subscription_delivery_schedule(
    member: Member,
    *,
    delivery_date: date,
    today: date | None = None,
) -> bool:
    """会员在指定业务日是否计入配送大表（到家或自提），与 eligible_members 口径一致。"""
    if not is_subscription_delivery_day(delivery_date):
        return False
    if member.deleted_at is not None:
        return False
    if not bool(member.is_active):
        return False
    if bool(member.delivery_deferred):
        return False
    units = effective_daily_meal_units(member)
    if int(member.balance) < units:
        return False
    biz_today = today if today is not None else today_shanghai()
    if is_absent_on_delivery_date(member, delivery_date, today=biz_today):
        return False
    ds = member.delivery_start_date
    if ds is not None and ds > delivery_date:
        return False
    if delivery_date.weekday() == 5 and bool(member.skip_subscription_saturday):
        return False
    return True


def member_on_any_entitled_delivery_schedule(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    today: date | None = None,
) -> bool:
    """备餐锁窗等：任一已开通餐段在业务日应履约则视为在表（午/晚餐严格分判后合并）。"""
    from app.services.meal_period.lunch_schedule import member_on_lunch_delivery_schedule
    from app.services.dinner.schedule import member_on_dinner_delivery_schedule

    if member_on_lunch_delivery_schedule(
        db, member, delivery_date=delivery_date, today=today
    ):
        return True
    return member_on_dinner_delivery_schedule(
        db, member, delivery_date=delivery_date, today=today
    )


def normalize_cn_mobile(raw: str) -> str:
    s = (raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    if len(digits) != 11 or not digits.startswith("1"):
        raise HTTPException(status_code=400, detail="请输入有效手机号")
    return digits


def courier_login(db: Session, courier_id: str, pin: str) -> Courier:
    c = db.get(Courier, courier_id)
    if not c or not c.is_active:
        raise HTTPException(status_code=401, detail="工号或 PIN 错误")
    if not verify_password(pin, c.pin_hash):
        raise HTTPException(status_code=401, detail="工号或 PIN 错误")
    return c


def courier_login_by_phone(db: Session, phone_raw: str) -> Courier:
    norm = normalize_cn_mobile(phone_raw)
    # 先用 SQL 按标准格式精确匹配，覆盖绝大多数情况
    stmt = select(Courier).where(
        Courier.is_active.is_(True),
        Courier.phone.in_([norm, f"86{norm}", f"+86{norm}"]),
    )
    matched = list(db.scalars(stmt).all())
    if not matched:
        # 降级：少量存储格式不规范的号码（全库扫描，但仅在精确匹配失败时触发）
        all_candidates = db.scalars(
            select(Courier).where(Courier.is_active.is_(True), Courier.phone.isnot(None))
        ).all()
        for c in all_candidates:
            p = (c.phone or "").strip()
            if not p:
                continue
            cand_digits = re.sub(r"\D", "", p)
            if len(cand_digits) == 13 and cand_digits.startswith("86"):
                cand_digits = cand_digits[2:]
            if cand_digits == norm:
                matched.append(c)
    if not matched:
        raise HTTPException(status_code=401, detail="手机号未登记或已停用")
    if len(matched) > 1:
        raise HTTPException(status_code=409, detail="该手机号绑定多个配送账号，请联系管理员")
    return matched[0]


def _home_delivery_absent_clause(delivery_date: date):
    """到家应送 SQL：业务日命中请假区间 / 明天请假（与 leave.is_absent_on_delivery_date 一致）。"""
    today = today_shanghai()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= delivery_date,
        Member.leave_range_end >= delivery_date,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == delivery_date,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(delivery_date) == literal(tomorrow),
    )
    return or_(in_leave_range, target_hit, legacy_tomorrow)


def post_push_first_day_whitelist_member_ids(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
    meal_period: str = "lunch",
) -> set[int]:
    """
    推单后白名单：起送业务日恰为 ``delivery_date`` 且当前满足应送 SQL 的到家会员 id。
    meal_period 默认 lunch（现网行为）；dinner 走晚餐 eligible 口径。
    """
    from app.models.enums import MealPeriod
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD

    if not is_subscription_delivery_day(delivery_date):
        return set()
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    if period == MealPeriod.DINNER.value:
        from app.services.dinner.eligibility import eligible_members_for_dinner_delivery

        members, _ = eligible_members_for_dinner_delivery(
            db,
            delivery_date=delivery_date,
            delivery_region_id=delivery_region_id,
            tenant_id=tenant_id,
            store_id=store_id,
        )
        return {
            int(m.id)
            for m in members
            if m.delivery_start_date is not None and m.delivery_start_date == delivery_date
        }

    units_sql = sql_effective_daily_meal_units_column()
    q = select(Member.id).where(
        Member.deleted_at.is_(None),
        Member.is_active.is_(True),
        Member.balance >= units_sql,
        Member.store_pickup.is_(False),
        not_(_home_delivery_absent_clause(delivery_date)),
        Member.delivery_start_date == delivery_date,
        _member_not_skip_subscription_saturday(delivery_date),
        _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
    )
    if delivery_region_id is not None:
        daf = default_address_pick_subquery()
        q = (
            q.select_from(Member)
            .outerjoin(daf, daf.c.mid == Member.id)
            .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
            .where(MemberAddress.delivery_region_id == int(delivery_region_id))
        )
    return {int(x) for x in db.scalars(q).all()}


def subscription_delivery_started_clause(delivery_date: date):
    """
    起送日门禁（与配送大表、备餐、顺丰推单口径一致）。

    - 已设起送日：仅当 ``delivery_date >= delivery_start_date`` 入选；
    - 起送日为空：仅历史老会员（``delivery_deferred=false``，即日生效）；
    - 新购卡包待完善（``delivery_deferred=true``）即使起送日为空也不入选。
    """
    return or_(
        and_(
            Member.delivery_start_date.is_(None),
            Member.delivery_deferred.is_(False),
        ),
        Member.delivery_start_date <= delivery_date,
    )


def eligible_members_for_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    应配送会员（Member 行）及每人默认地址（与 is_absent_on_delivery_date / 配送清单同一规则）。
    「仅明天请假」相对业务 today（上海），与 delivery_date 比较。
    若会员设置了 delivery_start_date，仅当 delivery_date 不早于该日才入选。
    起送日为空仅历史老会员（未暂停配送）；小程序购卡待完善（paid_card_awaiting_setup）一律排除。
    周日与法定节假日不配送，直接返回空列表（与配送大表、备餐口径一致）。
    普通周六且会员开启「固定周六不履约」时，该会员不进入名单（到家）；与 `store_pickup`/自提同类规则见本模块自提函数。
    单次查询 OUTER JOIN 默认地址；按片区筛选时在 SQL 中过滤，避免「全员查完再内存过滤」的二次往返。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}
    absent = _home_delivery_absent_clause(delivery_date)
    started = subscription_delivery_started_clause(delivery_date)
    units_sql = sql_effective_daily_meal_units_column()
    daf = default_address_pick_subquery()
    q = (
        select(Member, MemberAddress)
        .outerjoin(daf, daf.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
        .where(
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            Member.delivery_deferred.is_(False),
            Member.balance >= units_sql,
            Member.store_pickup.is_(False),
            not_(absent),
            started,
            _member_not_skip_subscription_saturday(delivery_date),
            _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
        )
    )
    if delivery_region_id is not None:
        q = q.where(MemberAddress.delivery_region_id == delivery_region_id)
    rows = db.execute(q).all()
    if not rows:
        return [], {}

    # 批量查询「有小程序自助付款工单」的会员 ID，避免逐条 N+1 查询
    # 原逻辑：有已支付小程序工单 + 履约信息未完善（无起送日 或 无默认地址）则排除
    # 主查询已过滤 store_pickup=False，故只需检查 delivery_start_date 和默认地址
    from app.models.member_card_order import MemberCardOrder
    from app.models.enums import CardOrderPayStatus

    all_member_ids = [int(m.id) for m, _ in rows]
    _has_paid_order_subq = (
        select(MemberCardOrder.member_id)
        .where(
            MemberCardOrder.member_id.in_(all_member_ids),
            MemberCardOrder.created_by == "miniprogram",
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        )
        .distinct()
    )
    has_paid_order_ids: set[int] = {int(r) for r in db.scalars(_has_paid_order_subq).all()}

    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    for m, addr in rows:
        mid = int(m.id)
        if mid in has_paid_order_ids:
            # 履约信息未完善则跳过（store_pickup 已被主查询排除）
            if m.delivery_start_date is None or addr is None:
                continue
        members.append(m)
        defaults[m.id] = addr
    return members, defaults


def _member_subscription_schedule_where(
    delivery_date: date,
    *,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> list:
    """与 eligible_members_for_delivery / store_pickup 相同的日程条件（不含余额门槛）。"""
    today = today_shanghai()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= delivery_date,
        Member.leave_range_end >= delivery_date,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == delivery_date,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(delivery_date) == literal(tomorrow),
    )
    tomorrow_leave_hit = or_(target_hit, legacy_tomorrow)
    absent = or_(in_leave_range, tomorrow_leave_hit)
    started = subscription_delivery_started_clause(delivery_date)
    return [
        Member.deleted_at.is_(None),
        Member.is_active.is_(True),
        Member.delivery_deferred.is_(False),
        not_(absent),
        started,
        _member_not_skip_subscription_saturday(delivery_date),
        _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
    ]


def _member_subscription_eligibility_where(
    delivery_date: date,
    *,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> list:
    """与 eligible_members_for_delivery / store_pickup 相同的会员资格条件（不含地址/片区）。"""
    units_sql = sql_effective_daily_meal_units_column()
    return [
        *_member_subscription_schedule_where(
            delivery_date, tenant_id=tenant_id, store_id=store_id
        ),
        Member.balance >= units_sql,
    ]


def list_members_insufficient_balance_for_delivery_day(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
    meal_period: str = "lunch",
) -> list[Member]:
    """
    当日本应履约（到家或自提），但剩余次数不足以覆盖每配送日份数、故未进配送大表的会员。

    条件：``0 < balance < effective_daily_meal_units`` 且 ``daily_meal_units > 1``。
    meal_period 默认 lunch（现网行为）；dinner 走晚餐次数池。
    """
    from app.models.enums import MealPeriod
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD

    if not is_subscription_delivery_day(delivery_date):
        return []
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    if period == MealPeriod.DINNER.value:
        return _list_dinner_members_insufficient_balance_for_delivery_day(
            db,
            delivery_date=delivery_date,
            tenant_id=tenant_id,
            store_id=store_id,
        )
    units_sql = sql_effective_daily_meal_units_column()
    stmt = (
        select(Member)
        .where(
            *_member_subscription_schedule_where(
                delivery_date, tenant_id=tenant_id, store_id=store_id
            ),
            Member.balance > 0,
            Member.balance < units_sql,
            units_sql > literal(1),
        )
        .order_by(Member.id.asc())
    )
    return list(db.scalars(stmt).all())


def _list_dinner_members_insufficient_balance_for_delivery_day(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> list[Member]:
    """晚餐：0 < dinner_balance < dinner_daily_meal_units 且 dinner_daily_meal_units > 1。"""
    from app.models.enums import DeliverySheetView, MealPeriod
    from app.models.member_meal_period_state import MemberMealPeriodState
    from app.services.meal_period.card_eligibility import member_entitled_for_sheet
    from app.services.meal_period.leave import is_dinner_absent_on_delivery_date
    from app.services.meal_period.units import dinner_daily_meal_units_from_state

    today = today_shanghai()
    started = subscription_delivery_started_clause(delivery_date)
    stmt = (
        select(Member)
        .join(
            MemberMealPeriodState,
            and_(
                MemberMealPeriodState.member_id == Member.id,
                MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
            ),
        )
        .where(
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            Member.delivery_deferred.is_(False),
            Member.store_pickup.is_(False),
            started,
            _member_not_skip_subscription_saturday(delivery_date),
            _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
            MemberMealPeriodState.balance > 0,
        )
        .order_by(Member.id.asc())
    )
    out: list[Member] = []
    for m in db.scalars(stmt).all():
        if not member_entitled_for_sheet(db, int(m.id), DeliverySheetView.DINNER.value):
            continue
        row = db.get(
            MemberMealPeriodState,
            {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
        )
        units = dinner_daily_meal_units_from_state(row)
        if units <= 1:
            continue
        bal = max(0, int(row.balance or 0)) if row else 0
        if bal >= units:
            continue
        if is_dinner_absent_on_delivery_date(row, delivery_date, today=today):
            continue
        out.append(m)
    return out


def sum_subscription_meals_on_date(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> int:
    """当日应配送的会员份数合计（到家+自提）；SQL SUM，不加载会员行与地址。"""
    if not is_subscription_delivery_day(delivery_date):
        return 0
    units_sql = sql_effective_daily_meal_units_column()
    q = select(func.coalesce(func.sum(units_sql), 0)).where(
        *_member_subscription_eligibility_where(
            delivery_date, tenant_id=tenant_id, store_id=store_id
        )
    )
    return int(db.scalar(q) or 0)


def count_members_first_scheduled_delivery_day(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> int:
    """起送业务日恰为 ``delivery_date``，且当日计入配送大表（到家或自提）的会员人数，即「首餐」新客。

    规则与 :func:`eligible_members_for_delivery` / :func:`eligible_members_for_store_pickup` 一致；
    额外限定 ``members.delivery_start_date == delivery_date``（不含起送日为空的即日生效老口径）。
    """
    if not is_subscription_delivery_day(delivery_date):
        return 0
    today = today_shanghai()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= delivery_date,
        Member.leave_range_end >= delivery_date,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == delivery_date,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(delivery_date) == literal(tomorrow),
    )
    tomorrow_leave_hit = or_(target_hit, legacy_tomorrow)
    absent = or_(in_leave_range, tomorrow_leave_hit)
    units_sql = sql_effective_daily_meal_units_column()
    daf = default_address_pick_subquery()
    first_day = Member.delivery_start_date == delivery_date

    def _cnt(*, store_pickup: bool) -> int:
        q = (
            select(func.count())
            .select_from(Member)
            .outerjoin(daf, daf.c.mid == Member.id)
            .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
            .where(
                Member.deleted_at.is_(None),
                Member.is_active.is_(True),
                Member.balance >= units_sql,
                Member.store_pickup.is_(store_pickup),
                not_(absent),
                first_day,
                _member_not_skip_subscription_saturday(delivery_date),
                _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
            )
        )
        return int(db.scalar(q) or 0)

    return _cnt(store_pickup=False) + _cnt(store_pickup=True)


def eligible_members_for_store_pickup(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    当日应备餐的门店自提会员（与 `eligible_members_for_delivery` 相同的请假、起送日、余额规则；
    不按片区过滤；不参与骑手线路。
    普通周六且会员开启「固定周六不履约」时亦不进入本名单。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}
    today = today_shanghai()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= delivery_date,
        Member.leave_range_end >= delivery_date,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == delivery_date,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(delivery_date) == literal(tomorrow),
    )
    tomorrow_leave_hit = or_(target_hit, legacy_tomorrow)
    absent = or_(in_leave_range, tomorrow_leave_hit)
    started = subscription_delivery_started_clause(delivery_date)
    units_sql = sql_effective_daily_meal_units_column()
    daf = default_address_pick_subquery()
    q = (
        select(Member, MemberAddress)
        .outerjoin(daf, daf.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
        .where(
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            Member.delivery_deferred.is_(False),
            Member.balance >= units_sql,
            Member.store_pickup.is_(True),
            not_(absent),
            started,
            _member_not_skip_subscription_saturday(delivery_date),
            _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
        )
    )
    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    for m, addr in db.execute(q).all():
        members.append(m)
        defaults[m.id] = addr
    return members, defaults


def count_expire_one_unit_members_for_business_day(
    db: Session,
    *,
    delivery_date: date,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> int:
    """当日已消费殆尽的末次出餐份数（到家；**份数非人数**，供后厨核对总出餐量）。

    字段名历史沿用 ``*_members``，返回值为餐份数。对锚定日已送达、``balance==0``、``is_active=False``、
    ``store_pickup=False`` 的会员，汇总当日末次配送扣次 ``sum(abs(change))``（``abs(change)==daily_meal_units``）。
    """
    if not is_subscription_delivery_day(delivery_date):
        return 0
    started = subscription_delivery_started_clause(delivery_date)
    units_sql = sql_effective_daily_meal_units_column()
    scope = _member_scope_clause(tenant_id=tenant_id, store_id=store_id)
    saturday = _member_not_skip_subscription_saturday(delivery_date)
    q = (
        select(func.coalesce(func.sum(func.abs(BalanceLog.change)), 0))
        .select_from(BalanceLog)
        .join(Member, Member.id == BalanceLog.member_id)
        .join(
            DeliveryLog,
            and_(
                DeliveryLog.member_id == Member.id,
                DeliveryLog.delivery_date == delivery_date,
                DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            ),
        )
        .where(
            BalanceLog.reason == BalanceReason.DELIVERY.value,
            func.date(BalanceLog.created_at) == delivery_date,
            func.abs(BalanceLog.change) == units_sql,
            Member.deleted_at.is_(None),
            Member.store_pickup.is_(False),
            Member.balance == 0,
            Member.is_active.is_(False),
            started,
            saturday,
            scope,
        )
    )
    return int(db.scalar(q) or 0)


def extra_delivered_ineligible_subscribers(
    db: Session,
    *,
    delivery_date: date,
    already_home: set[int],
    already_pickup: set[int],
    delivery_region_id: int | None,
    tenant_id: int | None = None,
    store_id: int | None = None,
    day_delivered_member_ids: set[int] | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None], list[Member], dict[int, MemberAddress | None]]:
    """
    当日 delivery_logs 已为 DELIVERED，但会员不再满足「应配送/应自提」SQL（常见：扣次后 balance
    低于当日应付份数）而未出现在上一步名单中的会员。补进配送大表与骑手端，使当日已送份数
    与记录可统计、可复核，不从当日视图中消失。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}, [], {}

    if day_delivered_member_ids is not None:
        log_ids = set(day_delivered_member_ids)
    else:
        log_ids = {
            int(x)
            for x in db.scalars(
                select(DeliveryLog.member_id)
                .distinct()
                .join(Member, Member.id == DeliveryLog.member_id)
                .where(
                    DeliveryLog.delivery_date == delivery_date,
                    DeliveryLog.status == DeliveryStatus.DELIVERED.value,
                    _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
                )
            ).all()
        }
    need = log_ids - already_home - already_pickup
    if not need:
        return [], {}, [], {}

    rows = list(
        db.scalars(
            select(Member).where(
                Member.id.in_(need),
                _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
            )
        ).all()
    )
    if not rows:
        return [], {}, [], {}

    mid_list = [int(m.id) for m in rows]
    defaults = load_default_address_map(db, mid_list)
    out_home: list[Member] = []
    out_pu: list[Member] = []
    d_home: dict[int, MemberAddress | None] = {}
    d_pu: dict[int, MemberAddress | None] = {}
    for m in rows:
        mid = int(m.id)
        addr = defaults.get(mid)
        if m.store_pickup:
            out_pu.append(m)
            d_pu[mid] = addr
            continue
        if delivery_region_id is not None and (
            addr is None
            or addr.delivery_region_id is None
            or int(addr.delivery_region_id) != int(delivery_region_id)
        ):
            continue
        out_home.append(m)
        d_home[mid] = addr
    return out_home, d_home, out_pu, d_pu


def list_today_tasks(
    db: Session,
    *,
    delivery_region_id: int,
    delivery_region_display: str,
    delivery_date: date | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> list[CourierTaskMemberOut]:
    """
    当日配送清单：
    - is_active 且 balance>=当日应付份数（daily_meal_units，封顶 50）；
    - 若设置了 delivery_start_date，仅当配送日>=该日；
    - 配送日不在请假区间，且「明天请假」不影响「今日」配送；
    - 周日与法定节假日不生成订阅清单；
    - 按 delivery_region_id 过滤默认地址；
    - 组内从门店（或质心）出发按最近邻贪心排序停留点，减少折返。
    - 当日已送达后余额不足、不再入选应送名单的会员，仍从 delivery_logs 补入本清单（与配送大表一致），便于对账。
    """
    d = delivery_date or today_shanghai()
    from app.services.meal_period.lunch_delivery import eligible_members_for_lunch_delivery

    eligible, defaults = eligible_members_for_lunch_delivery(
        db,
        delivery_date=d,
        delivery_region_id=delivery_region_id,
        tenant_id=tenant_id,
        store_id=store_id,
    )
    pu_list, _pu_def = eligible_members_for_store_pickup(
        db, delivery_date=d, tenant_id=tenant_id, store_id=store_id
    )
    ex_h, ex_d, _ex_pu, _ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home={int(m.id) for m in eligible},
        already_pickup={int(m.id) for m in pu_list},
        delivery_region_id=delivery_region_id,
        tenant_id=tenant_id,
        store_id=store_id,
    )
    for m in ex_h:
        eligible.append(m)
        defaults[m.id] = ex_d.get(int(m.id))

    mids = [m.id for m in eligible]
    delivered_ids: set[int] = set()
    if mids:
        delivered_ids = set(
            db.scalars(
                select(DeliveryLog.member_id).where(
                    DeliveryLog.delivery_date == d,
                    DeliveryLog.status == DeliveryStatus.DELIVERED.value,
                    DeliveryLog.member_id.in_(mids),
                )
            ).all()
        )

    if store_id is not None:
        store_lng, store_lat = load_store_coordinates_for_sorting(db, store_id=int(store_id))
    elif tenant_id is not None:
        store_lng, store_lat = load_store_coordinates_for_sorting(db, tenant_id=int(tenant_id))
    else:
        store_lng, store_lat = load_store_coordinates_for_sorting(db)
    ref_lng, ref_lat = reference_lng_lat_for_task_sorting(store_lng, store_lat, eligible, defaults)
    rows: list[CourierTaskMemberOut] = []
    ar = delivery_region_display
    for m in eligible:
        addr = defaults.get(m.id)
        dist = distance_from_anchor_m(
            ref_lng,
            ref_lat,
            float(addr.lng) if addr is not None and addr.lng is not None else None,
            float(addr.lat) if addr is not None and addr.lat is not None else None,
        )
        detail = full_address_line(addr.map_location_text, addr.door_detail) if addr else ""
        display_addr = f"{ar} {detail}".strip() or "（未设置默认配送地址）"
        units = effective_daily_meal_units(m)
        rows.append(
            CourierTaskMemberOut(
                member_id=m.id,
                phone=m.phone,
                name=m.name,
                address=display_addr,
                lng=float(addr.lng) if addr is not None and addr.lng is not None else None,
                lat=float(addr.lat) if addr is not None and addr.lat is not None else None,
                area=ar,
                remarks=m.remarks,
                daily_meal_units=units,
                sort_distance_m=dist,
                is_delivered=m.id in delivered_ids,
            )
        )
    order_task_rows_by_nearest_neighbor(rows, ref_lng, ref_lat)
    return rows


def list_tasks_for_courier(
    db: Session,
    courier_id: str,
    *,
    delivery_date: date | None = None,
) -> tuple[list[CourierTaskMemberOut], date]:
    """当日任务：仅包含该配送员在 delivery_region_couriers 中绑定的片区。"""
    d = delivery_date or today_shanghai()
    c_row = db.get(Courier, courier_id)
    tid = int(c_row.tenant_id) if c_row is not None else None
    from app.services.delivery.courier_store_scope import resolve_courier_task_store_id

    task_store_id = resolve_courier_task_store_id(db, tenant_id=tid)
    regions = regions_for_courier(db, courier_id)
    if not regions:
        singles = list_courier_single_order_tasks(db, courier_id, d)
        return singles, d
    by_member: dict[int, CourierTaskMemberOut] = {}
    for reg in regions:
        rname = (reg.name or "").strip() or UNASSIGNED_DELIVERY_AREA
        for row in list_today_tasks(
            db,
            delivery_region_id=int(reg.region_id),
            delivery_region_display=rname,
            delivery_date=d,
            tenant_id=tid,
            store_id=task_store_id,
        ):
            by_member[row.member_id] = row
    out = list(by_member.values())
    singles = list_courier_single_order_tasks(db, courier_id, d)
    out.extend(singles)
    store_lng, store_lat = (
        load_store_coordinates_for_sorting(db, tenant_id=tid)
        if tid is not None
        else load_store_coordinates_for_sorting(db)
    )
    depot_lng, depot_lat = (
        (float(store_lng), float(store_lat))
        if store_lng is not None and store_lat is not None
        else centroid_from_task_rows(out)
    )
    order_task_rows_by_nearest_neighbor(out, depot_lng, depot_lat)
    return out, d


def group_task_rows(rows: list[CourierTaskMemberOut]) -> list[dict]:
    grouped: dict[str, list] = defaultdict(list)
    for m in rows:
        grouped[m.area].append(m.model_dump(mode="json"))
    return [{"area": k, "items": grouped[k]} for k in sorted(grouped.keys())]


def confirm_delivery(db: Session, courier_id: str, member_id: int, delivery_date: date | None) -> None:
    """
    确认送达：单事务内完成流水 + 扣次 + 余额流水；已送达则幂等返回。
    """
    d = delivery_date or today_shanghai()
    today = today_shanghai()

    member = db.execute(select(Member).where(Member.id == member_id).with_for_update()).scalar_one_or_none()
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    courier_row = db.get(Courier, courier_id)
    if not courier_row:
        raise HTTPException(status_code=500, detail="配送员账户异常")
    if int(member.tenant_id) != int(courier_row.tenant_id):
        raise HTTPException(status_code=403, detail="无权操作该会员")

    from app.models.enums import DeliverySheetView
    from app.services.meal_period.card_eligibility import member_entitled_for_sheet

    if not member_entitled_for_sheet(db, int(member.id), DeliverySheetView.LUNCH.value):
        raise HTTPException(status_code=400, detail="该会员无午餐配送资格，晚餐请由管理端或顺丰履约")

    allowed_region_ids = {int(r.region_id) for r in regions_for_courier(db, courier_id)}
    if not allowed_region_ids:
        raise HTTPException(status_code=403, detail="账号未分配配送片区")
    da = load_default_address_map(db, [member_id]).get(member_id)
    ma_rid = int(da.delivery_region_id) if da and da.delivery_region_id is not None else None
    if ma_rid is None or ma_rid not in allowed_region_ids:
        raise HTTPException(status_code=403, detail="该会员不在您负责的片区")

    deduct = effective_daily_meal_units(member)
    if not member.is_active or member.balance <= 0:
        raise HTTPException(status_code=400, detail="用户未激活或次数不足")
    if member.balance < deduct:
        raise HTTPException(status_code=400, detail="次数不足，无法满足当日份数扣减")
    if is_absent_on_delivery_date(member, d, today=today):
        raise HTTPException(status_code=400, detail="该日用户请假，无法确认送达")
    if member.delivery_start_date is not None and d < member.delivery_start_date:
        raise HTTPException(status_code=400, detail="未到约定的开始配送日，无法确认送达")
    if not is_subscription_delivery_day(d):
        raise HTTPException(status_code=400, detail="该日为周日或法定节假日，订阅配送不履约")
    if d.weekday() == 5 and bool(member.skip_subscription_saturday):
        raise HTTPException(status_code=400, detail="该会员固定周六不参与订阅履约，无法确认送达")

    log = db.execute(
        select(DeliveryLog)
        .where(
            DeliveryLog.member_id == member_id,
            DeliveryLog.delivery_date == d,
            DeliveryLog.meal_period == "lunch",
        )
        .with_for_update()
    ).scalar_one_or_none()

    if log and log.status == DeliveryStatus.DELIVERED.value:
        return

    if log and log.status == DeliveryStatus.LEAVE.value:
        raise HTTPException(status_code=400, detail="该日记录为请假状态")

    if not log:
        log = DeliveryLog(
            member_id=member_id,
            delivery_date=d,
            meal_period="lunch",
            status=DeliveryStatus.DELIVERED.value,
            courier_id=courier_id,
        )
        db.add(log)
    else:
        log.status = DeliveryStatus.DELIVERED.value
        log.courier_id = courier_id

    member.balance -= deduct
    balance_before = int(member.balance) + int(deduct)
    from app.services.meal_period.balance import sync_member_is_active_from_period_balances

    sync_member_is_active_from_period_balances(db, member)
    db.add(
        BalanceLog(
            member_id=member_id,
            meal_period="lunch",
            change=-deduct,
            reason=BalanceReason.DELIVERY.value,
            operator=f"courier:{courier_id}",
            detail=None,
        )
    )
    fee_yuan = courier_delivery_fee_yuan_for_meal_units(db, deduct, store_id=int(member.store_id))
    courier_row = db.execute(select(Courier).where(Courier.courier_id == courier_id).with_for_update()).scalar_one_or_none()
    if not courier_row:
        raise HTTPException(status_code=500, detail="配送员账户异常")
    prev = courier_row.fee_pending if courier_row.fee_pending is not None else Decimal("0.00")
    courier_row.fee_pending = prev + fee_yuan
    db.commit()
    from app.services.member.member_renew_subscribe_service import try_send_renew_remind_after_balance_change

    try_send_renew_remind_after_balance_change(db, member, balance_before=balance_before)
    if db.new or db.dirty or db.deleted:
        db.commit()
