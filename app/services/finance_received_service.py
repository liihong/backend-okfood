from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import (
    format_beijing_naive_hm,
    shanghai_naive_range_for_calendar_day,
    shanghai_naive_range_for_calendar_month,
    today_shanghai,
)
from app.models.enums import CardOrderPayStatus
from app.models.member_card_order import MemberCardOrder
from app.models.member_membership_refund import MemberMembershipRefund
from app.models.single_meal_order import SingleMealOrder
from app.schemas.admin import (
    FinanceReceivedBucketOut,
    FinanceReceivedDayOut,
    FinanceReceivedMonthOut,
    FinanceReceivedSummaryOut,
    FinanceReceivedWindowOut,
    FinanceTodayPaidCardOrderRowOut,
    FinanceTodayPaidCardOrdersOut,
)


def _parse_calendar_date(value: str) -> date:
    """解析 YYYY-MM-DD 为上海日历日，非法格式抛出 ValueError。"""
    raw = (value or "").strip()
    parts = raw.split("-")
    if len(parts) != 3:
        raise ValueError("calendar_date 须为 YYYY-MM-DD")
    year, month, day_num = int(parts[0]), int(parts[1]), int(parts[2])
    return date(year, month, day_num)


def _parse_calendar_month(value: str) -> tuple[int, int]:
    """解析 YYYY-MM 为 (year, month)，非法格式抛出 ValueError。"""
    raw = (value or "").strip()
    parts = raw.split("-")
    if len(parts) != 2:
        raise ValueError("calendar_month 须为 YYYY-MM")
    year = int(parts[0])
    month = int(parts[1])
    if year < 2000 or year > 2100 or month < 1 or month > 12:
        raise ValueError("calendar_month 年月无效")
    return year, month


def _card_kind_bucket(
    db: Session,
    *,
    base_conds: list,
    card_kind: str,
) -> FinanceReceivedBucketOut:
    """在已缴开卡工单条件上按卡型（周卡 / 月卡）再聚合。"""
    cnt, amt = db.execute(
        select(
            func.count(MemberCardOrder.id),
            func.coalesce(func.sum(MemberCardOrder.amount_yuan), 0),
        ).where(*base_conds, MemberCardOrder.card_kind == card_kind)
    ).one()
    return FinanceReceivedBucketOut(
        count=int(cnt or 0),
        amount_yuan=Decimal(str(amt)),
    )


def _window_paid(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
    store_id: int | None = None,
) -> FinanceReceivedWindowOut:
    """按库内北京时间 naive 的 ``updated_at`` 落在 [start, end) 统计已收（两端可空表示不限制）。"""
    card_conds = [MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value]
    if store_id is not None:
        card_conds.append(MemberCardOrder.store_id == int(store_id))
    if start is not None:
        card_conds.append(MemberCardOrder.updated_at >= start)
    if end is not None:
        card_conds.append(MemberCardOrder.updated_at < end)

    card_weekly = _card_kind_bucket(db, base_conds=card_conds, card_kind="周卡")
    card_monthly = _card_kind_bucket(db, base_conds=card_conds, card_kind="月卡")

    sm_conds = [SingleMealOrder.pay_status == "已支付"]
    if store_id is not None:
        sm_conds.append(SingleMealOrder.store_id == int(store_id))
    if start is not None:
        sm_conds.append(SingleMealOrder.updated_at >= start)
    if end is not None:
        sm_conds.append(SingleMealOrder.updated_at < end)

    c_cnt, c_sum = db.execute(
        select(
            func.count(MemberCardOrder.id),
            func.coalesce(func.sum(MemberCardOrder.amount_yuan), 0),
        ).where(*card_conds)
    ).one()
    s_cnt, s_sum = db.execute(
        select(
            func.count(SingleMealOrder.id),
            func.coalesce(func.sum(SingleMealOrder.amount_yuan), 0),
        ).where(*sm_conds)
    ).one()

    refund_conds = []
    if store_id is not None:
        refund_conds.append(MemberMembershipRefund.store_id == int(store_id))
    if start is not None:
        refund_conds.append(MemberMembershipRefund.created_at >= start)
    if end is not None:
        refund_conds.append(MemberMembershipRefund.created_at < end)
    if refund_conds:
        r_cnt, r_sum = db.execute(
            select(
                func.count(MemberMembershipRefund.id),
                func.coalesce(func.sum(MemberMembershipRefund.refund_amount_yuan), 0),
            ).where(*refund_conds)
        ).one()
    else:
        r_cnt, r_sum = db.execute(
            select(
                func.count(MemberMembershipRefund.id),
                func.coalesce(func.sum(MemberMembershipRefund.refund_amount_yuan), 0),
            )
        ).one()

    c_amt = Decimal(str(c_sum))
    s_amt = Decimal(str(s_sum))
    r_amt = Decimal(str(r_sum)).quantize(Decimal("0.01"))
    c_n = int(c_cnt or 0)
    s_n = int(s_cnt or 0)
    r_n = int(r_cnt or 0)
    gross = c_amt + s_amt
    net = (gross - r_amt).quantize(Decimal("0.01"))
    return FinanceReceivedWindowOut(
        total_amount_yuan=gross,
        total_count=c_n + s_n,
        card_orders=FinanceReceivedBucketOut(count=c_n, amount_yuan=c_amt),
        card_orders_weekly=card_weekly,
        card_orders_monthly=card_monthly,
        single_meal_orders=FinanceReceivedBucketOut(count=s_n, amount_yuan=s_amt),
        membership_refunds=FinanceReceivedBucketOut(count=r_n, amount_yuan=r_amt),
        net_total_amount_yuan=net,
    )


