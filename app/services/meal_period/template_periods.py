"""模版餐段字段规范化（写入模版/工单 snapshot 时使用）。"""

from __future__ import annotations

import json

from app.models.enums import MealPeriod
from app.models.membership_card_template import MembershipCardTemplate
from app.services.meal_period.constants import DEFAULT_MEAL_PERIODS_SNAPSHOT

# 全餐卡常见运营文案：meal_periods 漏配晚餐时用于补全推断
_FULL_MEAL_LABEL_MARKERS = (
    "全餐",
    "午晚",
    "午餐晚餐",
    "午晚餐",
    "双餐",
    "午餐+晚餐",
    "午餐＋晚餐",
)

# 纯晚餐卡常见运营文案
_DINNER_ONLY_LABEL_MARKERS = (
    "晚餐卡",
    "晚饭卡",
    "仅晚餐",
    "纯晚餐",
)


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


def _infer_meal_periods_from_template_labels(name: str, kind_label: str) -> list[str] | None:
    """
    从模版名称/种类推断餐段。

    仅作 meal_periods 未配置或仍为迁移默认午餐时的补全，避免「午餐晚餐全餐卡」仅入午餐池。
    """
    text = f"{name or ''} {kind_label or ''}"
    if not text.strip():
        return None
    if any(marker in text for marker in _FULL_MEAL_LABEL_MARKERS):
        return [MealPeriod.LUNCH.value, MealPeriod.DINNER.value]
    if any(marker in text for marker in _DINNER_ONLY_LABEL_MARKERS):
        return [MealPeriod.DINNER.value]
    return None


def meal_periods_from_template(tpl: MembershipCardTemplate) -> list[str]:
    """读取模版餐段；空或默认午餐时尝试从商品文案推断午/晚范围。"""
    raw = getattr(tpl, "meal_periods", None)
    explicit = normalize_meal_periods_list(raw)
    raw_items = _coerce_meal_periods_raw(raw)
    # 库内未写入有效餐段，或 migration_046 后仍为默认 ["lunch"] 时，用语义推断补全
    if raw_items == [] or explicit == list(DEFAULT_MEAL_PERIODS_SNAPSHOT):
        inferred = _infer_meal_periods_from_template_labels(
            getattr(tpl, "name", "") or "",
            getattr(tpl, "kind_label", "") or "",
        )
        if inferred:
            return inferred
    return explicit


def classic_card_meal_periods_snapshot() -> list[str]:
    """无模版的经典周/月/次卡：仅午餐。"""
    return list(DEFAULT_MEAL_PERIODS_SNAPSHOT)


def resolve_meal_periods_for_card_order_credit(
    *,
    order_meal_periods_snapshot: object,
    template: MembershipCardTemplate | None,
    use_classic_lunch_only: bool = False,
) -> list[str]:
    """
    开卡入账餐段：模版（含名称推断）与工单既有快照取并集。

    防止全餐卡因模版 meal_periods 漏配晚餐、或创建/入账之间快照不一致而只写入午餐次数池。
    工单尚无快照（NULL/[]）时不把「默认午餐」并入并集，避免纯晚餐卡误入午餐池。
    """
    if use_classic_lunch_only or template is None:
        from_template = classic_card_meal_periods_snapshot()
    else:
        from_template = meal_periods_from_template(template)
    raw_existing = _coerce_meal_periods_raw(order_meal_periods_snapshot)
    existing = normalize_meal_periods_list(order_meal_periods_snapshot) if raw_existing else []
    merged: list[str] = []
    for src in (from_template, existing):
        for period in src:
            if period not in merged:
                merged.append(period)
    return merged if merged else list(DEFAULT_MEAL_PERIODS_SNAPSHOT)
