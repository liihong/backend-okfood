"""配送停靠点 id 计算（与顺丰推单 stop_id 一致，供大表与推单共用）。"""

from __future__ import annotations

import hashlib
from datetime import date


def _stop_key(d: date, group_area: str, address_line: str) -> str:
    return hashlib.sha256(f"{d.isoformat()}|{group_area}|{address_line}".encode()).hexdigest()[:32]


def compute_delivery_stop_id(d: date, group_area: str, address_line: str) -> str:
    """配送停靠点 id（与顺丰推单 stop_id 一致）。"""
    return _stop_key(d, group_area, address_line)
