"""
修复晚餐卡误入午餐次数池的历史数据。

用法（项目根目录）：
  python scripts/repair_dinner_card_mis_credited_to_lunch.py --order-id 1128
  python scripts/repair_dinner_card_mis_credited_to_lunch.py --dry-run --order-id 1128
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, MealPeriod, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.schemas.admin import RechargeIn
from app.services.admin_service import apply_member_recharge_delta
from app.services.meal_period.apply_side_effects import ensure_meal_period_states_after_card_apply
from app.services.meal_period.balance import apply_dinner_recharge_delta
from app.services.meal_period.template_periods import normalize_meal_periods_list


def _find_mis_credited_orders(db: Session, *, order_id: int | None) -> list[MemberCardOrder]:
    q = select(MemberCardOrder).where(
        MemberCardOrder.applied_to_member.is_(True),
        MemberCardOrder.meal_periods_snapshot.contains("dinner"),
    )
    if order_id is not None:
        q = q.where(MemberCardOrder.id == int(order_id))
    orders = list(db.scalars(q).all())
    out: list[MemberCardOrder] = []
    for order in orders:
        periods = normalize_meal_periods_list(order.meal_periods_snapshot)
        if MealPeriod.DINNER.value not in periods:
            continue
        detail_prefix = f"开卡工单#{order.id}"
        bad = db.scalar(
            select(BalanceLog.id).where(
                BalanceLog.member_id == int(order.member_id),
                BalanceLog.meal_period == MealPeriod.LUNCH.value,
                BalanceLog.reason == BalanceReason.RECHARGE.value,
                BalanceLog.change > 0,
                BalanceLog.detail.like(f"%{detail_prefix}%"),
            )
        )
        if bad is not None:
            out.append(order)
    return out


def _units_for_order(db: Session, order: MemberCardOrder) -> int:
    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if tpl:
            return max(1, int(tpl.meals_grant))
    from app.services.member_card_order_service import _quota_for_card_kind

    _, amt = _quota_for_card_kind(order.card_kind)
    return max(1, int(amt))


def repair_order(db: Session, order: MemberCardOrder, *, dry_run: bool) -> None:
    m = db.get(Member, int(order.member_id))
    if not m or m.deleted_at is not None:
        raise RuntimeError(f"工单#{order.id} 会员不存在")
    units = _units_for_order(db, order)
    lunch_before = int(m.balance or 0)
    if lunch_before < units:
        raise RuntimeError(
            f"工单#{order.id} 会员午餐剩余 {lunch_before} 不足扣回 {units} 次，请人工核对"
        )
    dinner_row = db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    dinner_before = int(dinner_row.balance or 0) if dinner_row else 0
    print(
        f"工单#{order.id} 会员{m.phone}({m.id}): "
        f"午餐 {lunch_before}->{lunch_before - units}, "
        f"晚餐 {dinner_before}->{dinner_before + units}"
    )
    if dry_run:
        return

    apply_member_recharge_delta(
        db,
        RechargeIn(phone=m.phone, amount=-units, plan_type=None),
        operator="system_repair",
        log_detail=f"修复：开卡工单#{order.id}晚餐卡误入午餐次数池，扣回{units}次",
        member_id=int(m.id),
    )
    # 正向午餐入账曾累加 meal_quota_total，扣回时须同步
    m.meal_quota_total = max(0, int(m.meal_quota_total or 0) - units)
    db.add(m)

    tpl_id = getattr(order, "membership_template_id", None)
    plan = PlanType.WEEK
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if tpl:
            from app.services.member_card_order_service import _plan_for_membership_template

            plan = _plan_for_membership_template(tpl)
    apply_dinner_recharge_delta(
        db,
        m,
        amount=units,
        plan_type=plan,
        bump_meal_quota_total=tpl_id is not None,
        operator="system_repair",
        log_detail=f"修复：开卡工单#{order.id}晚餐卡入账至晚餐次数池+{units}次",
    )
    ensure_meal_period_states_after_card_apply(db, m, order.meal_periods_snapshot)


def main() -> None:
    parser = argparse.ArgumentParser(description="晚餐卡误入午餐次数池修复")
    parser.add_argument("--order-id", type=int, default=None, help="仅修复指定工单")
    parser.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    args = parser.parse_args()

    engine = create_engine(get_settings().sqlalchemy_database_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        orders = _find_mis_credited_orders(db, order_id=args.order_id)
        if not orders:
            print("未发现需修复的晚餐卡工单")
            return
        for order in orders:
            repair_order(db, order, dry_run=args.dry_run)
        if not args.dry_run:
            db.commit()
            print("修复完成")
        else:
            db.rollback()
            print("dry-run 完成，未写库")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
