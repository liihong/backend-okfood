from datetime import date, timedelta



from fastapi import HTTPException

from sqlalchemy import func, literal, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session



from app.core.timeutil import (
    min_leave_start_shanghai,
    min_member_delivery_start_shanghai,
    now_shanghai,
    today_shanghai,
    tomorrow_shanghai,
)

from app.models.menu_dish import MenuDish, SPICE_LEVEL_MEMBER_LABELS

from app.models.menu_schedule import MenuSchedule

from app.models.store import Store

from app.models.weekly_menu_slot import WeeklyMenuSlot

from app.constants import STUB_MEMBER_NAME, UNASSIGNED_DELIVERY_AREA

from app.models.balance_log import BalanceLog

from app.models.enums import BalanceReason, LeaveType, PlanType

from app.models.member import Member

from app.models.member_address import MemberAddress

from app.schemas.user import Location, MemberOut, RegisterIn

from app.services import amap

from app.services.admin_system_notification_service import try_notify_delivery_sheet_manual_attention


from app.services.leave import (
    guard_member_self_leave_during_sf_fulfillment,
    guard_member_self_service_during_sf_fulfillment,
    is_absent_from_leave_snapshot_dict,
    is_absent_on_delivery_date,
)

from app.services.member_address_service import (
    admin_apply_manual_delivery_region,
    admin_set_default_address_plain_line,
    apply_auto_area_from_coords_or_geocode,
    delivery_region_name_map,
    full_address_line,
    get_default_address,
    upsert_default_address_after_register,
)

from app.services.member_operation_log_service import (
    OP_ADMIN_UPDATE_ADDRESS,
    OP_ADMIN_UPDATE_BALANCE,
    OP_ADMIN_UPDATE_DELIVERY_REGION,
    OP_ADMIN_UPDATE_NAME,
    OP_ADMIN_UPDATE_PLAN_TYPE,
    OP_ADMIN_UPDATE_REMARKS,
    OP_ADMIN_UPDATE_SKIP_SATURDAY,
    OP_LEAVE_CANCEL,
    OP_LEAVE_CLEAR_TOMORROW,
    OP_LEAVE_RANGE,
    OP_LEAVE_TOMORROW,
    OP_PAUSE_DELIVERY,
    OP_RESUME_DELIVERY,
    OP_UPDATE_DAILY_UNITS,
    OP_UPDATE_DELIVERY_START,
    OP_UPDATE_STORE_PICKUP,
    record_member_operation,
)
from app.services.region_assignment import assign_region_for_coords
from app.services.store_config_service import ensure_app_settings_row


def _blocked_today_by_delivery_start_snapshot(delivery_start_iso: str | None, *, today: date) -> bool:
    """与 ``eligible_members_for_delivery`` 中 started 条件对齐：有起送日且晚于业务日则当日不算起送。"""
    if delivery_start_iso is None:
        return False
    try:
        ds = date.fromisoformat(str(delivery_start_iso).strip()[:10])
    except ValueError:
        return False
    return ds > today

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


