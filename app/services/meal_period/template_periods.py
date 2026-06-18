"""模版餐段字段规范化（写入模版/工单 snapshot 时使用）。"""

from __future__ import annotations

import json

from app.models.membership_card_template import MembershipCardTemplate
from app.services.meal_period.constants import DEFAULT_MEAL_PERIODS_SNAPSHOT


def _coerce_meal_periods_raw(raw: object) -> list[object]:
    """JSON 列偶发以字符串读出时先解析，避免晚餐 snapshot 被误判为午餐。"""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return []
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def normalize_meal_periods_list(raw: object) -> list[str]:
    """合法餐段仅 lunch / dinner；空则默认午餐。"""
    out: list[str] = []
    for x in _coerce_meal_periods_raw(raw):
        s = str(x).strip().lower()
        if s in ("lunch", "dinner") and s not in out:
            out.append(s)
    return out if out else list(DEFAULT_MEAL_PERIODS_SNAPSHOT)


def meal_periods_from_template(tpl: MembershipCardTemplate) -> list[str]:
    return normalize_meal_periods_list(getattr(tpl, "meal_periods", None))


def classic_card_meal_periods_snapshot() -> list[str]:
    """无模版的经典周/月/次卡：仅午餐。"""
    return list(DEFAULT_MEAL_PERIODS_SNAPSHOT)
