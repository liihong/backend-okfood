"""午餐 eligible 包装：纯晚餐会员误充午餐池时不进名单。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOrderPayStatus, DeliverySheetView
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.meal_period.card_eligibility import filter_members_for_sheet_view
from app.services.meal_period.lunch_delivery import eligible_members_for_lunch_delivery


@pytest.fixture()
def lunch_elig_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberCardOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="t", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="s",
                leave_deadline_time=time(21, 0),
                is_active=True,
            )
        )
        session.add(
            Member(
                id=501,
                tenant_id=1,
                store_id=1,
                phone="13000000501",
                name="纯晚",
                balance=10,
                is_active=True,
                delivery_start_date=date(2026, 6, 1),
                store_pickup=False,
            )
        )
        session.add(
            MemberCardOrder(
                member_id=501,
                tenant_id=1,
                store_id=1,
                card_kind="周卡",
                pay_channel="微信",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["dinner"],
                created_by="test",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_card_filter_excludes_pure_dinner_member(lunch_elig_db: Session) -> None:
    m = lunch_elig_db.get(Member, 501)
    assert m is not None
    filtered = filter_members_for_sheet_view(
        lunch_elig_db, [m], DeliverySheetView.LUNCH.value
    )
    assert filtered == []


def test_lunch_eligible_wrapper_excludes_pure_dinner_member(
    lunch_elig_db: Session, monkeypatch
) -> None:
    """包装层在 SQL eligible 之后做卡资格过滤（不依赖 SQLite least 函数）。"""
    m = lunch_elig_db.get(Member, 501)
    assert m is not None
    monkeypatch.setattr(
        "app.services.meal_period.lunch_delivery.eligible_members_for_delivery",
        lambda *a, **k: ([m], {501: None}),
    )
    members, defaults = eligible_members_for_lunch_delivery(
        lunch_elig_db, delivery_date=date(2026, 6, 10), store_id=1
    )
    assert members == []
    assert defaults == {}
