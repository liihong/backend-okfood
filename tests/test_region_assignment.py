"""region_assignment：非法 polygon 打日志；命中顺序按 priority。"""

import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 —注册 metadata

from app.db.base import Base
from app.models.delivery_region import DeliveryRegion
from app.services.region_assignment import assign_area_name_for_coords


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()


def test_assign_area_invalid_polygon_logged(caplog, db_session):
    db = db_session
    db.add(
        DeliveryRegion(
            name="bad_poly",
            code=None,
            polygon_json={"type": "Invalid"},
            priority=0,
            is_active=True,
        )
    )
    db.add(
        DeliveryRegion(
            name="good_zone",
            code=None,
            polygon_json=[[121.0, 31.0], [121.1, 31.0], [121.05, 31.1]],
            priority=1,
            is_active=True,
        )
    )
    db.commit()

    caplog.set_level(logging.WARNING)
    name = assign_area_name_for_coords(db, 121.05, 31.05)
    assert name == "good_zone"
    msgs = [r.getMessage() for r in caplog.records]
    assert any("bad_poly" in m and ("polygon" in m.lower() or "无效" in m) for m in msgs)


def test_assign_area_priority_order(db_session):
    db = db_session
    tri = [[121.0, 31.0], [121.1, 31.0], [121.05, 31.1]]
    db.add(DeliveryRegion(name="后", code=None, polygon_json=tri, priority=10, is_active=True))
    db.add(DeliveryRegion(name="先", code=None, polygon_json=tri, priority=0, is_active=True))
    db.commit()
    assert assign_area_name_for_coords(db, 121.05, 31.05) == "先"


def test_assign_area_unassigned(db_session):
    db = db_session
    db.add(
        DeliveryRegion(
            name="远区",
            code=None,
            polygon_json=[[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
            priority=0,
            is_active=True,
        )
    )
    db.commit()
    from app.constants import UNASSIGNED_DELIVERY_AREA

    assert assign_area_name_for_coords(db, 121.0, 31.0) == UNASSIGNED_DELIVERY_AREA
