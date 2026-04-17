from collections import defaultdict
from datetime import date
import logging
import re

from fastapi import HTTPException
from sqlalchemy import and_, literal, not_, or_, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.core.timeutil import today_shanghai
from app.models.balance_log import BalanceLog
from app.models.courier import Courier
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.schemas.courier import CourierTaskMemberOut
from app.services.courier_admin_service import regions_for_courier
from app.services.geo import haversine_m
from app.services.leave import is_absent_on_delivery_date
from app.services.member_address_service import effective_routing_area, load_default_address_map
from app.services.single_meal_order_service import list_courier_single_order_tasks

logger = logging.getLogger(__name__)


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
    area: str | None = None,
) -> list[Member]:
    """
    应配送会员（Member 行），与 is_absent_on_delivery_date / 配送清单同一规则。
    「仅明天请假」相对业务 today（上海），与 delivery_date 比较。
    若会员设置了 delivery_start_date，仅当 delivery_date 不早于该日才入选。
    """
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
    q = select(Member).where(
        Member.is_active.is_(True),
        Member.balance > 0,
        not_(absent),
        started,
    )
    eligible = list(db.scalars(q).all())
    if not area:
        return eligible
    filt = (area or "").strip()
    defaults = load_default_address_map(db, [m.id for m in eligible])
    return [m for m in eligible if effective_routing_area(defaults.get(m.id)) == filt]


def list_today_tasks(db: Session, area: str | None, *, delivery_date: date | None = None) -> list[CourierTaskMemberOut]:
    """
    当日配送清单：
    - is_active 且 balance>0；
    - 若设置了 delivery_start_date，仅当配送日>=该日；
    - 配送日不在请假区间，且「明天请假」不影响「今日」配送；
    - 可选按 area 过滤；
    - 组内按与坐标均值的直线距离排序。
    """
    d = delivery_date or today_shanghai()
    eligible = eligible_members_for_delivery(db, delivery_date=d, area=area)
    defaults = load_default_address_map(db, [m.id for m in eligible])

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

    ref_lng, ref_lat = _reference_point_with_defaults(eligible, defaults)
    rows: list[CourierTaskMemberOut] = []
    for m in eligible:
        addr = defaults.get(m.id)
        dist = None
        if (
            ref_lng is not None
            and ref_lat is not None
            and addr is not None
            and addr.lng is not None
            and addr.lat is not None
        ):
            dist = haversine_m(ref_lng, ref_lat, float(addr.lng), float(addr.lat))
        ar = effective_routing_area(addr)
        detail = (addr.detail_address if addr else "") or ""
        display_addr = f"{ar} {detail}".strip() or "（未设置默认配送地址）"
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
                sort_distance_m=dist,
                is_delivered=m.id in delivered_ids,
            )
        )
    rows.sort(key=lambda x: (x.sort_distance_m is None, x.sort_distance_m or 0.0))
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
    area_names = sorted({(r.name or "").strip() for r in regions if r.name and (r.name or "").strip()})
    if not area_names:
        singles = list_courier_single_order_tasks(db, courier_id, d)
        return singles, d
    by_member: dict[int, CourierTaskMemberOut] = {}
    for an in area_names:
        for row in list_today_tasks(db, an, delivery_date=d):
            by_member[row.member_id] = row
    out = list(by_member.values())
    out.sort(key=lambda x: (x.sort_distance_m is None, x.sort_distance_m or 0.0))
    out.extend(list_courier_single_order_tasks(db, courier_id, d))
    return out, d


def group_task_rows(rows: list[CourierTaskMemberOut]) -> list[dict]:
    grouped: dict[str, list] = defaultdict(list)
    for m in rows:
        grouped[m.area].append(m.model_dump(mode="json"))
    return [{"area": k, "items": grouped[k]} for k in sorted(grouped.keys())]


def _reference_point_with_defaults(
    members: list[Member],
    defaults: dict,
) -> tuple[float | None, float | None]:
    pts: list[tuple[float, float]] = []
    for m in members:
        a = defaults.get(m.id)
        if a is not None and a.lng is not None and a.lat is not None:
            pts.append((float(a.lng), float(a.lat)))
    if not pts:
        return None, None
    lng = sum(p[0] for p in pts) / len(pts)
    lat = sum(p[1] for p in pts) / len(pts)
    return lng, lat


def confirm_delivery(db: Session, courier_id: str, member_id: int, delivery_date: date | None) -> None:
    """
    确认送达：单事务内完成流水 + 扣次 + 余额流水；已送达则幂等返回。
    """
    d = delivery_date or today_shanghai()
    today = today_shanghai()

    member = db.execute(select(Member).where(Member.id == member_id).with_for_update()).scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="用户不存在")

    allowed_areas = {
        (r.name or "").strip()
        for r in regions_for_courier(db, courier_id)
        if r.name and (r.name or "").strip()
    }
    if not allowed_areas:
        raise HTTPException(status_code=403, detail="账号未分配配送片区")
    da = load_default_address_map(db, [member_id]).get(member_id)
    ma = effective_routing_area(da)
    if ma not in allowed_areas:
        raise HTTPException(status_code=403, detail="该会员不在您负责的片区")

    if not member.is_active or member.balance <= 0:
        raise HTTPException(status_code=400, detail="用户未激活或次数不足")
    if is_absent_on_delivery_date(member, d, today=today):
        raise HTTPException(status_code=400, detail="该日用户请假，无法确认送达")
    if member.delivery_start_date is not None and d < member.delivery_start_date:
        raise HTTPException(status_code=400, detail="未到约定的开始配送日，无法确认送达")

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

    if member.balance < 1:
        raise HTTPException(status_code=400, detail="次数不足")
    member.balance -= 1

    db.add(
        BalanceLog(
            member_id=member_id,
            change=-1,
            reason=BalanceReason.DELIVERY.value,
            operator=courier_id,
        )
    )
    db.commit()

    try:
        from app.integrations.wechat_mini import try_notify_member_delivery_confirmed

        openid = (member.wx_mini_openid or "").strip()
        if openid:
            try_notify_member_delivery_confirmed(openid, delivery_date=d)
    except Exception:
        logger.exception("送达后订阅消息调度失败 member_id=%s", member_id)
