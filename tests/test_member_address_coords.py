"""会员地址保存：禁止无经纬度落库，改门牌不得清空已有坐标。"""

from __future__ import annotations

from datetime import time

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_operation_log import MemberOperationLog
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.member_address import MemberAddressCreateIn, MemberAddressUpdateIn
from app.schemas.user import Location
from app.services.member.member_address_service import create_address, update_address


@pytest.fixture()
def addr_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MemberOperationLog.__table__,
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
        m = Member(
            tenant_id=1,
            store_id=1,
            phone="13800001111",
            name="测用户",
            balance=0,
            is_active=False,
        )
        session.add(m)
        session.commit()
        session.refresh(m)
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def member(addr_db: Session) -> Member:
    return addr_db.query(Member).one()


def _patch_address_deps(monkeypatch: pytest.MonkeyPatch, *, geocode=None) -> None:
    monkeypatch.setattr(
        "app.services.member.member_address_service.guard_member_self_service_during_sf_fulfillment",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.member.member_address_service.assign_region_for_coords",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.member.member_address_service.amap.fetch_regeo_snapshot",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.member.member_address_service.amap.geocode_address",
        lambda _addr: geocode,
    )


def test_miniprogram_create_without_location_rejected(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch, geocode=None)
    body = MemberAddressCreateIn(
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        door_detail="1号楼",
    )
    with pytest.raises(HTTPException) as ei:
        create_address(addr_db, int(member.id), body, source="miniprogram")
    assert ei.value.status_code == 400
    assert addr_db.query(MemberAddress).count() == 0


def test_miniprogram_create_with_location_persists_coords(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch)
    body = MemberAddressCreateIn(
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        door_detail="1号楼",
        location=Location(lng=113.883, lat=35.303),
    )
    out = create_address(addr_db, int(member.id), body, source="miniprogram")
    assert out.location is not None
    assert out.location.lng == pytest.approx(113.883)
    assert out.location.lat == pytest.approx(35.303)
    row = addr_db.get(MemberAddress, out.id)
    assert row is not None
    assert float(row.lng) == pytest.approx(113.883)
    assert float(row.lat) == pytest.approx(35.303)


def test_create_rejects_zero_zero_coords(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch)
    body = MemberAddressCreateIn(
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        location=Location(lng=0, lat=0),
    )
    with pytest.raises(HTTPException) as ei:
        create_address(addr_db, int(member.id), body, source="miniprogram")
    assert ei.value.status_code == 400


def test_admin_create_geocode_fail_rejected(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch, geocode=None)
    body = MemberAddressCreateIn(
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="无法识别的POI简称",
    )
    with pytest.raises(HTTPException) as ei:
        create_address(addr_db, int(member.id), body, source="admin")
    assert ei.value.status_code == 400
    assert addr_db.query(MemberAddress).count() == 0


def test_patch_door_keeps_existing_coords_when_geocode_fails(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch, geocode=None)
    row = MemberAddress(
        member_id=int(member.id),
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        door_detail="1号楼",
        lng=113.883,
        lat=35.303,
        is_default=True,
    )
    addr_db.add(row)
    addr_db.commit()
    addr_db.refresh(row)

    out = update_address(
        addr_db,
        int(member.id),
        int(row.id),
        MemberAddressUpdateIn(door_detail="2号楼2707"),
        source="miniprogram",
    )
    assert out.location is not None
    assert out.location.lng == pytest.approx(113.883)
    assert out.location.lat == pytest.approx(35.303)
    fresh = addr_db.get(MemberAddress, row.id)
    assert fresh is not None
    assert (fresh.door_detail or "") == "2号楼2707"
    assert float(fresh.lng) == pytest.approx(113.883)
    assert float(fresh.lat) == pytest.approx(35.303)


def test_patch_address_text_without_coords_rejected(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch, geocode=None)
    row = MemberAddress(
        member_id=int(member.id),
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        door_detail="1号楼",
        lng=None,
        lat=None,
        is_default=True,
    )
    addr_db.add(row)
    addr_db.commit()
    addr_db.refresh(row)

    with pytest.raises(HTTPException) as ei:
        update_address(
            addr_db,
            int(member.id),
            int(row.id),
            MemberAddressUpdateIn(door_detail="2号楼"),
            source="miniprogram",
        )
    assert ei.value.status_code == 400
    addr_db.rollback()
    fresh = addr_db.get(MemberAddress, row.id)
    assert fresh is not None
    assert fresh.lng is None
    assert fresh.lat is None
    assert (fresh.door_detail or "") == "1号楼"


def test_patch_set_default_allows_missing_coords(
    addr_db: Session, member: Member, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_address_deps(monkeypatch)
    row = MemberAddress(
        member_id=int(member.id),
        contact_name="张三",
        contact_phone="13800001111",
        map_location_text="绿都城",
        lng=None,
        lat=None,
        is_default=False,
    )
    addr_db.add(row)
    addr_db.commit()
    addr_db.refresh(row)

    out = update_address(
        addr_db,
        int(member.id),
        int(row.id),
        MemberAddressUpdateIn(is_default=True),
        source="miniprogram",
    )
    assert out.is_default is True
    assert out.location is None
