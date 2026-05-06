"""skip_subscription_saturday：周六从订阅到家名单排除（内存 SQLite）。"""

from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.models  # noqa: F401 — 加载全部表元数据
from app.models.member import Member as MemberModel
from app.models.member_address import MemberAddress as MemberAddressModel
from app.services.courier_service import eligible_members_for_delivery


@pytest.fixture
def units_sql_patch():
    """SQLite 无 LEAST/GREATEST，测试里用 daily_meal_units 列替代封顶 SQL。"""

    def _fake():
        return MemberModel.daily_meal_units

    with patch("app.services.courier_service.sql_effective_daily_meal_units_column", _fake):
        yield


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Mk = sessionmaker(bind=engine, class_=Session, future=True)
    s = Mk()
    try:
        yield s
    finally:
        s.close()


def _seed_member(
    db: Session,
    *,
    phone: str,
    skip_subscription_saturday: bool,
) -> None:
    m = MemberModel(
        phone=phone,
        name="T",
        balance=10,
        daily_meal_units=1,
        is_active=True,
        store_pickup=False,
        skip_subscription_saturday=skip_subscription_saturday,
    )
    db.add(m)
    db.flush()
    db.add(
        MemberAddressModel(
            member_id=m.id,
            contact_name="T",
            contact_phone=phone,
            delivery_region_id=None,
            map_location_text="x",
            door_detail=None,
            is_default=True,
        )
    )
    db.commit()


@patch("app.services.courier_service.is_subscription_delivery_day", return_value=True)
def test_eligible_excludes_skip_saturday_member_on_saturday(_mock_cal, db: Session, units_sql_patch):
    _seed_member(db, phone="13000000001", skip_subscription_saturday=True)
    _seed_member(db, phone="13000000002", skip_subscription_saturday=False)
    sat = date(2026, 5, 9)  # 周六
    with patch("app.services.courier_service.today_shanghai", return_value=date(2026, 5, 6)):
        rows, _defaults = eligible_members_for_delivery(db, delivery_date=sat, delivery_region_id=None)
    phones = {m.phone for m in rows}
    assert "13000000001" not in phones
    assert "13000000002" in phones


@patch("app.services.courier_service.is_subscription_delivery_day", return_value=True)
def test_eligible_includes_skip_member_on_monday(_mock_cal, db: Session, units_sql_patch):
    _seed_member(db, phone="13000000003", skip_subscription_saturday=True)
    mon = date(2026, 5, 4)  # 周一
    with patch("app.services.courier_service.today_shanghai", return_value=date(2026, 5, 4)):
        rows, _defaults = eligible_members_for_delivery(db, delivery_date=mon, delivery_region_id=None)
    assert any(m.phone == "13000000003" for m in rows)