def _member_by_phone(db: Session, phone: str, store_id: int) -> Member | None:

    return db.scalar(
        select(Member).where(
            Member.phone == phone,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    )





def _is_placeholder_profile(db: Session, m: Member) -> bool:

    """占位档案：仍为占位姓名且无默认配送地址。"""

    if m.name != STUB_MEMBER_NAME:

        return False

    return get_default_address(db, m.id) is None





def ensure_member_stub(
    db: Session,
    phone: str,
    *,
    tenant_id: int,
    store_id: int,
    wx_mini_openid: str | None = None,
) -> int:

    """登录成功时保证存在会员行；返回 members.id 用于签发 JWT。

    手机号与 openid 均在同一门店内唯一；微信登录可更新 openid。
    """

    row_id = db.scalar(
        select(Member.id).where(
            Member.phone == phone,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    )

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

        tenant_id=int(tenant_id),

        store_id=int(store_id),

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

        address_line = full_address_line(default_addr.map_location_text, default_addr.door_detail)

        if default_addr.delivery_region_id is not None:

            nm = delivery_region_name_map(db, {int(default_addr.delivery_region_id)})

            area_name = nm.get(int(default_addr.delivery_region_id), UNASSIGNED_DELIVERY_AREA)

        if default_addr.lng is not None and default_addr.lat is not None:

            loc = Location(lng=float(default_addr.lng), lat=float(default_addr.lat))

    lr = None

    if m.leave_range_start or m.leave_range_end:

        lr = {"start": m.leave_range_start, "end": m.leave_range_end}

    from app.core.timeutil import today_shanghai
    from app.services.leave import guard_member_self_service_during_sf_fulfillment
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date
    from app.services.store_config_service import get_leave_deadline_time_for_store

    ldt = get_leave_deadline_time_for_store(db, int(m.store_id))
    leave_deadline_str = ldt.isoformat() if ldt is not None else "21:00:00"
    biz_today = today_shanghai()
    sf_self_service_locked = member_sf_self_service_locked_on_delivery_date(
        db,
        member_id=int(m.id),
        store_id=int(m.store_id),
        delivery_date=biz_today,
        member_phone=(m.phone or "").strip() or None,
    )

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

        sf_self_service_locked=sf_self_service_locked,

        created_at=m.created_at.isoformat() if m.created_at else "",

    )





def get_member(db: Session, member_id: int) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    return _to_member_out(db, m, get_default_address(db, member_id))





def register_member(
    db: Session,
    body: RegisterIn,
    *,
    tenant_id: int,
    store_id: int,
) -> MemberOut:

    existing = _member_by_phone(db, body.phone, int(store_id))

    if existing and not _is_placeholder_profile(db, existing):

        raise HTTPException(status_code=409, detail="该手机号已注册")

    coords = amap.geocode_address(body.address)

    if coords:

        lng, lat = coords[0], coords[1]

        r = assign_region_for_coords(db, lng, lat, tenant_id=int(tenant_id))

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

            address_line=body.address,

            remarks=body.remarks,

            delivery_region_id=rid,

            lng=lng,

            lat=lat,

        )

        db.commit()

        db.refresh(existing)

        return _to_member_out(db, existing, get_default_address(db, existing.id))

    member = Member(

        tenant_id=int(tenant_id),

        store_id=int(store_id),

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

        address_line=body.address,

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

    ip_address: str | None = None,

) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    if (
        (set_daily_meal_units and daily_meal_units is not None)
        or (set_delivery_deferred and delivery_deferred is not None)
        or set_delivery_start
        or (set_store_pickup and store_pickup is not None)
    ):
        guard_member_self_service_during_sf_fulfillment(db, m)

    # 采集变更前关键字段，供操作日志 before/after 对比
    prev_snapshot = {
        "daily_meal_units": int(m.daily_meal_units or 1),
        "delivery_deferred": bool(m.delivery_deferred),
        "store_pickup": bool(m.store_pickup),
        "delivery_start_date": m.delivery_start_date.isoformat() if m.delivery_start_date else None,
        "is_active": bool(m.is_active),
    }

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
                    detail="起送日期须不早于今日（上海业务日）",
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

    # 操作日志：仅记录「争议易扯皮」的字段变化（份数/暂停/自提/起送日）
    new_snapshot = {
        "daily_meal_units": int(m.daily_meal_units or 1),
        "delivery_deferred": bool(m.delivery_deferred),
        "store_pickup": bool(m.store_pickup),
        "delivery_start_date": m.delivery_start_date.isoformat() if m.delivery_start_date else None,
        "is_active": bool(m.is_active),
    }
    if set_daily_meal_units and prev_snapshot["daily_meal_units"] != new_snapshot["daily_meal_units"]:
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=OP_UPDATE_DAILY_UNITS,
            summary=(
                f"修改每日送达份数 {prev_snapshot['daily_meal_units']}→"
                f"{new_snapshot['daily_meal_units']}（次日生效）"
            ),
            before={"daily_meal_units": prev_snapshot["daily_meal_units"]},
            after={"daily_meal_units": new_snapshot["daily_meal_units"]},
            ip_address=ip_address,
        )
    if set_delivery_deferred and prev_snapshot["delivery_deferred"] != new_snapshot["delivery_deferred"]:
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=(
                OP_PAUSE_DELIVERY if new_snapshot["delivery_deferred"] else OP_RESUME_DELIVERY
            ),
            summary="暂停配送" if new_snapshot["delivery_deferred"] else "取消暂停配送",
            before={"delivery_deferred": prev_snapshot["delivery_deferred"]},
            after={
                "delivery_deferred": new_snapshot["delivery_deferred"],
                "delivery_start_date": new_snapshot["delivery_start_date"],
                "store_pickup": new_snapshot["store_pickup"],
            },
            ip_address=ip_address,
        )
    if set_store_pickup and prev_snapshot["store_pickup"] != new_snapshot["store_pickup"]:
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=OP_UPDATE_STORE_PICKUP,
            summary=("改为门店自提" if new_snapshot["store_pickup"] else "改为配送到家"),
            before={"store_pickup": prev_snapshot["store_pickup"]},
            after={"store_pickup": new_snapshot["store_pickup"]},
            ip_address=ip_address,
        )
    if (
        set_delivery_start
        and not (set_delivery_deferred and prev_snapshot["delivery_deferred"] != new_snapshot["delivery_deferred"])
        and prev_snapshot["delivery_start_date"] != new_snapshot["delivery_start_date"]
    ):
        prev_ds = prev_snapshot["delivery_start_date"] or "-"
        new_ds = new_snapshot["delivery_start_date"] or "-"
        # 从暂停态切到配送/自提+选起送日，视作恢复配送
        op_type = (
            OP_RESUME_DELIVERY
            if prev_snapshot["delivery_deferred"] and not new_snapshot["delivery_deferred"]
            else OP_UPDATE_DELIVERY_START
        )
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=op_type,
            summary=f"修改起送日 {prev_ds}→{new_ds}",
            before={"delivery_start_date": prev_snapshot["delivery_start_date"]},
            after={"delivery_start_date": new_snapshot["delivery_start_date"]},
            ip_address=ip_address,
        )

    today_d = today_shanghai()
    attn_labels: list[str] = []
    if (
        set_delivery_deferred
        and prev_snapshot["delivery_deferred"]
        and not new_snapshot["delivery_deferred"]
    ):
        attn_labels.append("取消暂停配送")
    if set_delivery_start and not defer_applied:
        pblk = _blocked_today_by_delivery_start_snapshot(
            prev_snapshot["delivery_start_date"], today=today_d
        )
        nblk = _blocked_today_by_delivery_start_snapshot(
            new_snapshot["delivery_start_date"], today=today_d
        )
        if pblk and not nblk:
            attn_labels.append("修改起送日")

    attn_ordered = list(dict.fromkeys(attn_labels))
    if attn_ordered:
        try_notify_delivery_sheet_manual_attention(
            db,
            store_id=int(m.store_id),
            action_labels_cn=attn_ordered,
            member_id=int(m.id),
            member_phone=str(m.phone or "").strip() or None,
            member_name=str(m.name or "").strip() or None,
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
    ip_address: str | None = None,
    source: str = "miniprogram",
    operator: str | None = None,
) -> MemberOut:

    m = db.get(Member, member_id)

    if not m or m.deleted_at is not None:

        raise HTTPException(status_code=404, detail="用户不存在")

    now = now_shanghai()

    # 操作日志：采集变更前的请假状态，便于争议时还原
    prev = {
        "is_leaved_tomorrow": bool(m.is_leaved_tomorrow),
        "tomorrow_leave_target_date": (
            m.tomorrow_leave_target_date.isoformat() if m.tomorrow_leave_target_date else None
        ),
        "leave_range_start": m.leave_range_start.isoformat() if m.leave_range_start else None,
        "leave_range_end": m.leave_range_end.isoformat() if m.leave_range_end else None,
    }

    today_d = today_shanghai()
    before_absent_today = is_absent_from_leave_snapshot_dict(
        prev, delivery_date=today_d, today=today_d
    )

    if source == "miniprogram":
        guard_member_self_leave_during_sf_fulfillment(db, m)

    if typ == LeaveType.CANCEL:

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

        m.leave_range_start = None

        m.leave_range_end = None

    elif typ == LeaveType.CLEAR_TOMORROW:

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

    elif typ == LeaveType.TOMORROW:

        t_target = tomorrow_shanghai()

        m.tomorrow_leave_target_date = t_target

        m.is_leaved_tomorrow = True

    elif typ == LeaveType.RANGE:

        if not start or not end:

            raise HTTPException(status_code=400, detail="区间请假需提供 start 与 end")

        if end < start:

            raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

        if not skip_leave_deadline:
            min_day = min_leave_start_shanghai(now)
            if start < min_day or end < min_day:
                raise HTTPException(status_code=400, detail="区间请假须从明天起选日期")

        m.leave_range_start = start

        m.leave_range_end = end

        m.is_leaved_tomorrow = False

        m.tomorrow_leave_target_date = None

    else:

        raise HTTPException(status_code=400, detail="不支持的请假类型")

    after_absent_today = is_absent_on_delivery_date(m, today_d, today=today_d)

    after = {
        "is_leaved_tomorrow": bool(m.is_leaved_tomorrow),
        "tomorrow_leave_target_date": (
            m.tomorrow_leave_target_date.isoformat() if m.tomorrow_leave_target_date else None
        ),
        "leave_range_start": m.leave_range_start.isoformat() if m.leave_range_start else None,
        "leave_range_end": m.leave_range_end.isoformat() if m.leave_range_end else None,
    }
    if typ == LeaveType.TOMORROW:
        op_type = OP_LEAVE_TOMORROW
        summary = f"明天请假：{after['tomorrow_leave_target_date'] or '-'}"
    elif typ == LeaveType.RANGE:
        op_type = OP_LEAVE_RANGE
        s = after["leave_range_start"] or "-"
        e = after["leave_range_end"] or "-"
        summary = f"区间请假：{s} ~ {e}"
    elif typ == LeaveType.CLEAR_TOMORROW:
        op_type = OP_LEAVE_CLEAR_TOMORROW
        summary = "取消明天请假"
    else:
        op_type = OP_LEAVE_CANCEL
        summary = "取消所有请假"
    record_member_operation(
        db,
        member_id=member_id,
        operation_type=op_type,
        summary=summary,
        before=prev,
        after=after,
        ip_address=ip_address,
        source=source,
        operator=operator,
    )

    if (
        source == "miniprogram"
        and typ != LeaveType.TOMORROW
        and before_absent_today
        and not after_absent_today
    ):
        if typ == LeaveType.CANCEL:
            leave_lab = ["取消全部请假"]
        elif typ == LeaveType.CLEAR_TOMORROW:
            leave_lab = ["清除明天请假"]
        elif typ == LeaveType.RANGE:
            leave_lab = ["调整请假区间"]
        else:
            leave_lab = ["请假变更"]
        try_notify_delivery_sheet_manual_attention(
            db,
            store_id=int(m.store_id),
            action_labels_cn=leave_lab,
            member_id=int(m.id),
            member_phone=str(m.phone or "").strip() or None,
            member_name=str(m.name or "").strip() or None,
        )

    db.commit()

    db.refresh(m)

    return _to_member_out(db, m, get_default_address(db, member_id))


