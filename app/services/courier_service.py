from collections import defaultdict
from datetime import date
from decimal import Decimal
import re

from fastapi import HTTPException
from sqlalchemy import and_, literal, not_, or_, select
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
from app.services.courier_admin_service import regions_for_courier
from app.services.courier_task_sorting import (
    distance_from_anchor_m,
    reference_lng_lat_for_task_sorting,
    task_sort_key,
)
from app.services.store_config_service import load_store_coordinates_for_sorting
from app.services.leave import is_absent_on_delivery_date
from app.services.member_address_service import default_address_pick_subquery, load_default_address_map
from app.services.member_service import effective_daily_meal_units, sql_effective_daily_meal_units_column
from app.services.single_meal_order_service import list_courier_single_order_tasks


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
    stmt = select(Courier).where(Courier.is_active.is_(True), Courier.phone.isnot(None))
    candidates = list(db.scalars(stmt).all())
    matched = []
    for c in candidates:
        p = (c.phone or "").strip()
        if not p:
            continue
        cand_digits = re.sub(r"\D", "", p)
        if len(cand_digits) == 13 and cand_digits.startswith("86"):
            cand_digits = cand_digits[2:]
        if cand_digits == norm or p == norm:
            matched.append(c)
    if not matched:
        raise HTTPException(status_code=401, detail="手机号未登记或已停用")
    if len(matched) > 1:
        raise HTTPException(status_code=409, detail="该手机号绑定多个配送账号，请联系管理员")
    return matched[0]


def eligible_members_for_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    应配送会员（Member 行）及每人默认地址（与 is_absent_on_delivery_date / 配送清单同一规则）。
    「仅明天请假」相对业务 today（上海），与 delivery_date 比较。
    若会员设置了 delivery_start_date，仅当 delivery_date 不早于该日才入选。
    周日与法定节假日不配送，直接返回空列表（与配送大表、备餐口径一致）。

    单次查询 OUTER JOIN 默认地址；按片区筛选时在 SQL 中过滤，避免「全员查完再内存过滤」的二次往返。
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
    tomorrow_leave_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        literal(delivery_date) == literal(tomorrow),
    )
    absent = or_(in_leave_range, tomorrow_leave_hit)
    started = or_(
        Member.delivery_start_date.is_(None),
        Member.delivery_start_date <= delivery_date,
    )
    units_sql = sql_effective_daily_meal_units_column()
    daf = default_address_pick_subquery()
    q = (
        select(Member, MemberAddress)
        .outerjoin(daf, daf.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
        .where(
            Member.is_active.is_(True),
            Member.balance >= units_sql,
            not_(absent),
            started,
        )
    )
    if delivery_region_id is not None:
        q = q.where(MemberAddress.delivery_region_id == delivery_region_id)
    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    for m, addr in db.execute(q).all():
        members.append(m)
        defaults[m.id] = addr
    return members, defaults


def list_today_tasks(
    db: Session,
    *,
    delivery_region_id: int,
    delivery_region_display: str,
    delivery_date: date | None = None,
) -> list[CourierTaskMemberOut]:
    """
    当日配送清单：
    - is_active 且 balance>=当日应付份数（daily_meal_units，封顶 50）；
    - 若设置了 delivery_start_date，仅当配送日>=该日；
    - 配送日不在请假区间，且「明天请假」不影响「今日」配送；
    - 周日与法定节假日不生成订阅清单；
    - 按 delivery_region_id 过滤默认地址；
    - 组内按与坐标均值的直线距离排序。
    """
    d = delivery_date or today_shanghai()
    eligible, defaults = eligible_members_for_delivery(db, delivery_date=d, delivery_region_id=delivery_region_id)

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
        detail = (addr.detail_address if addr else "") or ""
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
    rows.sort(key=lambda x: task_sort_key(x.sort_distance_m))
    return rows


def list_tasks_for_courier(
    db: Session,
    courier_id: str,
    *,
    delivery_date: date | None = None,
) -> tuple[list[CourierTaskMemberOut], date]:
    """当日任务：仅包含该配送员在 delivery_region_couriers 中绑定的片区。"""
    d = delivery_date or today_shanghai()
    regions = regions_for_courier(db, courier_id)
    if not regions:
        singles = list_courier_single_order_tasks(db, courier_id, d)
        singles.sort(key=lambda x: task_sort_key(x.sort_distance_m))
        return singles, d
    by_member: dict[int, CourierTaskMemberOut] = {}
    for reg in regions:
        rname = (reg.name or "").strip() or UNASSIGNED_DELIVERY_AREA
        for row in list_today_tasks(
            db,
            delivery_region_id=int(reg.region_id),
            delivery_region_display=rname,
            delivery_date=d,
        ):
            by_member[row.member_id] = row
    out = list(by_member.values())
    singles = list_courier_single_order_tasks(db, courier_id, d)
    out.extend(singles)
    out.sort(key=lambda x: task_sort_key(x.sort_distance_m))
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
    if not member:
        raise HTTPException(status_code=404, detail="用户不存在")

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

    log = db.execute(
        select(DeliveryLog).where(DeliveryLog.member_id == member_id, DeliveryLog.delivery_date == d).with_for_update()
    ).scalar_one_or_none()

    if log and log.status == DeliveryStatus.DELIVERED.value:
        return

    if log and log.status == DeliveryStatus.LEAVE.value:
        raise HTTPException(status_code=400, detail="该日记录为请假状态")

    if not log:
        log = DeliveryLog(member_id=member_id, delivery_date=d, status=DeliveryStatus.DELIVERED.value, courier_id=courier_id)
        db.add(log)
    else:
        log.status = DeliveryStatus.DELIVERED.value
        log.courier_id = courier_id

    member.balance -= deduct
    db.add(
        BalanceLog(
            member_id=member_id,
            change=-deduct,
            reason=BalanceReason.DELIVERY.value,
            operator=f"courier:{courier_id}",
            detail=None,
        )
    )
    fee_yuan = courier_delivery_fee_yuan_for_meal_units(db, deduct)
    courier_row = db.execute(select(Courier).where(Courier.courier_id == courier_id).with_for_update()).scalar_one_or_none()
    if not courier_row:
        raise HTTPException(status_code=500, detail="配送员账户异常")
    prev = courier_row.fee_pending if courier_row.fee_pending is not None else Decimal("0.00")
    courier_row.fee_pending = prev + fee_yuan
    db.commit()
