from datetime import date, timedelta



from fastapi import HTTPException

from sqlalchemy import func, literal, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session



from app.core.timeutil import (
    min_member_delivery_start_shanghai,
    now_shanghai,
    today_shanghai,
    tomorrow_shanghai,
)

from app.models.menu_dish import MenuDish

from app.models.menu_schedule import MenuSchedule

from app.models.weekly_menu_slot import WeeklyMenuSlot

from app.constants import STUB_MEMBER_NAME, UNASSIGNED_DELIVERY_AREA

from app.models.balance_log import BalanceLog

from app.models.enums import BalanceReason, LeaveType, PlanType

from app.models.member import Member

from app.models.member_address import MemberAddress

from app.schemas.user import Location, MemberOut, RegisterIn

from app.services import amap

from app.services.leave import is_leave_deadline_passed

from app.services.member_address_service import (
    admin_apply_manual_delivery_region,
    admin_set_default_address_detail,
    apply_auto_area_from_coords_or_geocode,
    delivery_region_name_map,
    get_default_address,
    upsert_default_address_after_register,
)

from app.services.region_assignment import assign_region_for_coords
from app.services.store_config_service import ensure_app_settings_row

# 与 DB chk_members_daily_meal_units 上限一致
MAX_DAILY_MEAL_UNITS = 50


def effective_daily_meal_units(m: Member) -> int:
    """每配送日份数：备餐、清单与扣次用（非法值按 1，封顶 MAX_DAILY_MEAL_UNITS）。"""

    try:
        u = int(m.daily_meal_units)
    except (TypeError, ValueError):
        return 1
    return max(1, min(u, MAX_DAILY_MEAL_UNITS))


def sql_effective_daily_meal_units_column():
    """与 effective_daily_meal_units 一致的 SQL 列表达式（用于 eligibility / SUM）。"""

    return func.least(
        literal(MAX_DAILY_MEAL_UNITS),
        func.greatest(literal(1), func.coalesce(Member.daily_meal_units, 1)),
    )


def _member_by_phone(db: Session, phone: str) -> Member | None:

    return db.scalar(select(Member).where(Member.phone == phone, Member.deleted_at.is_(None)))





def _is_placeholder_profile(db: Session, m: Member) -> bool:

    """占位档案：仍为占位姓名且无默认配送地址。"""

    if m.name != STUB_MEMBER_NAME:

        return False

    return get_default_address(db, m.id) is None





def ensure_member_stub(
    db: Session,
    phone: str,
    *,
    wx_mini_openid: str | None = None,
) -> int:

    """登录成功时保证存在会员行；返回 members.id 用于签发 JWT。

    仅按手机号解析 id，避免加载整行（与历史库结构更易兼容）。

    微信登录可对已存在会员更新 wx_mini_openid；新号则创建占位档案并写入 openid。
    """

    row_id = db.scalar(select(Member.id).where(Member.phone == phone, Member.deleted_at.is_(None)))

    if row_id is not None:

        mid = int(row_id)

        if wx_mini_openid:

            db.execute(

                update(Member)

                .where(Member.id == mid)

                .values(wx_mini_openid=wx_mini_openid)

            )

            db.commit()

        return mid

    member = Member(

        phone=phone,

        name=STUB_MEMBER_NAME,

        remarks=None,

        avatar_url=None,

        balance=0,

        daily_meal_units=1,

        plan_type=None,

        is_active=False,

        is_leaved_tomorrow=False,

        leave_range_start=None,

        leave_range_end=None,

        wx_mini_openid=wx_mini_openid,

    )

    db.add(member)

    db.commit()

    db.refresh(member)

    return member.id





