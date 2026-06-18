"""开卡工单更新入参：卡包模版与经典卡型互斥校验。"""

import pytest
from pydantic import ValidationError

from app.models.enums import CardOrderKind
from app.schemas.admin import CardOrderPatchIn


def test_card_order_patch_rejects_both_template_and_kind():
    with pytest.raises(ValidationError):
        CardOrderPatchIn(
            card_kind=CardOrderKind.WEEK,
            membership_template_id=1,
        )


def test_card_order_patch_accepts_membership_template_id():
    body = CardOrderPatchIn(membership_template_id=12)
    assert body.membership_template_id == 12
    assert body.card_kind is None
