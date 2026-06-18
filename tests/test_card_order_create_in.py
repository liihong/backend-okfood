"""开卡工单创建入参：卡包模版与经典卡型互斥校验。"""

import pytest
from pydantic import ValidationError

from app.models.enums import CardOrderKind, CardPayChannel, CardOrderPayStatus
from app.schemas.admin import CardOrderCreateIn


def test_card_order_create_requires_template_or_kind():
    with pytest.raises(ValidationError):
        CardOrderCreateIn(
            phone="13800138000",
            pay_channel=CardPayChannel.WECHAT,
        )


def test_card_order_create_rejects_both_template_and_kind():
    with pytest.raises(ValidationError):
        CardOrderCreateIn(
            phone="13800138000",
            pay_channel=CardPayChannel.WECHAT,
            card_kind=CardOrderKind.WEEK,
            membership_template_id=1,
        )


def test_card_order_create_accepts_membership_template_id():
    body = CardOrderCreateIn(
        phone="13800138000",
        pay_channel=CardPayChannel.WECHAT,
        pay_status=CardOrderPayStatus.PAID,
        membership_template_id=12,
    )
    assert body.membership_template_id == 12
    assert body.card_kind is None
