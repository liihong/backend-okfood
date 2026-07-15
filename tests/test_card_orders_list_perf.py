"""开卡工单列表分页：批量序列化、按需 JOIN、深分页跳过 COUNT。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.enums import CardOrderPayStatus
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.services.member.member_card_order_service import list_card_orders_paged


def _seed_card_order(
    db: Session,
    *,
    member: Member,
    pay_status: str = CardOrderPayStatus.PAID.value,
    applied: bool = True,
    template: MembershipCardTemplate | None = None,
) -> MemberCardOrder:
    now = beijing_now_naive()
    order = MemberCardOrder(
        tenant_id=1,
        store_id=1,
        member_id=int(member.id),
        membership_template_id=int(template.id) if template else None,
        card_kind="周卡",
        pay_channel="微信",
        pay_status=pay_status,
        amount_yuan=Decimal("188.00"),
        applied_to_member=applied,
        created_by="admin_test",
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    db.flush()
    return order


def test_list_card_orders_batch_out_no_n_plus_one(
    db: Session, new_member: Member, mall_template: MembershipCardTemplate
):
    """批量序列化：多条工单应正确带出会员与模版信息。"""
    for _ in range(3):
        _seed_card_order(db, member=new_member, template=mall_template, applied=False)
    db.commit()

    items, total, has_more = list_card_orders_paged(
        db,
        q=None,
        pay_status=None,
        page=1,
        page_size=10,
        include_history=True,
        store_id=1,
    )
    assert total == 3
    assert has_more is False
    assert len(items) == 3
    assert all(i.member_phone == new_member.phone for i in items)
    assert all(
        i.template_product_label == f"{mall_template.name}（{mall_template.kind_label}）"
        for i in items
    )
    assert all(i.meal_periods == ["lunch"] for i in items)


def test_list_card_orders_pending_excludes_applied_paid(db: Session, new_member: Member):
    """待处理视图：隐藏已缴且已入账的完结单。"""
    _seed_card_order(db, member=new_member, pay_status=CardOrderPayStatus.PAID.value, applied=True)
    _seed_card_order(db, member=new_member, pay_status=CardOrderPayStatus.UNPAID.value, applied=False)
    db.commit()

    items, total, _ = list_card_orders_paged(
        db,
        q=None,
        pay_status=None,
        page=1,
        page_size=10,
        include_history=False,
        store_id=1,
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].pay_status == CardOrderPayStatus.UNPAID.value


def test_list_card_orders_history_page2_skips_count(db: Session, new_member: Member):
    """全量历史第 2 页起跳过 COUNT，total 为 None，has_more 由 limit+1 探测。"""
    for _ in range(5):
        _seed_card_order(db, member=new_member, applied=True)
    db.commit()

    page1, total1, has_more1 = list_card_orders_paged(
        db,
        q=None,
        pay_status=None,
        page=1,
        page_size=2,
        include_history=True,
        store_id=1,
    )
    assert total1 == 5
    assert len(page1) == 2
    assert has_more1 is True

    page2, total2, has_more2 = list_card_orders_paged(
        db,
        q=None,
        pay_status=None,
        page=2,
        page_size=2,
        include_history=True,
        store_id=1,
    )
    assert total2 is None
    assert len(page2) == 2
    assert has_more2 is True

    last_page, total_last, has_more_last = list_card_orders_paged(
        db,
        q=None,
        pay_status=None,
        page=3,
        page_size=2,
        include_history=True,
        store_id=1,
    )
    assert total_last is None
    assert len(last_page) >= 1
    assert has_more_last is False
