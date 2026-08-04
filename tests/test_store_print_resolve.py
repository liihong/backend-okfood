"""门店打印场景解析：store_retail 回退 delivery_sheet 打印机。"""

from __future__ import annotations

from datetime import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.store import Store
from app.models.store_print_profile import StorePrintProfile
from app.models.store_print_scene_setting import StorePrintSceneSetting
from app.models.tenant import Tenant
from app.services.admin import store_print_service as svc


@pytest.fixture()
def print_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        StorePrintProfile.__table__,
        StorePrintSceneSetting.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True))
        session.add(
            StorePrintProfile(
                id=1,
                store_id=1,
                tenant_id=1,
                name="本地标签机",
                brand="local_label",
                paper_width_mm=76,
                paper_height_mm=130,
                is_active=True,
            )
        )
        session.add(
            StorePrintSceneSetting(
                store_id=1,
                scene="delivery_sheet",
                profile_id=1,
                template_key="delivery_meal_full",
                copies_mode="per_unit",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_store_retail_falls_back_to_delivery_sheet_printer(print_db: Session) -> None:
    """仅配置配送标签时，零售打印应能解析到同一台打印机。"""
    out = svc.resolve_print_config(print_db, store_id=1, scene="store_retail")
    assert out.configured is True
    assert out.profile_id == 1
    assert out.template_key == "delivery_meal_full"


def test_store_retail_without_any_printer_returns_not_configured(print_db: Session) -> None:
    """配送与零售均未绑定时，应返回未配置。"""
    print_db.query(StorePrintSceneSetting).delete()
    print_db.commit()
    out = svc.resolve_print_config(print_db, store_id=1, scene="store_retail")
    assert out.configured is False
