from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai, utc_naive_range_for_shanghai_calendar_day, utc_naive_range_for_shanghai_calendar_month
from app.models.enums import CardOrderPayStatus
from app.models.member_card_order import MemberCardOrder
from app.models.single_meal_order import SingleMealOrder
from app.schemas.admin import FinanceReceivedBucketOut, FinanceReceivedSummaryOut, FinanceReceivedWindowOut


def _window_paid(
    db: Session,
    *,
    start_utc: datetime | None,
    end_utc: datetime | None,
) -> FinanceReceivedWindowOut:
    """按库内 naive UTC 的 updated_at 落在 [start_utc, end_utc) 统计已收（两端可空表示不限制）。"""
    card_conds = [MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value]
    if start_utc is not None:
        card_conds.append(MemberCardOrder.updated_at >= start_utc)
    if end_utc is not None:
        card_conds.append(MemberCardOrder.updated_at < end_utc)

    sm_conds = [SingleMealOrder.pay_status == "已支付"]
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


def finance_received_summary(db: Session) -> FinanceReceivedSummaryOut:
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
        cumulative=_window_paid(db, start_utc=None, end_utc=None),
        this_month=_window_paid(db, start_utc=m0, end_utc=m1),
        today=_window_paid(db, start_utc=d0, end_utc=d1),
    )
