"""商城订单：支付后待接单、后台接单进入待发货。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_product import StoreRetailProduct
from app.models.tenant import Tenant
from app.services.admin.store_retail_order_admin_service import (
    admin_accept_store_retail_order,
    admin_update_store_retail_order_delivery,
    list_admin_store_retail_orders,
)
from app.services.client.store_retail_order_service import (
    _FULFILLMENT_AWAITING_ACCEPT,
    finalize_store_retail_order_wechat_pay,
)
from app.integrations.wechat_pay_v2 import WechatPayNotifyParsed


@pytest.fixture()
def retail_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        StoreRetailProduct.__table__,
        StoreRetailOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.add(Member(id=1, tenant_id=1, store_id=1, name="m", phone="13800000000", balance=0))
    session.add(
        StoreRetailProduct(
            id=1,
            store_id=1,
            title="juice",
            unit_price_yuan=Decimal("98.00"),
            is_on_shelf=True,
        )
    )
    session.flush()
    yield session
    session.close()
    engine.dispose()


def _add_order(
    db: Session,
    *,
    oid: int,
    pay_status: str = "未支付",
    fulfillment_status: str = "pending",
    store_pickup: bool = False,
) -> None:
    db.add(
        StoreRetailOrder(
            id=oid,
            tenant_id=1,
            store_id=1,
            out_trade_no=f"RO{oid:08d}",
            member_id=1,
            retail_product_id=1,
            product_title="juice",
            store_pickup=store_pickup,
            quantity=1,
            fulfillment_date=date(2026, 7, 8),
            routing_area="A区",
            amount_yuan=Decimal("98.00"),
            pay_status=pay_status,
            fulfillment_status=fulfillment_status,
        )
    )


def test_finalize_pay_sets_awaiting_accept(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, store_pickup=True)
    retail_db.commit()
    order = retail_db.get(StoreRetailOrder, 1)
    with (
        patch("app.services.client.store_retail_order_service._notify_store_retail_order_paid"),
        patch("app.services.client.store_retail_order_service.mark_member_coupon_used_for_order"),
    ):
        ok, reason = finalize_store_retail_order_wechat_pay(
            retail_db,
            WechatPayNotifyParsed(out_trade_no=order.out_trade_no, transaction_id="wx1", total_fee=9800),
        )
    assert ok is True
    assert reason == "paid"
    retail_db.refresh(order)
    assert order.pay_status == "已支付"
    assert order.fulfillment_status == _FULFILLMENT_AWAITING_ACCEPT


def test_awaiting_accept_tab_only_shows_paid_awaiting(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, pay_status="已支付", fulfillment_status=_FULFILLMENT_AWAITING_ACCEPT)
    _add_order(retail_db, oid=2, pay_status="未支付", fulfillment_status="pending")
    _add_order(retail_db, oid=3, pay_status="已支付", fulfillment_status="pending")
    retail_db.commit()

    items, total = list_admin_store_retail_orders(
        retail_db, store_id=1, fulfillment_phase="awaiting_accept"
    )
    assert total == 1
    assert len(items) == 1
    assert items[0].id == 1


def test_admin_accept_moves_to_pending_ship(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, pay_status="已支付", fulfillment_status=_FULFILLMENT_AWAITING_ACCEPT)
    retail_db.commit()

    out = admin_accept_store_retail_order(retail_db, order_id=1, store_id=1)
    assert out.fulfillment_status == "pending"

    _, pending_total = list_admin_store_retail_orders(
        retail_db, store_id=1, fulfillment_phase="pending_ship"
    )
    assert pending_total == 1


def test_admin_update_delivery_awaiting_accept(retail_db: Session) -> None:
    retail_db.add(
        MemberAddress(
            id=10,
            member_id=1,
            contact_name="张三",
            contact_phone="13800000000",
            map_location_text="某小区",
            door_detail="1号楼",
            lng=121.0,
            lat=31.0,
            is_default=True,
        )
    )
    _add_order(
        retail_db,
        oid=1,
        pay_status="已支付",
        fulfillment_status=_FULFILLMENT_AWAITING_ACCEPT,
        store_pickup=True,
    )
    retail_db.commit()

    out = admin_update_store_retail_order_delivery(
        retail_db,
        order_id=1,
        store_id=1,
        store_pickup=False,
        member_address_id=10,
    )
    assert out.store_pickup is False
    assert out.member_address_id == 10
    assert out.routing_area != "门店自提"

    order = retail_db.get(StoreRetailOrder, 1)
    assert order is not None
    assert order.store_pickup is False
    assert int(order.member_address_id or 0) == 10


def test_admin_update_delivery_rejects_in_delivery(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, pay_status="已支付", fulfillment_status="accepted")
    retail_db.commit()

    with pytest.raises(ValueError, match="配送中"):
        admin_update_store_retail_order_delivery(
            retail_db,
            order_id=1,
            store_id=1,
            store_pickup=True,
            member_address_id=None,
        )
