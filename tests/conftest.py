"""pytest 公共 fixture：SQLite 内存库，覆盖小程序新用户购卡链路所需表。"""

from __future__ import annotations

from datetime import time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.admin_system_notification import AdminSystemNotification
from app.models.member import Member
from app.models.member_operation_log import MemberOperationLog
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant


@pytest.fixture()
def db() -> Session:
    """每个用例独立内存库，避免状态污染。"""
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
        AdminSystemNotification.__table__,
        MemberOperationLog.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        tenant = Tenant(id=1, name="测试租户", is_active=True)
        store = Store(
            id=1,
            tenant_id=1,
            name="测试门店",
            leave_deadline_time=time(21, 0),
            is_active=True,
        )
        session.add_all([tenant, store])
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def new_member(db: Session) -> Member:
    """新用户：无余额、无起送日、未激活。"""
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13500001111",
        name="待完善",
        balance=0,
        meal_quota_total=0,
        wx_mini_openid="openid_new_user_test",
        is_active=False,
        delivery_start_date=None,
        delivery_deferred=False,
        store_pickup=False,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@pytest.fixture()
def mall_template(db: Session) -> MembershipCardTemplate:
    tpl = MembershipCardTemplate(
        id=1,
        tenant_id=1,
        store_id=1,
        kind_label="周卡",
        name="一周午餐6次卡",
        meals_grant=6,
        sale_price_yuan=Decimal("188.00"),
        list_price_yuan=Decimal("188.00"),
        is_active=True,
        sort_order=0,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl
