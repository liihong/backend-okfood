from datetime import date, timedelta



from fastapi import HTTPException

from sqlalchemy import select, update

from sqlalchemy.orm import Session



from app.core.timeutil import now_shanghai, today_shanghai, tomorrow_shanghai

from app.models.app_settings import AppSettings

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

    admin_set_default_address_detail,

    get_default_address,

    upsert_default_address_after_register,

)

from app.services.region_assignment import assign_area_name_for_coords





def _member_by_phone(db: Session, phone: str) -> Member | None:

    return db.scalar(select(Member).where(Member.phone == phone))





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

    row_id = db.scalar(select(Member.id).where(Member.phone == phone))

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





def _to_member_out(m: Member, default_addr: MemberAddress | None = None) -> MemberOut:

    """会员对外资料：地址/坐标/片区以默认配送地址为准。"""

    loc = None

    address_line = ""

    area_name = UNASSIGNED_DELIVERY_AREA

    area_manual = False

    if default_addr is not None:

        address_line = (default_addr.detail_address or "").strip()

        ar = (default_addr.area or "").strip()

        area_name = ar if ar else UNASSIGNED_DELIVERY_AREA

        area_manual = bool(default_addr.area_manual)

        if default_addr.lng is not None and default_addr.lat is not None:

            loc = Location(lng=float(default_addr.lng), lat=float(default_addr.lat))

    lr = None

    if m.leave_range_start or m.leave_range_end:

        lr = {"start": m.leave_range_start, "end": m.leave_range_end}



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

        area_manual=area_manual,

        remarks=m.remarks,

        balance=m.balance,

        plan_type=plan_out,

        delivery_start_date=m.delivery_start_date,

        is_active=m.is_active,

        is_leaved_tomorrow=m.is_leaved_tomorrow,

        leave_range=lr,

        created_at=m.created_at.isoformat() if m.created_at else "",

    )





def get_member(db: Session, member_id: int) -> MemberOut:

    m = db.get(Member, member_id)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    return _to_member_out(m, get_default_address(db, member_id))





def register_member(db: Session, body: RegisterIn) -> MemberOut:

    existing = _member_by_phone(db, body.phone)

    if existing and not _is_placeholder_profile(db, existing):

        raise HTTPException(status_code=409, detail="该手机号已注册")

    coords = amap.geocode_address(body.address)

    if coords:

        lng, lat = coords[0], coords[1]

        area_name = assign_area_name_for_coords(db, lng, lat)

    else:

        lng, lat = None, None

        area_name = UNASSIGNED_DELIVERY_AREA

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

            area=area_name,

            lng=lng,

            lat=lat,

        )

        db.commit()

        db.refresh(existing)

        return _to_member_out(existing, get_default_address(db, existing.id))

    member = Member(

        phone=body.phone,

        name=body.name,

        remarks=body.remarks,

        avatar_url=body.avatar_url,

        balance=0,

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

        area=area_name,

        lng=lng,

        lat=lat,

    )

    db.commit()

    db.refresh(member)

    return _to_member_out(member, get_default_address(db, member.id))





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

) -> MemberOut:

    m = db.get(Member, member_id)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

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

        old_plan = (m.plan_type or "").strip() if isinstance(m.plan_type, str) else ""

        new_val = plan_type.value if plan_type is not None else None

        m.plan_type = new_val

        if not old_plan and new_val in (PlanType.WEEK.value, PlanType.MONTH.value):

            add = 6 if new_val == PlanType.WEEK.value else 24

            m.balance = int(m.balance or 0) + add

            m.is_active = True

            db.add(

                BalanceLog(

                    member_id=m.id,

                    change=add,

                    reason=BalanceReason.RECHARGE.value,

                    operator="miniprogram_plan",

                )

            )

    if set_delivery_start:

        if delivery_start_date is not None and delivery_start_date < today_shanghai():

            raise HTTPException(status_code=400, detail="起送日期不能早于今天（上海）")

        m.delivery_start_date = delivery_start_date

    db.commit()

    db.refresh(m)

    return _to_member_out(m, get_default_address(db, member_id))