def _to_member_out(
    db: Session,
    m: Member,
    default_addr: MemberAddress | None = None,
) -> MemberOut:

    """会员对外资料：地址/坐标/片区以默认配送地址为准。"""

    loc = None

    address_line = ""

    area_name = UNASSIGNED_DELIVERY_AREA

    if default_addr is not None:

        address_line = (default_addr.detail_address or "").strip()

        if default_addr.delivery_region_id is not None:

            nm = delivery_region_name_map(db, {int(default_addr.delivery_region_id)})

            area_name = nm.get(int(default_addr.delivery_region_id), UNASSIGNED_DELIVERY_AREA)

        if default_addr.lng is not None and default_addr.lat is not None:

            loc = Location(lng=float(default_addr.lng), lat=float(default_addr.lat))

    lr = None

    if m.leave_range_start or m.leave_range_end:

        lr = {"start": m.leave_range_start, "end": m.leave_range_end}

    settings_row = ensure_app_settings_row(db)
    ldt = settings_row.leave_deadline_time
    leave_deadline_str = ldt.isoformat() if ldt is not None else "21:00:00"

    plan_out: PlanType | None = None

    if m.plan_type:

        try:

            plan_out = PlanType(m.plan_type)

        except ValueError:

            plan_out = None



    return MemberOut(

        id=m.id,

        phone=m.phone,

        name=m.name,

        wechat_name=m.wechat_name,

        address=address_line,

        avatar_url=m.avatar_url,

        location=loc,

        area=area_name,

        remarks=m.remarks,

        balance=m.balance,

        daily_meal_units=effective_daily_meal_units(m),

        meal_quota_total=m.meal_quota_total,

        plan_type=plan_out,

        delivery_start_date=m.delivery_start_date,

        delivery_deferred=bool(m.delivery_deferred),

        store_pickup=bool(m.store_pickup),

        is_active=m.is_active,

        is_leaved_tomorrow=m.is_leaved_tomorrow,

        tomorrow_leave_target_date=m.tomorrow_leave_target_date,

        leave_range=lr,

        leave_deadline_time=leave_deadline_str,

        created_at=m.created_at.isoformat() if m.created_at else "",

    )





def get_member(db: Session, member_id: int) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    return _to_member_out(db, m, get_default_address(db, member_id))





def register_member(db: Session, body: RegisterIn) -> MemberOut:

    existing = _member_by_phone(db, body.phone)

    if existing and not _is_placeholder_profile(db, existing):

        raise HTTPException(status_code=409, detail="该手机号已注册")

    coords = amap.geocode_address(body.address)

    if coords:

        lng, lat = coords[0], coords[1]

        r = assign_region_for_coords(db, lng, lat)

        rid = int(r.id) if r else None

    else:

        lng, lat, rid = None, None, None

    if existing:

        existing.name = body.name

        existing.remarks = body.remarks

        if body.avatar_url is not None:

            existing.avatar_url = body.avatar_url

        upsert_default_address_after_register(

            db,

            member_id=existing.id,

            contact_name=body.name,

            contact_phone=body.phone,

            detail_address=body.address,

            remarks=body.remarks,

            delivery_region_id=rid,

            lng=lng,

            lat=lat,

        )

        db.commit()

        db.refresh(existing)

        return _to_member_out(db, existing, get_default_address(db, existing.id))

    member = Member(

        phone=body.phone,

        name=body.name,

        remarks=body.remarks,

        avatar_url=body.avatar_url,

        balance=0,

        daily_meal_units=1,

        plan_type=None,

        is_active=False,

        is_leaved_tomorrow=False,

        leave_range_start=None,

        leave_range_end=None,

    )

    db.add(member)

    db.commit()

    db.refresh(member)

    upsert_default_address_after_register(

        db,

        member_id=member.id,

        contact_name=body.name,

        contact_phone=body.phone,

        detail_address=body.address,

        remarks=body.remarks,

        delivery_region_id=rid,

        lng=lng,

        lat=lat,

    )

    db.commit()

    db.refresh(member)

    return _to_member_out(db, member, get_default_address(db, member.id))





