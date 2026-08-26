"""配送大表顺丰预览：全部片区不得扫入其它租户（含 OK饭租户 1）单次单。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.tenant_scope import sql_member_scope_clause
from app.db.base import Base
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery import sf_same_city_service as svc


@pytest.fixture()
def iso_db() -> Session:
    global _SMO_ID
    _SMO_ID = 0
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MenuDish.__table__,
        SingleMealOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="OK饭租户1", is_active=True),
                Tenant(id=2, name="其它租户", is_active=True),
                Store(id=1, tenant_id=1, name="OK饭门店", leave_deadline_time=time(21, 0), is_active=True),
                Store(id=2, tenant_id=2, name="其它门店", leave_deadline_time=time(21, 0), is_active=True),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member_with_addr(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    phone: str,
    name: str,
) -> tuple[Member, MemberAddress]:
    m = Member(
        tenant_id=tenant_id,
        store_id=store_id,
        phone=phone,
        name=name,
        balance=0,
        is_active=True,
    )
    db.add(m)
    db.flush()
    addr = MemberAddress(
        member_id=int(m.id),
        contact_name=name,
        contact_phone=phone,
        map_location_text="河南省许昌市魏都区测试路 1 号",
        door_detail="1 单元",
        is_default=True,
        lng=Decimal("113.82000000"),
        lat=Decimal("34.03000000"),
    )
    db.add(addr)
    db.flush()
    return m, addr


_SMO_ID = 0


def _next_smo_id() -> int:
    global _SMO_ID
    _SMO_ID += 1
    return _SMO_ID


def _paid_pending_single(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    member: Member,
    addr: MemberAddress,
    dish_name: str,
    routing_area: str,
    out_trade_no: str,
) -> SingleMealOrder:
    row = SingleMealOrder(
        id=_next_smo_id(),
        tenant_id=tenant_id,
        store_id=store_id,
        out_trade_no=out_trade_no,
        member_id=int(member.id),
        dish_name=dish_name,
        member_address_id=int(addr.id),
        store_pickup=False,
        quantity=1,
        delivery_date=date(2026, 8, 26),
        meal_period="lunch",
        routing_area=routing_area,
        amount_yuan=Decimal("18.00"),
        pay_status="已支付",
        fulfillment_status="pending",
    )
    db.add(row)
    db.flush()
    return row


def test_sql_member_scope_requires_both_tenant_and_store(iso_db: Session) -> None:
    """门店+租户同时传入时，租户 1 会员不得因 store_id 误配进入其它租户名单。"""
    m1, _ = _member_with_addr(
        iso_db, tenant_id=1, store_id=1, phone="13800000001", name="租户1会员"
    )
    ids = list(
        iso_db.scalars(
            select(Member.id).where(sql_member_scope_clause(tenant_id=2, store_id=1))
        ).all()
    )
    assert int(m1.id) not in {int(x) for x in ids}


def test_single_order_rows_all_areas_exclude_okfan_tenant1(iso_db: Session) -> None:
    d = date(2026, 8, 26)
    m1, a1 = _member_with_addr(
        iso_db, tenant_id=1, store_id=1, phone="13700893378", name="租户1收件人"
    )
    m2, a2 = _member_with_addr(
        iso_db, tenant_id=2, store_id=2, phone="13900000002", name="本店收件人"
    )
    _paid_pending_single(
        iso_db,
        tenant_id=1,
        store_id=1,
        member=m1,
        addr=a1,
        dish_name="照烧肥牛拌饭",
        routing_area="东南片区",
        out_trade_no="T1-001",
    )
    own = _paid_pending_single(
        iso_db,
        tenant_id=2,
        store_id=2,
        member=m2,
        addr=a2,
        dish_name="本店拌饭",
        routing_area="禹州片区",
        out_trade_no="T2-001",
    )
    iso_db.commit()

    leaked = svc._single_order_rows(iso_db, d, store_id=2, tenant_id=2, meal_period="lunch")
    order_ids = {int(o.id) for o, _m, _a, _d in leaked}
    assert int(own.id) in order_ids
    assert len(order_ids) == 1


def test_build_aggs_all_regions_exclude_okfan_tenant1_singles(
    iso_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """勾选「加载全部片区」时 area_key 为空，仍不得合并 OK饭租户 1 的单次单。"""
    monkeypatch.setattr(svc, "home_delivery_stops_for_aggs", lambda *a, **k: [])
    d = date(2026, 8, 26)
    m1, a1 = _member_with_addr(
        iso_db, tenant_id=1, store_id=1, phone="13700893378", name="租户1收件人"
    )
    m2, a2 = _member_with_addr(
        iso_db, tenant_id=2, store_id=2, phone="13900000002", name="本店收件人"
    )
    _paid_pending_single(
        iso_db,
        tenant_id=1,
        store_id=1,
        member=m1,
        addr=a1,
        dish_name="照烧肥牛拌饭",
        routing_area="东南片区",
        out_trade_no="T1-002",
    )
    _paid_pending_single(
        iso_db,
        tenant_id=2,
        store_id=2,
        member=m2,
        addr=a2,
        dish_name="本店拌饭",
        routing_area="禹州片区",
        out_trade_no="T2-002",
    )
    iso_db.commit()

    ags = svc._build_aggs(iso_db, d, None, None, [], {}, store_id=2, meal_period="lunch")
    labels = [s.get("label") or "" for a in ags.values() for s in a.singles]
    assert any("本店拌饭" in x for x in labels)
    assert not any("照烧肥牛拌饭" in x for x in labels)
    assert not any(a.group_area == "东南片区" for a in ags.values())
