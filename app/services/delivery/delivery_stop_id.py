"""配送停靠点 id 计算（与顺丰推单 stop_id 一致，供大表与推单共用）。"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any


def _stop_key(d: date, group_area: str, address_line: str, member_id: int) -> str:
    """一名会员一个停靠点：同址不同会员不得共用 stop_id。"""
    return hashlib.sha256(
        f"{d.isoformat()}|{group_area}|{address_line}|m{int(member_id)}".encode()
    ).hexdigest()[:32]


def compute_delivery_stop_id(
    d: date, group_area: str, address_line: str, member_id: int
) -> str:
    """配送停靠点 id（与顺丰推单 stop_id 一致）。"""
    return _stop_key(d, group_area, address_line, member_id)


def compute_legacy_address_stop_id(d: date, group_area: str, address_line: str) -> str:
    """历史同址合并口径（不含会员 id），仅用于匹配当日已推的旧合并单。"""
    return hashlib.sha256(f"{d.isoformat()}|{group_area}|{address_line}".encode()).hexdigest()[
        :32
    ]


def member_ids_from_sf_push_snapshot(snap: Any) -> list[int]:
    """创单快照 ``fulfillment_member_ids``；旧同址合并单靠此对齐拆分后的会员停靠点。"""
    if not isinstance(snap, dict):
        return []
    raw = snap.get("fulfillment_member_ids")
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            pass
    return out
