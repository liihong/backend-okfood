from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import (
    format_utc_naive_as_shanghai_hm,
    today_shanghai,
    utc_naive_range_for_shanghai_calendar_day,
    utc_naive_range_for_shanghai_calendar_month,
)
from app.models.enums import CardOrderPayStatus
from app.models.member_card_order import MemberCardOrder
from app.models.single_meal_order import SingleMealOrder
from app.schemas.admin import (
    FinanceReceivedBucketOut,
    FinanceReceivedSummaryOut,
    FinanceReceivedWindowOut,
    FinanceTodayPaidCardOrderRowOut,
    FinanceTodayPaidCardOrdersOut,
)


def _window_paid(
    db: Session,
    *,
    start_utc: datetime | None,
    end_utc: datetime | None,
    store_id: int | None = None,
) -> FinanceReceivedWindowOut:
    """按库内 naive UTC 的 updated_at 落在 [start_utc, end_utc) 统计已收（两端可空表示不限制）。"""
    card_conds = [MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value]
    if store_id is not None:
        card_conds.append(MemberCardOrder.store_id == int(store_id))
    if start_utc is not None:
        card_conds.append(MemberCardOrder.updated_at >= start_utc)
    if end_utc is not None:
        card_conds.append(MemberCardOrder.updated_at < end_utc)

    sm_conds = [SingleMealOrder.pay_status == "已支付"]
    if store_id is not None:
        sm_conds.append(SingleMealOrder.store_id == int(store_id))
    if start_utc is not None:
        sm_conds.append(SingleMealOrder.updated_at >= start_utc)
    if end_utc is not None:
        sm_conds.append(SingleMealOrder.updated_at < end_utc)

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

    c_amt = Decimal(str(c_sum))
    s_amt = Decimal(str(s_sum))
    c_n = int(c_cnt or 0)
    s_n = int(s_cnt or 0)
    return FinanceReceivedWindowOut(
        total_amount_yuan=c_amt + s_amt,
        total_count=c_n + s_n,
        card_orders=FinanceReceivedBucketOut(count=c_n, amount_yuan=c_amt),
        single_meal_orders=FinanceReceivedBucketOut(count=s_n, amount_yuan=s_amt),
    )


def finance_today_paid_card_orders(db: Session, *, store_id: int | None = None) -> FinanceTodayPaidCardOrdersOut:
    """今日（上海日界）已缴开卡工单明细，按收款时刻先后排序。"""
    day = today_shanghai()
    d0, d1 = utc_naive_range_for_shanghai_calendar_day(day)
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
            time_hm=format_utc_naive_as_shanghai_hm(r.updated_at),
            card_kind=(r.card_kind or "").strip() or "—",
            amount_yuan=Decimal(r.amount_yuan) if r.amount_yuan is not None else Decimal(0),
        )
        for r in rows
    ]
    return FinanceTodayPaidCardOrdersOut(shanghai_today=day, items=items)


def finance_received_summary(db: Session, *, store_id: int | None = None) -> FinanceReceivedSummaryOut:
    """汇总已收：累计、本月（上海自然月）、今日（上海自然日）。

    时间依据订单行的 updated_at（UTC 存库）；支付成功或后台改为已缴时会更新。
    已缴工单若之后仅改备注等也可能刷新 updated_at，属已知局限（无单独 paid_at 字段时）。
    """
    day = today_shanghai()
    m0, m1 = utc_naive_range_for_shanghai_calendar_month(day.year, day.month)
    d0, d1 = utc_naive_range_for_shanghai_calendar_day(day)
    ym = f"{day.year:04d}-{day.month:02d}"

    return FinanceReceivedSummaryOut(
        timezone_label="Asia/Shanghai",
        shanghai_today=day,
        shanghai_calendar_month=ym,
        cumulative=_window_paid(db, start_utc=None, end_utc=None, store_id=store_id),
        this_month=_window_paid(db, start_utc=m0, end_utc=m1, store_id=store_id),
        today=_window_paid(db, start_utc=d0, end_utc=d1, store_id=store_id),
    )
