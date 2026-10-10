from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
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
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.schemas.admin import (
    FinanceReceivedBucketOut,
    FinanceReceivedDayOut,
    FinanceReceivedMonthOut,
    FinanceReceivedSummaryOut,
    FinanceReceivedWindowOut,
    FinanceRetailSkuRevenueOut,
    FinanceRetailSkuRevenueRowOut,
    FinanceTodayPaidCardOrderRowOut,
    FinanceTodayPaidCardOrdersOut,
)
from app.services.retail.retail_display import retail_sku_display_title


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
    """按库内北京时间 naive 的 ``created_at`` 落在 [start, end) 统计已收（两端可空表示不限制）。"""
    card_conds = [MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value]
    if store_id is not None:
        card_conds.append(MemberCardOrder.store_id == int(store_id))
    if start is not None:
        card_conds.append(MemberCardOrder.created_at >= start)
    if end is not None:
        card_conds.append(MemberCardOrder.created_at < end)

    card_weekly = _card_kind_bucket(db, base_conds=card_conds, card_kind="周卡")
    card_monthly = _card_kind_bucket(db, base_conds=card_conds, card_kind="月卡")

    # 单次点餐实收仅统计微信支付；会员卡次数支付为 0 元核销，不计入金额
    sm_conds = [
        SingleMealOrder.pay_status == "已支付",
        or_(SingleMealOrder.pay_channel == "微信", SingleMealOrder.pay_channel.is_(None)),
    ]
    if store_id is not None:
        sm_conds.append(SingleMealOrder.store_id == int(store_id))
    if start is not None:
        sm_conds.append(SingleMealOrder.created_at >= start)
    if end is not None:
        sm_conds.append(SingleMealOrder.created_at < end)

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

    # 商城订单：仅统计当前仍为已支付的微信实收（已退款订单不计入）
    sr_conds = [StoreRetailOrder.pay_status == "已支付"]
    if store_id is not None:
        sr_conds.append(StoreRetailOrder.store_id == int(store_id))
    if start is not None:
        sr_conds.append(StoreRetailOrder.created_at >= start)
    if end is not None:
        sr_conds.append(StoreRetailOrder.created_at < end)

    sr_cnt, sr_sum = db.execute(
        select(
            func.count(StoreRetailOrder.id),
            func.coalesce(func.sum(StoreRetailOrder.amount_yuan), 0),
        ).where(*sr_conds)
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
    sr_amt = Decimal(str(sr_sum))
    r_amt = Decimal(str(r_sum)).quantize(Decimal("0.01"))
    c_n = int(c_cnt or 0)
    s_n = int(s_cnt or 0)
    sr_n = int(sr_cnt or 0)
    r_n = int(r_cnt or 0)
    gross = c_amt + s_amt + sr_amt
    net = (gross - r_amt).quantize(Decimal("0.01"))
    return FinanceReceivedWindowOut(
        total_amount_yuan=gross,
        total_count=c_n + s_n + sr_n,
        card_orders=FinanceReceivedBucketOut(count=c_n, amount_yuan=c_amt),
        card_orders_weekly=card_weekly,
        card_orders_monthly=card_monthly,
        single_meal_orders=FinanceReceivedBucketOut(count=s_n, amount_yuan=s_amt),
        store_retail_orders=FinanceReceivedBucketOut(count=sr_n, amount_yuan=sr_amt),
        membership_refunds=FinanceReceivedBucketOut(count=r_n, amount_yuan=r_amt),
        net_total_amount_yuan=net,
    )


def finance_paid_card_orders_for_day(
    db: Session,
    *,
    calendar_date: date | None = None,
    store_id: int | None = None,
) -> FinanceTodayPaidCardOrdersOut:
    """指定上海自然日（默认当日）已缴开卡工单明细，按工单创建时刻先后排序。"""
    day = calendar_date or today_shanghai()
    d0, d1 = shanghai_naive_range_for_calendar_day(day)
    conds = [
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        MemberCardOrder.created_at >= d0,
        MemberCardOrder.created_at < d1,
    ]
    if store_id is not None:
        conds.append(MemberCardOrder.store_id == int(store_id))

    rows = (
        db.execute(
            select(MemberCardOrder)
            .where(*conds)
            .order_by(MemberCardOrder.created_at.asc(), MemberCardOrder.id.asc())
        )
        .scalars()
        .all()
    )
    items = [
        FinanceTodayPaidCardOrderRowOut(
            order_id=int(r.id),
            time_hm=format_beijing_naive_hm(r.created_at),
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

    开卡工单、单次点餐与商城订单按 ``created_at``（北京时间 naive）落入日界；退卡按 ``created_at``。
    无单独 paid_at 字段时，以工单/订单创建时刻近似收款时刻。
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


def allocate_order_amount_to_lines(order_amount: Decimal, line_amounts: list[Decimal]) -> list[Decimal]:
    """按明细行金额比例分摊订单实收。

    优惠券记在订单头，行金额是券前小计。末行吃掉分位差，保证各行之和等于订单实收。
    """
    if not line_amounts:
        return []
    payable = Decimal(order_amount).quantize(Decimal("0.01"))
    if len(line_amounts) == 1:
        return [payable]
    total = sum((Decimal(v) for v in line_amounts), Decimal("0"))
    if total <= 0:
        shares = [Decimal("0.00")] * len(line_amounts)
        shares[0] = payable
        return shares
    shares: list[Decimal] = []
    remaining = payable
    last = len(line_amounts) - 1
    for i, line in enumerate(line_amounts):
        if i == last:
            shares.append(remaining)
            break
        share = (payable * Decimal(line) / total).quantize(Decimal("0.01"))
        if share > remaining:
            share = remaining
        remaining -= share
        shares.append(share)
    return shares


def _sku_display_name(
    *,
    spu_title: str | None,
    spec_label: str | None,
    product_title: str | None,
) -> str:
    """优先用 SPU + 规格；历史单只有订单标题时回退标题。"""
    spu = (spu_title or "").strip()
    if spu:
        return retail_sku_display_title(spu_title=spu, spec_label=spec_label)
    title = (product_title or "").strip()
    return title or "未命名 SKU"


def finance_retail_sku_revenue(
    db: Session,
    *,
    window: str,
    calendar_date: str | None = None,
    calendar_month: str | None = None,
    store_id: int | None = None,
) -> FinanceRetailSkuRevenueOut:
    """已支付商城订单按 SKU 汇总实收，口径与财务卡「商城订单」一致。

    window: day（上海自然日）/ month（上海自然月）/ cumulative（不限时间）。
    """
    kind = (window or "").strip().lower()
    anchor = today_shanghai()
    start: datetime | None
    end: datetime | None
    if kind == "day":
        day = _parse_calendar_date(calendar_date) if calendar_date else anchor
        if day > anchor:
            raise ValueError("不能查询未来日期")
        start, end = shanghai_naive_range_for_calendar_day(day)
        period_label = day.isoformat()
    elif kind == "month":
        if calendar_month:
            year, month = _parse_calendar_month(calendar_month)
        else:
            year, month = anchor.year, anchor.month
        if (year, month) > (anchor.year, anchor.month):
            raise ValueError("不能查询未来月份")
        start, end = shanghai_naive_range_for_calendar_month(year, month)
        period_label = f"{year:04d}-{month:02d}"
    elif kind == "cumulative":
        start, end = None, None
        period_label = "累计"
    else:
        raise ValueError("window 须为 day、month 或 cumulative")

    conds = [StoreRetailOrder.pay_status == "已支付"]
    if store_id is not None:
        conds.append(StoreRetailOrder.store_id == int(store_id))
    if start is not None:
        conds.append(StoreRetailOrder.created_at >= start)
    if end is not None:
        conds.append(StoreRetailOrder.created_at < end)

    orders = db.execute(select(StoreRetailOrder).where(*conds)).scalars().all()
    order_ids = [int(o.id) for o in orders]
    items_by_order: dict[int, list[StoreRetailOrderItem]] = defaultdict(list)
    if order_ids:
        item_rows = (
            db.execute(
                select(StoreRetailOrderItem)
                .where(StoreRetailOrderItem.order_id.in_(order_ids))
                .order_by(StoreRetailOrderItem.order_id.asc(), StoreRetailOrderItem.sort_order.asc())
            )
            .scalars()
            .all()
        )
        for it in item_rows:
            items_by_order[int(it.order_id)].append(it)

    # retail_product_id -> 汇总
    buckets: dict[int, dict] = {}

    def _touch(
        *,
        sku_id: int,
        sku_name: str,
        spu_title: str | None,
        spec_label: str | None,
        quantity: int,
        order_id: int,
        amount: Decimal,
    ) -> None:
        bucket = buckets.get(sku_id)
        if bucket is None:
            bucket = {
                "sku_name": sku_name,
                "spu_title": spu_title,
                "spec_label": spec_label,
                "quantity": 0,
                "order_ids": set(),
                "amount": Decimal("0.00"),
            }
            buckets[sku_id] = bucket
        elif sku_name and sku_name != "未命名 SKU":
            bucket["sku_name"] = sku_name
            bucket["spu_title"] = spu_title
            bucket["spec_label"] = spec_label
        bucket["quantity"] += int(quantity)
        bucket["order_ids"].add(int(order_id))
        bucket["amount"] += amount

    for order in orders:
        oid = int(order.id)
        payable = Decimal(order.amount_yuan or 0).quantize(Decimal("0.01"))
        lines = items_by_order.get(oid) or []
        if not lines:
            sku_id = int(order.retail_product_id or 0)
            if sku_id < 1:
                continue
            _touch(
                sku_id=sku_id,
                sku_name=_sku_display_name(
                    spu_title=None,
                    spec_label=None,
                    product_title=order.product_title,
                ),
                spu_title=None,
                spec_label=None,
                quantity=int(order.quantity or 0),
                order_id=oid,
                amount=payable,
            )
            continue
        shares = allocate_order_amount_to_lines(
            payable,
            [Decimal(it.line_amount_yuan or 0) for it in lines],
        )
        for it, share in zip(lines, shares, strict=True):
            sku_id = int(it.retail_product_id)
            _touch(
                sku_id=sku_id,
                sku_name=_sku_display_name(
                    spu_title=it.spu_title,
                    spec_label=it.spec_label,
                    product_title=it.product_title,
                ),
                spu_title=(it.spu_title or "").strip() or None,
                spec_label=(it.spec_label or "").strip() or None,
                quantity=int(it.quantity or 0),
                order_id=oid,
                amount=share,
            )

    rows = [
        FinanceRetailSkuRevenueRowOut(
            retail_product_id=sku_id,
            sku_name=str(bucket["sku_name"]),
            spu_title=bucket["spu_title"],
            spec_label=bucket["spec_label"],
            quantity=int(bucket["quantity"]),
            order_count=len(bucket["order_ids"]),
            amount_yuan=Decimal(bucket["amount"]).quantize(Decimal("0.01")),
        )
        for sku_id, bucket in buckets.items()
    ]
    rows.sort(key=lambda r: (-r.amount_yuan, -r.quantity, r.sku_name))
    total_amt = sum((r.amount_yuan for r in rows), Decimal("0.00")).quantize(Decimal("0.01"))
    return FinanceRetailSkuRevenueOut(
        window=kind,
        period_label=period_label,
        order_count=len(orders),
        amount_yuan=total_amt,
        items=rows,
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