def admin_member_leave(
    db: Session,
    *,
    phone: str,
    store_id: int,
    typ: LeaveType,
    start: date | None,
    end: date | None,
    operator: str | None = None,
    ip_address: str | None = None,
) -> MemberOut:
    """管理端代会员设置请假：不校验「须从明天起」等小程序限制（可代填历史区间）。"""

    p = (phone or "").strip()
    m = _member_by_phone(db, p, int(store_id))
    if not m:
        raise HTTPException(status_code=404, detail="用户不存在")
    return leave_request(
        db,
        m.id,
        typ,
        start,
        end,
        skip_leave_deadline=True,
        ip_address=ip_address,
        source="admin",
        operator=(f"admin:{operator}" if operator else None),
    )


def _week_start_and_slot(d: date) -> tuple[date, int]:

    return _monday_of_week(d), d.weekday() + 1





def _by_date_from_weekly_rows(rows: list[tuple[WeeklyMenuSlot, MenuDish]]) -> dict[date, MenuDish]:

    by_date: dict[date, MenuDish] = {}

    for ws, dish in rows:

        day = ws.week_start + timedelta(days=ws.slot - 1)

        by_date[day] = dish

    return by_date





def get_tomorrow_menu(db: Session, *, store_id: int) -> dict:

    d = tomorrow_shanghai()

    ws, slot = _week_start_and_slot(d)

    sid = int(store_id)

    row = db.execute(

        select(WeeklyMenuSlot, MenuDish)

        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)

        .where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == ws,
            WeeklyMenuSlot.slot == slot,
        )

    ).first()

    if row:

        _, dish = row

        out = {

            "date": d.isoformat(),

            "dish_id": dish.id,

            "title": dish.name,

            "desc": dish.description,

            "pic": dish.image_url,

            "price": _member_menu_price(dish),

        }

        out.update(_member_spice_public_fields(dish))

        return out

    row2 = db.execute(

        select(MenuSchedule, MenuDish)

        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)

        .where(MenuSchedule.menu_date == d, MenuSchedule.store_id == sid)

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

    out = {

        "date": d.isoformat(),

        "dish_id": dish.id,

        "title": dish.name,

        "desc": dish.description,

        "pic": dish.image_url,

        "price": _member_menu_price(dish),

    }

    out.update(_member_spice_public_fields(dish))

    return out