def finance_paid_card_orders_for_day(
    db: Session,
    *,
    calendar_date: date | None = None,
    store_id: int | None = None,
) -> FinanceTodayPaidCardOrdersOut:
    """指定上海自然日（默认当日）已缴开卡工单明细，按收款时刻先后排序。"""
    day = calendar_date or today_shanghai()
    d0, d1 = shanghai_naive_range_for_calendar_day(day)
    conds = [
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        MemberCardOrder.updated_at >= d0,
        MemberCardOrder.updated_at < d1,
    ]
    if store_id is not None:
        conds.append(MemberCardOrder.store_id == int(store_id))

    rows = (
        db.execute(
            select(MemberCardOrder)
            .where(*conds)
            .order_by(MemberCardOrder.updated_at.asc(), MemberCardOrder.id.asc())
        )
        .scalars()
        .all()
    )
    items = [
        FinanceTodayPaidCardOrderRowOut(
            order_id=int(r.id),
            time_hm=format_beijing_naive_hm(r.updated_at),
            card_kind=(r.card_kind or "").strip() or "—",
            amount_yuan=Decimal(r.amount_yuan) if r.amount_yuan is not None else Decimal(0),
        )
        for r in rows
    ]
    return FinanceTodayPaidCardOrdersOut(shanghai_today=day, items=items)


def finance_today_paid_card_orders(db: Session, *, store_id: int | None = None) -> FinanceTodayPaidCardOrdersOut:
    """今日（上海日界）已缴开卡工单明细。"""
    return finance_paid_card_orders_for_day(db, calendar_date=None, store_id=store_id)


def finance_received_day_window(
    db: Session,
    *,
    calendar_date: str,
    store_id: int | None = None,
) -> FinanceReceivedDayOut:
    """指定上海自然日已收汇总；不可查询未来日期。"""
    day = _parse_calendar_date(calendar_date)
    anchor = today_shanghai()
    if day > anchor:
        raise ValueError("不能查询未来日期")
    d0, d1 = shanghai_naive_range_for_calendar_day(day)
    return FinanceReceivedDayOut(
        calendar_date=day,
        window=_window_paid(db, start=d0, end=d1, store_id=store_id),
    )


def finance_received_summary(db: Session, *, store_id: int | None = None) -> FinanceReceivedSummaryOut:
    """汇总已收：累计、本月（上海自然月）、今日（上海自然日）。

    时间依据订单行的 ``updated_at``（北京时间 naive）；支付成功或后台改为已缴时会更新。
    已缴工单若之后仅改备注等也可能刷新 ``updated_at``，属已知局限（无单独 paid_at 字段时）。
    """
    day = today_shanghai()
    m0, m1 = shanghai_naive_range_for_calendar_month(day.year, day.month)
    d0, d1 = shanghai_naive_range_for_calendar_day(day)
    ym = f"{day.year:04d}-{day.month:02d}"

    return FinanceReceivedSummaryOut(
        timezone_label="Asia/Shanghai",
        shanghai_today=day,
        shanghai_calendar_month=ym,
        cumulative=_window_paid(db, start=None, end=None, store_id=store_id),
        this_month=_window_paid(db, start=m0, end=m1, store_id=store_id),
        today=_window_paid(db, start=d0, end=d1, store_id=store_id),
    )


def finance_received_month_window(
    db: Session,
    *,
    calendar_month: str,
    store_id: int | None = None,
) -> FinanceReceivedMonthOut:
    """指定上海自然月已收汇总；不可查询未来月份。"""
    year, month = _parse_calendar_month(calendar_month)
    day = today_shanghai()
    if (year, month) > (day.year, day.month):
        raise ValueError("不能查询未来月份")
    m0, m1 = shanghai_naive_range_for_calendar_month(year, month)
    ym = f"{year:04d}-{month:02d}"
    return FinanceReceivedMonthOut(
        calendar_month=ym,
        window=_window_paid(db, start=m0, end=m1, store_id=store_id),
    )
