"""管理端零售订单手动建单：入参校验。

curl 示例（需管理员 Token；供餐日、坐标按实际替换）：

curl -sS -X POST "http://127.0.0.1:8000/api/admin/orders/single-meals?store_id=1" \\
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \\
  -d '{"phone":"13900001111","name":"体验用户","delivery_date":"2026-09-17","quantity":1,"pay_status":"已支付","pay_channel":"线下","delivery_address":{"contact_name":"体验用户","contact_phone":"13900001111","lng":113.92,"lat":35.30,"map_location_text":"河南省新乡市测试路1号"}}'
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.single_meal_order import AdminSingleMealOrderCreateIn


def _base_payload(**kwargs):
    body = {
        "phone": "13900001111",
        "name": "体验用户",
        "delivery_date": date(2026, 9, 17),
        "delivery_address": {
            "contact_name": "体验用户",
            "contact_phone": "13900001111",
            "lng": 113.92,
            "lat": 35.30,
            "map_location_text": "河南省新乡市牧野区测试路 1 号",
        },
    }
    body.update(kwargs)
    return body


def test_admin_single_meal_create_defaults_paid_one_portion() -> None:
    out = AdminSingleMealOrderCreateIn.model_validate(_base_payload())
    assert out.pay_status == "已支付"
    assert out.pay_channel == "线下"
    assert out.quantity == 1
    assert out.store_pickup is False
    assert out.meal_period == "lunch"


def test_admin_single_meal_create_requires_address_for_delivery() -> None:
    with pytest.raises(ValidationError):
        AdminSingleMealOrderCreateIn.model_validate(
            {
                "phone": "13900001111",
                "name": "体验用户",
                "delivery_date": date(2026, 9, 17),
            }
        )


def test_admin_single_meal_create_pickup_skips_address() -> None:
    out = AdminSingleMealOrderCreateIn.model_validate(
        _base_payload(store_pickup=True, delivery_address=None)
    )
    assert out.store_pickup is True
    assert out.delivery_address is None


def test_admin_single_meal_create_amount_optional() -> None:
    out = AdminSingleMealOrderCreateIn.model_validate(_base_payload(amount_yuan="36.00"))
    assert out.amount_yuan == Decimal("36.00")