def patch_member_profile(

    db: Session,

    member_id: int,

    *,

    set_avatar: bool = False,

    avatar_url: str | None = None,

    set_wechat_name: bool = False,

    wechat_name: str | None = None,

    set_name: bool = False,

    name: str | None = None,

    set_plan_type: bool = False,

    plan_type: PlanType | None = None,

    set_delivery_start: bool = False,

    delivery_start_date: date | None = None,

    set_delivery_deferred: bool = False,

    delivery_deferred: bool | None = None,

    card_pay_mode: str | None = None,

    set_store_pickup: bool = False,

    store_pickup: bool | None = None,

    set_daily_meal_units: bool = False,

    daily_meal_units: int | None = None,

) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    if set_daily_meal_units and daily_meal_units is not None:

        u = int(daily_meal_units)

        if u < 1 or u > 20:

            raise HTTPException(status_code=400, detail="每日送达数量须为 1～20")

        m.daily_meal_units = u

    if set_avatar:

        m.avatar_url = avatar_url

    if set_wechat_name:

        m.wechat_name = wechat_name

        if wechat_name and m.name == STUB_MEMBER_NAME:

            m.name = wechat_name[:100]

    if set_name and name is not None:

        t = str(name).strip()[:100]

        if t and m.name == STUB_MEMBER_NAME:

            m.name = t

    if set_plan_type:

        new_val = plan_type.value if plan_type is not None else None

        m.plan_type = new_val

    defer_applied = set_delivery_deferred and delivery_deferred is True

    if defer_applied:

        m.delivery_deferred = True

        m.is_active = False

        m.delivery_start_date = None

        m.store_pickup = False

    elif set_delivery_deferred and delivery_deferred is False:

        m.delivery_deferred = False

    if set_store_pickup and store_pickup is not None:

        m.store_pickup = bool(store_pickup)

        if m.store_pickup:

            m.delivery_deferred = False

    if set_delivery_start and not defer_applied:

        if delivery_start_date is not None:

            if delivery_start_date < min_member_delivery_start_shanghai():

                raise HTTPException(
                    status_code=400,
                    detail="起送日期须不早于允许的最小业务日（上海；当日 10:00 前最早今天，10:00 及之后最早明天）",
                )

            m.delivery_start_date = delivery_start_date

            m.delivery_deferred = False

            if m.balance > 0:

                m.is_active = True

        else:

            m.delivery_start_date = None

    want_offline = (card_pay_mode or "").strip() == "offline_paid"

    if want_offline and int(m.balance) > 0:

        raise HTTPException(status_code=400, detail="仅剩余次数为 0 时可登记线下已缴开卡")

    if want_offline:

        m.is_active = False

    if want_offline and not defer_applied:

        if m.delivery_start_date is None:

            raise HTTPException(

                status_code=400,

                detail="已支付(线下)时须先选择起送日；或改为「暂不配送」",

            )

        if (m.plan_type or "") not in ("周卡", "月卡", "次卡"):

            raise HTTPException(

                status_code=400,

                detail="已支付(线下)时须选择周卡、月卡或次卡",

            )

        from app.services.member_card_order_service import (

            ensure_miniprogram_offline_claim_order,

        )

        ensure_miniprogram_offline_claim_order(

            db,

            member_id,

            card_kind=str(m.plan_type).strip(),

            delivery_start_date=m.delivery_start_date,

        )

    db.commit()

    db.refresh(m)

    return _to_member_out(db, m, get_default_address(db, member_id))





def activate_member(db: Session, member_id: int) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    m.is_active = True

    m.delivery_deferred = False

    db.commit()

    db.refresh(m)

    return _to_member_out(db, m, get_default_address(db, member_id))





def leave_request(
    db: Session,
    member_id: int,
    typ: LeaveType,
    start: date | None,
    end: date | None,
    *,
    skip_leave_deadline: bool = False,
) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")



    settings_row = ensure_app_settings_row(db)



    now = now_shanghai()



    if typ == LeaveType.CANCEL:

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

        m.leave_range_start = None

        m.leave_range_end = None

    elif typ == LeaveType.CLEAR_TOMORROW:

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

    elif typ == LeaveType.TOMORROW:

        if not skip_leave_deadline and is_leave_deadline_passed(
            now.time(), settings_row.leave_deadline_time
        ):

            raise HTTPException(status_code=400, detail="已超过当日请假截止时间")

        t_target = tomorrow_shanghai()

        m.tomorrow_leave_target_date = t_target

        m.is_leaved_tomorrow = True

    elif typ == LeaveType.RANGE:

        if not skip_leave_deadline and is_leave_deadline_passed(
            now.time(), settings_row.leave_deadline_time
        ):

            raise HTTPException(status_code=400, detail="已超过当日请假截止时间")

        if not start or not end:

            raise HTTPException(status_code=400, detail="区间请假需提供 start 与 end")

        if end < start:

            raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

        m.leave_range_start = start

        m.leave_range_end = end

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

    else:

        raise HTTPException(status_code=400, detail="不支持的请假类型")



    db.commit()

    db.refresh(m)

    return _to_member_out(db, m, get_default_address(db, member_id))


def admin_member_leave(
    db: Session,
    *,
    phone: str,
    typ: LeaveType,
    start: date | None,
    end: date | None,
) -> MemberOut:
    """管理端代会员设置请假：不校验当日 `leave_deadline_time`（小程序端提交「明天/区间」仍受截止限制）。"""

    p = (phone or "").strip()
    m = _member_by_phone(db, p)
    if not m:
        raise HTTPException(status_code=404, detail="用户不存在")
    return leave_request(db, m.id, typ, start, end, skip_leave_deadline=True)


def _week_start_and_slot(d: date) -> tuple[date, int]:

    return _monday_of_week(d), d.weekday() + 1





def _by_date_from_weekly_rows(rows: list[tuple[WeeklyMenuSlot, MenuDish]]) -> dict[date, MenuDish]:

    by_date: dict[date, MenuDish] = {}

    for ws, dish in rows:

        day = ws.week_start + timedelta(days=ws.slot - 1)

        by_date[day] = dish

    return by_date





