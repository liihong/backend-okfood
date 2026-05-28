"""会员顺丰推单快照查询：按手机号/业务日精确匹配，避免全表 LIKE。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from app.services.sf_order_fulfillment_service import (
    _member_active_sf_pushes_on_delivery_date,
    _member_sf_push_snapshot_match_clauses,
)


def test_snapshot_match_clauses_sqlite_uses_recv_phone_not_broad_like():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "sqlite"
    clauses = _member_sf_push_snapshot_match_clauses(
        db,
        member_id=42,
        member_phone="13800138000",
        single_meal_order_ids=[9],
    )
    compiled = " ".join(str(c) for c in clauses)
    assert "13800138000" in compiled
    assert "%13800138000%" not in compiled
    assert "recv_phone" in compiled
    assert "fulfillment_single_meal_order_ids" in compiled


def test_snapshot_match_clauses_mysql_uses_json_functions():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "mysql"
    clauses = _member_sf_push_snapshot_match_clauses(
        db,
        member_id=42,
        member_phone="13800138000",
        single_meal_order_ids=[9],
    )
    compiled = " ".join(str(c) for c in clauses).lower()
    assert "json_contains" in compiled
    assert "json_extract" in compiled
    assert "recv_phone" in compiled


def test_active_pushes_passes_phone_and_date_to_query():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "sqlite"
    pus = MagicMock()
    pus.id = 1
    db.scalars.return_value.all.side_effect = [[], [pus]]

    with patch(
        "app.services.sf_order_fulfillment_service._member_sf_push_snapshot_match_clauses",
        return_value=[MagicMock()],
    ) as mock_clauses, patch(
        "app.services.sf_order_fulfillment_service._member_on_sf_push",
        return_value=True,
    ):
        out = _member_active_sf_pushes_on_delivery_date(
            db,
            member_id=7,
            store_id=1,
            delivery_date=date(2026, 5, 28),
            member_phone="13800138000",
        )

    assert out == [pus]
    mock_clauses.assert_called_once_with(
        db,
        member_id=7,
        member_phone="13800138000",
        single_meal_order_ids=[],
    )
    db.get.assert_not_called()


def test_active_pushes_returns_empty_when_no_match_clauses():
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "sqlite"
    db.scalars.return_value.all.return_value = []

    with patch(
        "app.services.sf_order_fulfillment_service._member_sf_push_snapshot_match_clauses",
        return_value=[],
    ):
        out = _member_active_sf_pushes_on_delivery_date(
            db,
            member_id=7,
            store_id=1,
            delivery_date=date(2026, 5, 28),
            member_phone=None,
        )

    assert out == []