def activate_member(db: Session, member_id: int) -> MemberOut:

    m = db.get(Member, member_id)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    m.is_active = True

    db.commit()

    db.refresh(m)

    return _to_member_out(m, get_default_address(db, member_id))





def leave_request(db: Session, member_id: int, typ: LeaveType, start: date | None, end: date | None) -> MemberOut:

    m = db.get(Member, member_id)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")



    settings_row = db.get(AppSettings, 1)

    if not settings_row:

        raise HTTPException(status_code=500, detail="系统设置缺失")



    now = now_shanghai()



    if typ == LeaveType.CANCEL:

        m.is_leaved_tomorrow = False

        m.leave_range_start = None

        m.leave_range_end = None

    elif typ == LeaveType.CLEAR_TOMORROW:

        m.is_leaved_tomorrow = False

    elif typ == LeaveType.TOMORROW:

        if is_leave_deadline_passed(now.time(), settings_row.leave_deadline_time):

            raise HTTPException(status_code=400, detail="已超过当日请假截止时间")

        m.is_leaved_tomorrow = True

    elif typ == LeaveType.RANGE:

        if not start or not end:

            raise HTTPException(status_code=400, detail="区间请假需提供 start 与 end")

        if end < start:

            raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

        m.leave_range_start = start

        m.leave_range_end = end

        m.is_leaved_tomorrow = False

    else:

        raise HTTPException(status_code=400, detail="不支持的请假类型")



    db.commit()

    db.refresh(m)

    return _to_member_out(m, get_default_address(db, member_id))





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





def get_menu_detail_by_dish_id(db: Session, dish_id: int) -> dict:

    dish = db.get(MenuDish, dish_id)

    if not dish:

        raise HTTPException(status_code=404, detail="餐品不存在")

    return {

        "dish_id": dish.id,

        "title": dish.name,

        "desc": dish.description,

        "pic": dish.image_url,

        "is_enabled": dish.is_enabled,

        "category_id": dish.category_id,

        "price": _member_menu_price(dish),

    }





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

    return _to_member_out(m, get_default_address(db, m.id))





def admin_patch_member_profile(

    db: Session,

    *,

    phone: str,

    name: str | None,

    remarks: str | None,

    address: str | None,

    delivery_area: str | None,

    use_auto_area: bool,

    operator: str,

) -> MemberOut:

    _ = operator

    if (

        name is None

        and remarks is None

        and address is None

        and delivery_area is None

        and not use_auto_area

    ):

        raise HTTPException(status_code=400, detail="请至少修改一项内容")

    if use_auto_area and delivery_area is not None:

        raise HTTPException(status_code=400, detail="不能同时指定手工片区与恢复自动划区")

    m = _member_by_phone(db, phone)

    if not m:

        raise HTTPException(status_code=404, detail="用户不存在")

    mid = m.id

    if name is not None:

        t = name.strip()

        if not t:

            raise HTTPException(status_code=400, detail="姓名不能为空")

        m.name = t

    if remarks is not None:

        m.remarks = remarks.strip() or None

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

    if use_auto_area:

        addr = get_default_address(db, mid)

        if not addr:

            raise HTTPException(status_code=400, detail="该会员暂无默认配送地址，无法自动划区")

        if addr.lng is not None and addr.lat is not None:

            lng_f, lat_f = float(addr.lng), float(addr.lat)

            addr.area = assign_area_name_for_coords(db, lng_f, lat_f)

        else:

            addr.area = UNASSIGNED_DELIVERY_AREA

        addr.area_manual = False

    if delivery_area is not None:

        addr = get_default_address(db, mid)

        if not addr:

            raise HTTPException(status_code=400, detail="该会员暂无默认配送地址，请先填写地址后再指定片区")

        t = delivery_area.strip()

        addr.area = t if t else UNASSIGNED_DELIVERY_AREA

        addr.area_manual = True

    db.commit()

    db.refresh(m)

    return _to_member_out(m, get_default_address(db, mid))