def _monday_of_week(d: date) -> date:

    return d - timedelta(days=d.weekday())





def _member_menu_price(dish: MenuDish | None) -> float | None:

    if dish is None or dish.single_order_price_yuan is None:

        return None

    return float(dish.single_order_price_yuan)


def _member_spice_public_fields(dish: MenuDish | None) -> dict[str, str]:
    """会员端辣度：未在后台标注则不返回；含 none(不辣)/mild/medium/hot。"""
    if dish is None:
        return {}
    raw = (getattr(dish, "spice_level", None) or "").strip().lower()
    if not raw:
        return {}
    label = SPICE_LEVEL_MEMBER_LABELS.get(raw)
    if not label:
        return {}
    return {"spice_level": raw, "spice_label": label}





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

    if dish is not None:

        o.update(_member_spice_public_fields(dish))

    return o





def get_weekly_menu(
    db: Session,
    week_start: date | None,
    *,
    store_id: int,
    as_of_date: date | None = None,
    include_stock: bool = False,
) -> dict:

    anchor = _monday_of_week(week_start) if week_start else _monday_of_week(today_shanghai())

    dates = [anchor + timedelta(days=i) for i in range(7)]

    sid = int(store_id)

    as_of_eff = as_of_date if as_of_date is not None else today_shanghai()

    weekly_rows = db.execute(

        select(WeeklyMenuSlot, MenuDish)

        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)

        .where(WeeklyMenuSlot.week_start == anchor, WeeklyMenuSlot.store_id == sid)

    ).all()

    by_date = _by_date_from_weekly_rows(list(weekly_rows))

    missing = [x for x in dates if x not in by_date]

    if missing:

        sched_rows = db.execute(

            select(MenuSchedule, MenuDish)

            .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)

            .where(MenuSchedule.menu_date.in_(missing), MenuSchedule.store_id == sid)

        ).all()

        for sched, dish in sched_rows:

            by_date[sched.menu_date] = dish

    stocks: dict[date, object] = {}
    if include_stock:
        from app.services.menu_day_stock_service import single_order_stock_by_date_for_week

        stocks = single_order_stock_by_date_for_week(
            db,
            week_start_anchor=anchor,
            dates=dates,
            dishes_by_date=by_date,
            weekly_slot_rows=weekly_rows,
            store_id=sid,
            subscription_floor_date=as_of_eff,
        )

    items: list[dict] = []
    for i, d in enumerate(dates):
        dish = by_date.get(d)
        card = _dish_to_member_card(menu_date=d, dish=dish, slot=i + 1)
        if include_stock and dish is not None:
            card.update(stocks[d].to_detail_dict())
        items.append(card)

    return {"week_start": anchor.isoformat(), "as_of": as_of_eff.isoformat(), "items": items}





