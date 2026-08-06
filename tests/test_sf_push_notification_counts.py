"""顺丰推单系统消息统计：与监控页口径一致，且不含「未勾选」等伪成功。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import SfSameCityPushItemResult
from app.services.admin.admin_system_notification_service import compute_sf_push_notification_counts
from app.services.delivery.sf_same_city_service import summarize_sf_push_batch_results


@pytest.fixture()
def sf_notify_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [Tenant.__table__, Store.__table__, SfSameCityPush.__table__]
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


def test_summarize_excludes_unselected_skip_rows() -> None:
    results = [
        SfSameCityPushItemResult(stop_id="a", ok=True, message="已跳过（未勾选）", sf_order_id=None),
        SfSameCityPushItemResult(stop_id="b", ok=True, message="已提交顺丰", sf_order_id="SF1"),
        SfSameCityPushItemResult(stop_id="c", ok=False, message="创单失败", sf_order_id=None),
    ]
    total, success, failed = summarize_sf_push_batch_results(results)
    assert total == 2
    assert success == 1
    assert failed == 1


def test_compute_aligns_success_with_monitor_db(sf_notify_db: Session) -> None:
    d = date(2026, 8, 6)
    sf_notify_db.add_all(
        [
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id=f"stop-{i}",
                shop_order_id=f"OKF20260806s{i:03d}",
                sf_order_id=f"SF{i:04d}",
                error_code=0,
                sf_callback_order_status=None,
            )
            for i in range(3)
        ]
        + [
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-fail",
                shop_order_id="OKF20260806fail",
                error_code=4001,
            )
        ]
    )
    sf_notify_db.commit()

    batch = [
        SfSameCityPushItemResult(stop_id=f"stop-{i}", ok=True, message="已提交顺丰", sf_order_id=f"SF{i:04d}")
        for i in range(3)
    ] + [
        SfSameCityPushItemResult(stop_id="stop-fail", ok=False, message="余额不足", sf_order_id=None),
        SfSameCityPushItemResult(
            stop_id="stop-pre",
            ok=False,
            message="配送地址缺少有效坐标，不可推顺丰",
            sf_order_id=None,
        ),
    ]
    total, success, failed = compute_sf_push_notification_counts(
        sf_notify_db,
        store_id=1,
        delivery_date=d,
        push_results=batch,
    )
    assert success == 3
    assert failed == 2
    assert total == 5