def get_tomorrow_menu(db: Session) -> dict:

    d = tomorrow_shanghai()

    ws, slot = _week_start_and_slot(d)

    row = db.execute(

        select(WeeklyMenuSlot, MenuDish)

        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)

        .where(WeeklyMenuSlot.week_start == ws, WeeklyMenuSlot.slot == slot)

    ).first()

    if row:

        _, dish = row

        return {

            "date": d.isoformat(),

            "dish_id": dish.id,

            "title": dish.name,

            "desc": dish.description,

            "pic": dish.image_url,

            "price": _member_menu_price(dish),

        }

    row2 = db.execute(

        select(MenuSchedule, MenuDish)

        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)

        .where(MenuSchedule.menu_date == d)

    ).first()

    if not row2:

        return {

            "date": d.isoformat(),

            "dish_id": None,

            "title": None,

            "desc": None,

            "pic": None,

            "price": None,

        }

    _, dish = row2

    return {

        "date": d.isoformat(),

        "dish_id": dish.id,

        "title": dish.name,

        "desc": dish.description,

        "pic": dish.image_url,

        "price": _member_menu_price(dish),

    }





def _monday_of_week(d: date) -> date:

    return d - timedelta(days=d.weekday())





def _member_menu_price(dish: MenuDish | None) -> float | None:

    if dish is None or dish.single_order_price_yuan is None:

        return None

    return float(dish.single_order_price_yuan)





def _dish_to_member_card(*, menu_date: date, dish: MenuDish | None, slot: int | None = None) -> dict:

    o: dict = {

        "date": menu_date.isoformat(),

        "dish_id": dish.id if dish else None,

        "pic": dish.image_url if dish else None,

        "title": dish.name if dish else None,

        "desc": dish.description if dish else None,

        "price": _member_menu_price(dish),

    }

    if slot is not None:

        o["slot"] = slot

    return o





def get_weekly_menu(db: Session, week_start: date | None) -> dict:

    anchor = _monday_of_week(week_start) if week_start else _monday_of_week(today_shanghai())

    dates = [anchor + timedelta(days=i) for i in range(7)]

    weekly_rows = db.execute(

        select(WeeklyMenuSlot, MenuDish)

        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)

        .where(WeeklyMenuSlot.week_start == anchor)

    ).all()

    by_date = _by_date_from_weekly_rows(list(weekly_rows))

    missing = [x for x in dates if x not in by_date]

    if missing:

        sched_rows = db.execute(

            select(MenuSchedule, MenuDish)

            .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)

            .where(MenuSchedule.menu_date.in_(missing))

        ).all()

        for sched, dish in sched_rows:

            by_date[sched.menu_date] = dish

    items = [

        _dish_to_member_card(menu_date=d, dish=by_date.get(d), slot=i + 1) for i, d in enumerate(dates)

    ]

    return {"week_start": anchor.isoformat(), "items": items}





def get_menu_detail_by_dish_id(db: Session, dish_id: int, *, service_date: date | None = None) -> dict:

    dish = db.get(MenuDish, dish_id)

    if not dish:

        raise HTTPException(status_code=404, detail="餐品不存在")

    out: dict = {

        "dish_id": dish.id,

        "title": dish.name,

        "desc": dish.description,

        "pic": dish.image_url,

        "is_enabled": dish.is_enabled,

        "category_id": dish.category_id,

        "price": _member_menu_price(dish),

    }
    if service_date is not None:
        from app.services.menu_day_stock_service import single_order_stock_for_dish_date

        out.update(single_order_stock_for_dish_date(db, int(dish_id), service_date).to_detail_dict())

    return out





def admin_update_member_address(db: Session, phone: str, address: str, *, operator: str) -> MemberOut:

    _ = operator

    m = _member_by_phone(db, phone)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    admin_set_default_address_detail(

        db,

        member_id=m.id,

        detail_line=address,

        contact_name=m.name,

        contact_phone=m.phone,

    )

    db.commit()

    db.refresh(m)

    return _to_member_out(db, m, get_default_address(db, m.id))