def get_menu_detail_by_dish_id(
    db: Session, dish_id: int, *, service_date: date | None = None, store_id: int
) -> dict:

    dish = db.get(MenuDish, dish_id)

    if not dish:

        raise HTTPException(status_code=404, detail="餐品不存在")

    if int(dish.store_id) != int(store_id):

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

    out.update(_member_spice_public_fields(dish))

    if service_date is not None:
        from app.services.menu_day_stock_service import single_order_stock_for_dish_date

        out.update(
            single_order_stock_for_dish_date(db, int(dish_id), service_date, store_id=int(store_id)).to_detail_dict()
        )

    return out





def admin_update_member_address(
    db: Session,
    phone: str,
    address: str,
    *,
    operator: str,
    store_id: int,
    ip_address: str | None = None,
) -> MemberOut:

    m = _member_by_phone(db, phone, int(store_id))

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    addr_before = get_default_address(db, m.id)
    prev_address = (
        full_address_line(addr_before.map_location_text, addr_before.door_detail)
        if addr_before
        else None
    )

    admin_set_default_address_plain_line(

        db,

        member_id=m.id,

        detail_line=address,

        contact_name=m.name,

        contact_phone=m.phone,

    )

    addr_after = get_default_address(db, m.id)
    new_address = (
        full_address_line(addr_after.map_location_text, addr_after.door_detail)
        if addr_after
        else None
    )
    if prev_address != new_address:
        record_member_operation(
            db,
            member_id=m.id,
            operation_type=OP_ADMIN_UPDATE_ADDRESS,
            summary="修改默认配送地址",
            before={"address": prev_address},
            after={"address": new_address},
            ip_address=ip_address,
            source="admin",
            operator=(f"admin:{(operator or '').strip()}" if (operator or "").strip() else "admin")[:100],
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

    store_id: int,

    daily_meal_units: int | None = None,

    plan_type: PlanType | None = None,

    set_balance: bool = False,

    balance: int | None = None,

    set_delivery_start_date: bool = False,

    delivery_start_date: date | None = None,

    set_store_pickup: bool = False,

    store_pickup: bool | None = None,

    set_skip_subscription_saturday: bool = False,

    skip_subscription_saturday: bool | None = None,

    set_delivery_region_id: bool = False,

    delivery_region_id: int | None = None,

    set_delivery_deferred: bool = False,

    delivery_deferred: bool | None = None,

    set_remarks: bool = False,

    ip_address: str | None = None,

) -> MemberOut:

    admin_op = (f"admin:{(operator or '').strip()}" if (operator or "").strip() else "admin")[:100]

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

        and not set_skip_subscription_saturday

        and not set_delivery_region_id

        and not set_delivery_deferred

    ):

        raise HTTPException(status_code=400, detail="请至少修改一项内容")

    m = _member_by_phone(db, phone, int(store_id))

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    mid = m.id

    addr_before = get_default_address(db, mid)
    prev_snapshot = {
        "name": m.name,
        "remarks": m.remarks,
        "address": (
            full_address_line(addr_before.map_location_text, addr_before.door_detail)
            if addr_before
            else None
        ),
        "delivery_region_id": (
            int(addr_before.delivery_region_id)
            if addr_before and addr_before.delivery_region_id is not None
            else None
        ),
        "daily_meal_units": int(m.daily_meal_units or 1),
        "plan_type": m.plan_type,
        "balance": int(m.balance),
        "delivery_start_date": m.delivery_start_date.isoformat() if m.delivery_start_date else None,
        "store_pickup": bool(m.store_pickup),
        "skip_subscription_saturday": bool(m.skip_subscription_saturday),
        "delivery_deferred": bool(m.delivery_deferred),
        "is_active": bool(m.is_active),
    }

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

        admin_set_default_address_plain_line(

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

    if set_skip_subscription_saturday:

        if skip_subscription_saturday is None:

            raise HTTPException(status_code=400, detail="固定周六不履约标记不能为空")

        m.skip_subscription_saturday = bool(skip_subscription_saturday)

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

    addr_after = get_default_address(db, mid)
    new_snapshot = {
        "name": m.name,
        "remarks": m.remarks,
        "address": (
            full_address_line(addr_after.map_location_text, addr_after.door_detail)
            if addr_after
            else None
        ),
        "delivery_region_id": (
            int(addr_after.delivery_region_id)
            if addr_after and addr_after.delivery_region_id is not None
            else None
        ),
        "daily_meal_units": int(m.daily_meal_units or 1),
        "plan_type": m.plan_type,
        "balance": int(m.balance),
        "delivery_start_date": m.delivery_start_date.isoformat() if m.delivery_start_date else None,
        "store_pickup": bool(m.store_pickup),
        "skip_subscription_saturday": bool(m.skip_subscription_saturday),
        "delivery_deferred": bool(m.delivery_deferred),
        "is_active": bool(m.is_active),
    }

    def _admin_log(op_type: str, summary: str, *, before: dict | None = None, after: dict | None = None) -> None:
        record_member_operation(
            db,
            member_id=mid,
            operation_type=op_type,
            summary=summary,
            before=before,
            after=after,
            ip_address=ip_address,
            source="admin",
            operator=admin_op,
        )

    if name is not None and prev_snapshot["name"] != new_snapshot["name"]:
        _admin_log(
            OP_ADMIN_UPDATE_NAME,
            f"修改姓名 {prev_snapshot['name'] or '-'}→{new_snapshot['name'] or '-'}",
            before={"name": prev_snapshot["name"]},
            after={"name": new_snapshot["name"]},
        )
    if set_remarks and prev_snapshot["remarks"] != new_snapshot["remarks"]:
        _admin_log(
            OP_ADMIN_UPDATE_REMARKS,
            f"修改备注",
            before={"remarks": prev_snapshot["remarks"]},
            after={"remarks": new_snapshot["remarks"]},
        )
    if address is not None and prev_snapshot["address"] != new_snapshot["address"]:
        _admin_log(
            OP_ADMIN_UPDATE_ADDRESS,
            f"修改默认配送地址",
            before={"address": prev_snapshot["address"]},
            after={"address": new_snapshot["address"]},
        )
    if (
        (use_auto_area or set_delivery_region_id)
        and prev_snapshot["delivery_region_id"] != new_snapshot["delivery_region_id"]
    ):
        prev_rid = prev_snapshot["delivery_region_id"]
        new_rid = new_snapshot["delivery_region_id"]
        _admin_log(
            OP_ADMIN_UPDATE_DELIVERY_REGION,
            f"修改配送片区 {prev_rid if prev_rid is not None else '-'}→{new_rid if new_rid is not None else '-'}",
            before={"delivery_region_id": prev_rid},
            after={"delivery_region_id": new_rid},
        )
    if set_balance and prev_snapshot["balance"] != new_snapshot["balance"]:
        _admin_log(
            OP_ADMIN_UPDATE_BALANCE,
            f"修改剩余次数 {prev_snapshot['balance']}→{new_snapshot['balance']}",
            before={"balance": prev_snapshot["balance"]},
            after={"balance": new_snapshot["balance"]},
        )
    if plan_type is not None and prev_snapshot["plan_type"] != new_snapshot["plan_type"]:
        _admin_log(
            OP_ADMIN_UPDATE_PLAN_TYPE,
            f"修改套餐类型 {prev_snapshot['plan_type'] or '-'}→{new_snapshot['plan_type'] or '-'}",
            before={"plan_type": prev_snapshot["plan_type"]},
            after={"plan_type": new_snapshot["plan_type"]},
        )
    if (
        daily_meal_units is not None
        and prev_snapshot["daily_meal_units"] != new_snapshot["daily_meal_units"]
    ):
        _admin_log(
            OP_UPDATE_DAILY_UNITS,
            (
                f"修改每日送达份数 {prev_snapshot['daily_meal_units']}→"
                f"{new_snapshot['daily_meal_units']}"
            ),
            before={"daily_meal_units": prev_snapshot["daily_meal_units"]},
            after={"daily_meal_units": new_snapshot["daily_meal_units"]},
        )
    if (
        set_delivery_deferred
        and prev_snapshot["delivery_deferred"] != new_snapshot["delivery_deferred"]
    ):
        _admin_log(
            OP_PAUSE_DELIVERY if new_snapshot["delivery_deferred"] else OP_RESUME_DELIVERY,
            "暂停配送" if new_snapshot["delivery_deferred"] else "取消暂停配送",
            before={"delivery_deferred": prev_snapshot["delivery_deferred"]},
            after={
                "delivery_deferred": new_snapshot["delivery_deferred"],
                "delivery_start_date": new_snapshot["delivery_start_date"],
                "store_pickup": new_snapshot["store_pickup"],
            },
        )
    if set_store_pickup and prev_snapshot["store_pickup"] != new_snapshot["store_pickup"]:
        _admin_log(
            OP_UPDATE_STORE_PICKUP,
            "改为门店自提" if new_snapshot["store_pickup"] else "改为配送到家",
            before={"store_pickup": prev_snapshot["store_pickup"]},
            after={"store_pickup": new_snapshot["store_pickup"]},
        )
    if (
        set_delivery_start_date
        and not (
            set_delivery_deferred
            and prev_snapshot["delivery_deferred"] != new_snapshot["delivery_deferred"]
        )
        and prev_snapshot["delivery_start_date"] != new_snapshot["delivery_start_date"]
    ):
        prev_ds = prev_snapshot["delivery_start_date"] or "-"
        new_ds = new_snapshot["delivery_start_date"] or "-"
        op_type = (
            OP_RESUME_DELIVERY
            if prev_snapshot["delivery_deferred"] and not new_snapshot["delivery_deferred"]
            else OP_UPDATE_DELIVERY_START
        )
        _admin_log(
            op_type,
            f"修改起送日 {prev_ds}→{new_ds}",
            before={"delivery_start_date": prev_snapshot["delivery_start_date"]},
            after={"delivery_start_date": new_snapshot["delivery_start_date"]},
        )
    if (
        set_skip_subscription_saturday
        and prev_snapshot["skip_subscription_saturday"] != new_snapshot["skip_subscription_saturday"]
    ):
        _admin_log(
            OP_ADMIN_UPDATE_SKIP_SATURDAY,
            (
                "开启固定周六不履约"
                if new_snapshot["skip_subscription_saturday"]
                else "关闭固定周六不履约"
            ),
            before={"skip_subscription_saturday": prev_snapshot["skip_subscription_saturday"]},
            after={"skip_subscription_saturday": new_snapshot["skip_subscription_saturday"]},
        )

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

