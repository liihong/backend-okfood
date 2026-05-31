"""管理端微信原路退款：微信侧已 REFUND 但本地未同步时的幂等对齐。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.models.enums import CardOrderPayStatus, CardPayChannel
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.services.member_card_pay_service import admin_wechat_refund_member_card_order


def _paid_mall_order(
    db: Session, member: Member, template: MembershipCardTemplate
) -> MemberCardOrder:
    order = MemberCardOrder(
        tenant_id=1,
        store_id=1,
        member_id=int(member.id),
        membership_template_id=int(template.id),
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("178.00"),
        applied_to_member=False,
        out_trade_no="OKC776TEST0001",
        wx_transaction_id="420000776TEST",
        created_by="miniprogram",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@patch("app.services.member_card_pay_service.get_merged_pay_config")
@patch("app.services.member_card_pay_service.query_order_by_out_trade_no")
def test_refund_syncs_local_when_wechat_already_refund(
    mock_query,
    mock_pay_cfg,
    db: Session,
    new_member: Member,
    mall_template: MembershipCardTemplate,
) -> None:
    """模拟 #776：首次退款微信已成功，本地仍为「已缴」，重试应对齐为「已退款」。"""
    order = _paid_mall_order(db, new_member, mall_template)
    mock_pay_cfg.return_value = object()
    mock_query.return_value = {
        "result_code": "SUCCESS",
        "trade_state": "REFUND",
        "total_fee": "17800",
    }

    payload = admin_wechat_refund_member_card_order(
        db,
        order_id=int(order.id),
        store_id=1,
        require_mall_template=True,
    )

    assert "已同步" in payload["message"]
    db.expire_all()
    row = db.get(MemberCardOrder, order.id)
    assert row is not None
    assert row.pay_status == CardOrderPayStatus.REFUNDED.value


@patch("app.services.member_card_pay_service.get_merged_pay_config")
@patch("app.services.member_card_pay_service.query_order_by_out_trade_no")
def test_refund_wechat_refund_idempotent_when_local_already_refunded(
    mock_query,
    mock_pay_cfg,
    db: Session,
    new_member: Member,
    mall_template: MembershipCardTemplate,
) -> None:
    order = _paid_mall_order(db, new_member, mall_template)
    order.pay_status = CardOrderPayStatus.REFUNDED.value
    db.add(order)
    db.commit()

    mock_pay_cfg.return_value = object()
    mock_query.return_value = {"result_code": "SUCCESS", "trade_state": "REFUND", "total_fee": "17800"}

    with pytest.raises(ValueError, match="仅「已缴」"):
        admin_wechat_refund_member_card_order(
            db,
            order_id=int(order.id),
            store_id=1,
            require_mall_template=True,
        )