def admin_patch_member_profile(

    db: Session,

    *,

    phone: str,

    name: str | None,

    remarks: str | None,

    address: str | None,

    use_auto_area: bool,

    operator: str,

    daily_meal_units: int | None = None,

    plan_type: PlanType | None = None,

    set_balance: bool = False,

    balance: int | None = None,

    set_delivery_start_date: bool = False,

    delivery_start_date: date | None = None,

    set_store_pickup: bool = False,

    store_pickup: bool | None = None,

    set_delivery_region_id: bool = False,

    delivery_region_id: int | None = None,

    set_delivery_deferred: bool = False,

    delivery_deferred: bool | None = None,

    set_remarks: bool = False,

) -> MemberOut:

    _ = operator

    if (

        name is None

        and not set_remarks

        and address is None

        and daily_meal_units is None

        and plan_type is None

        and not use_auto_area

        and not set_balance

        and not set_delivery_start_date

        and not set_store_pickup

        and not set_delivery_region_id

        and not set_delivery_deferred

    ):

        raise HTTPException(status_code=400, detail="请至少修改一项内容")

    m = _member_by_phone(db, phone)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    mid = m.id

    if name is not None:

        t = name.strip()

        if not t:

            raise HTTPException(status_code=400, detail="姓名不能为空")

        m.name = t

    if set_remarks:

        m.remarks = (remarks or "").strip() or None

    if address is not None:

        t = address.strip()

        if not t:

            raise HTTPException(status_code=400, detail="地址不能为空")

        admin_set_default_address_detail(

            db,

            member_id=mid,

            detail_line=t,

            contact_name=m.name,

            contact_phone=m.phone,

        )

        # 新建默认地址时尚未 flush，后续 get_default_address（自动/手动划区）可能查不到 pending 行
        db.flush()

    if use_auto_area:

        addr = get_default_address(db, mid)

        if not addr:

            raise HTTPException(status_code=400, detail="该会员暂无默认配送地址，无法自动划区")

        apply_auto_area_from_coords_or_geocode(db, addr)

    elif set_delivery_region_id:

        admin_apply_manual_delivery_region(

            db,

            member_id=mid,

            delivery_region_id=delivery_region_id,

        )

    if set_balance:

        if balance is None:

            raise HTTPException(status_code=400, detail="剩余次数不能为空")

        new_b = int(balance)

        if new_b < 0 or new_b > 999_999:

            raise HTTPException(status_code=400, detail="剩余次数超出允许范围")

        old_b = int(m.balance)

        if new_b != old_b:

            delta = new_b - old_b

            m.balance = new_b

            op = (operator or "").strip()[:50] or "admin"

            detail = f"档案修改 {old_b}→{new_b}"

            # 与仅含 recharge/delivery/refund 的历史库 ENUM 兼容；正差额→recharge，负差额→refund，见 detail
            log_reason = (
                BalanceReason.RECHARGE.value if delta > 0 else BalanceReason.REFUND.value
            )

            db.add(

                BalanceLog(

                    member_id=m.id,

                    change=delta,

                    reason=log_reason,

                    operator=op,

                    detail=detail[:500],

                )

            )

        if new_b > 0:

            m.is_active = True

        else:

            m.is_active = False

    if set_delivery_start_date:

        if delivery_start_date is not None:

            m.delivery_start_date = delivery_start_date

            m.delivery_deferred = False

            if int(m.balance) > 0:

                m.is_active = True

        else:

            m.delivery_start_date = None

    if set_store_pickup:

        if store_pickup is None:

            raise HTTPException(status_code=400, detail="门店自提标记不能为空")

        m.store_pickup = bool(store_pickup)

    if set_delivery_deferred:

        if delivery_deferred is None:

            raise HTTPException(status_code=400, detail="暂停配送(会员卡停用)状态不能为空")

        if delivery_deferred:

            m.delivery_deferred = True

            m.is_active = False

            m.delivery_start_date = None

            m.store_pickup = False

        else:

            m.delivery_deferred = False

            m.is_active = int(m.balance) > 0

    if daily_meal_units is not None:
        if daily_meal_units < 1 or daily_meal_units > MAX_DAILY_MEAL_UNITS:
            raise HTTPException(
                status_code=400,
                detail=f"每配送日份数须在 1～{MAX_DAILY_MEAL_UNITS} 之间",
            )
        m.daily_meal_units = daily_meal_units

    if plan_type is not None:
        m.plan_type = plan_type.value

    try:
        db.commit()
        db.refresh(m)
    except OperationalError as e:
        db.rollback()
        err_txt = (str(e.orig) if getattr(e, "orig", None) else str(e)).lower()
        if "daily_meal_units" in err_txt or "unknown column" in err_txt:
            raise HTTPException(
                status_code=400,
                detail="数据库尚未添加 daily_meal_units 字段，请在业务库执行 sql/migration_026_members_daily_meal_units.sql 后重试",
            ) from e
        raise

    return _to_member_out(db, m, get_default_address(db, mid))

