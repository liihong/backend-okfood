"""管理端商城订单手动建单：请求体验证。"""

import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.douyin import AdminDouyinCertificateRedeemIn
from app.schemas.store_retail_order import AdminStoreRetailOrderCreateIn


def test_admin_store_retail_order_create_requires_address_for_delivery():
    with pytest.raises(ValidationError):
        AdminStoreRetailOrderCreateIn(
            phone="13800138000",
            retail_product_id=1,
            store_pickup=False,
            member_address_id=None,
            pay_channel="线下",
        )


def test_admin_store_retail_order_create_pickup_ok():
    body = AdminStoreRetailOrderCreateIn(
        phone="13800138000",
        name="测试会员",
        retail_product_id=2,
        store_pickup=True,
        pay_channel="抖音",
        pay_status="已支付",
        amount_yuan=Decimal("268.00"),
    )
    assert body.quantity == 1
    assert body.pay_status == "已支付"


def test_admin_douyin_redeem_in_min_code():
    body = AdminDouyinCertificateRedeemIn(phone="13800138000", code="1234")
    assert body.code == "1234"
