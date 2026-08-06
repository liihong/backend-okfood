"""顺丰监控页推单统计：回调 status 为 NULL 时仍应计入创单成功。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.sf_order_fulfillment_service import count_sf_same_city_pushes_for_delivery_date


@pytest.fixture()
def sf_stats_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        SfSameCityPush.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True))
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_count_success_includes_null_callback_status(sf_stats_db: Session) -> None:
    """创单成功且尚未收到回调时，success 应与 total 一致（勿因 NOT cancelled 为 UNKNOWN 漏计）。"""
    d = date(2026, 8, 6)
    rows = [
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id=f"stop-{i}",
            shop_order_id=f"OKF20260806stop{i:03d}",
            sf_order_id=f"SF{i:06d}",
            error_code=0,
            sf_callback_order_status=None,
        )
        for i in range(5)
    ]
    # 已收到非取消类回调，仍应计入成功
    rows.append(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-cb",
            shop_order_id="OKF20260806stopcb01",
            sf_order_id="SF000999",
            error_code=0,
            sf_callback_order_status=10,
        )
    )
    # 创单失败
    rows.append(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-fail",
            shop_order_id="OKF20260806stopfail",
            error_code=4001,
        )
    )
    # 已取消
    rows.append(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-cancel",
            shop_order_id="OKF20260806stopcancel",
            sf_order_id="SF000888",
            error_code=0,
            sf_callback_order_status=2,
        )
    )
    sf_stats_db.add_all(rows)
    sf_stats_db.commit()

    stats = count_sf_same_city_pushes_for_delivery_date(
        sf_stats_db, store_id=1, delivery_date=d
    )
    assert stats["total"] == 8
    assert stats["success"] == 6
    assert stats["failed"] == 1
    assert stats["cancelled"] == 1
    assert stats["success"] + stats["failed"] + stats["cancelled"] == stats["total"]
