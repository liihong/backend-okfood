"""礼品券卡型判定。

卡包「季卡」入账后工单 card_kind 与会员 plan_type 都会落成「月卡」，
因此先看模版 kind_label 是否含「季」，禁止用 members.plan_type 圈人。
"""

from __future__ import annotations

import json

from app.models.enums import CardOrderKind
from app.services.gift_coupon.constants import PLAN_KIND_MONTH, PLAN_KIND_QUARTER

_KIND_ALIASES = {
    "month": PLAN_KIND_MONTH,
    "quarter": PLAN_KIND_QUARTER,
    "月卡": PLAN_KIND_MONTH,
    "季卡": PLAN_KIND_QUARTER,
}


def normalize_plan_kinds(raw) -> list[str]:
    """MySQL JSON 偶发读成字符串时，归一成 ['month'] / ['quarter']。"""
    val = raw
    if isinstance(val, str):
        text = val.strip()
        try:
            val = json.loads(text)
        except json.JSONDecodeError:
            val = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
    if not isinstance(val, (list, tuple)):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in val:
        mapped = _KIND_ALIASES.get(str(item).strip())
        if mapped and mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    return out


def classify_gift_plan_kind(
    *,
    kind_label: str | None,
    card_kind: str | None,
    has_template: bool,
) -> str | None:
    """
    返回 month / quarter / None。

    - 种类含「季」→ 季卡（优先；季卡工单 card_kind 也会写成月卡）
    - 种类含「月」→ 月卡
    - 工单 card_kind=月卡（经典开卡，或午晚餐卡等不含月/季字的模版）→ 月卡
    """
    _ = has_template
    kl = (kind_label or "").strip()
    if "季" in kl:
        return PLAN_KIND_QUARTER
    if "月" in kl:
        return PLAN_KIND_MONTH
    if (card_kind or "").strip() == CardOrderKind.MONTH.value:
        return PLAN_KIND_MONTH
    return None


def plan_kind_matches(classified: str | None, selected: set[str]) -> bool:
    """classified 是否落在活动勾选的月卡/季卡集合内。"""
    if not classified:
        return False
    return classified in selected
