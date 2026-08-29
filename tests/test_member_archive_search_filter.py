"""会员档案库搜索框：手机号后四位也可模糊命中。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import PlanType
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.admin_service import _apply_member_list_filters


@pytest.fixture()
def search_db() -> Session:
    """档案库搜索所需最小表集（含默认地址子查询用到的 member_addresses）。"""
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _week_member(db: Session, *, phone: str, name: str) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=name,
        balance=6,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=True,
        delivery_start_date=date(2026, 1, 1),
    )
    db.add(m)
    db.flush()
    return m


def _search_phones(db: Session, q: str) -> set[str]:
    stmt = _apply_member_list_filters(
        select(Member.phone).select_from(Member),
        q_phone=q,
        validity=None,
        store_id=1,
    )
    return {str(x) for x in db.scalars(stmt).all()}


def test_search_matches_phone_last_four_digits(search_db: Session) -> None:
    hit = _week_member(search_db, phone="13800138000", name="张三")
    miss = _week_member(search_db, phone="13900139000", name="李四")
    search_db.commit()

    assert _search_phones(search_db, "8000") == {hit.phone}
    assert miss.phone not in _search_phones(search_db, "8000")


def test_search_still_matches_full_phone_and_name(search_db: Session) -> None:
    m = _week_member(search_db, phone="13612345678", name="王五")
    _week_member(search_db, phone="13712345679", name="赵六")
    search_db.commit()

    assert _search_phones(search_db, "13612345678") == {m.phone}
    assert _search_phones(search_db, "王五") == {m.phone}
