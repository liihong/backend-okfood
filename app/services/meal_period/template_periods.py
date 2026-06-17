"""模版餐段字段规范化（写入模版/工单 snapshot 时使用）。"""

from __future__ import annotations

from app.models.membership_card_template import MembershipCardTemplate
from app.services.meal_period.constants import DEFAULT_MEAL_PERIODS_SNAPSHOT


def normalize_meal_periods_list(raw: object) -> list[str]:
    """合法餐段仅 lunch / dinner；空则默认午餐。"""
    if not isinstance(raw, list):
        return list(DEFAULT_MEAL_PERIODS_SNAPSHOT)
    out: list[str] = []
    for x in raw:
        s = str(x).strip().lower()
        if s in ("lunch", "dinner") and s not in out:
            out.append(s)
    return out if out else list(DEFAULT_MEAL_PERIODS_SNAPSHOT)


def meal_periods_from_template(tpl: MembershipCardTemplate) -> list[str]:
    return normalize_meal_periods_list(getattr(tpl, "meal_periods", None))


def classic_card_meal_periods_snapshot() -> list[str]:
    """无模版的经典周/月/次卡：仅午餐。"""
    return list(DEFAULT_MEAL_PERIODS_SNAPSHOT)
