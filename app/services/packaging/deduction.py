"""把一餐的份数拆成每个耗材要扣的数量。

不访问数据库。午餐和晚餐必须各调一次，不能把两餐份数加总后共用一套盒子。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.packaging.constants import PORTION_SOURCE_DELIVERED


@dataclass(frozen=True)
class RecipeQty:
    """sku_id、每份个数、是否已期初且仍启用。"""

    sku_id: int
    qty_per_portion: int
    ready: bool
    name: str


@dataclass(frozen=True)
class DeductionPlan:
    quantities: dict[int, int]
    warnings: list[str]


def plan_meal_deduction(
    *,
    meal_label: str,
    portions: int,
    portion_source: str,
    bag_sku_id: int | None,
    bag_ready: bool,
    bag_name: str,
    box_lines: list[RecipeQty],
    standard_lines: list[RecipeQty],
) -> DeductionPlan:
    """一餐扣减：打包袋每份 1 只，再加上该餐自己的用盒和每份标配。"""
    warnings: list[str] = []
    quantities: dict[int, int] = {}
    count = max(0, int(portions))
    if portion_source == PORTION_SOURCE_DELIVERED:
        warnings.append(
            f"{meal_label}未填后厨出餐，已按实发 {count} 份扣库，已包装未售出的今晚没扣"
        )
    if count == 0:
        return DeductionPlan(quantities={}, warnings=warnings)

    if bag_sku_id is None:
        warnings.append(f"{meal_label}未指定打包袋，打包袋未扣")
    elif not bag_ready:
        warnings.append(f"{meal_label}{bag_name or '打包袋'}尚未期初或已停用，打包袋未扣")
    else:
        quantities[int(bag_sku_id)] = count

    usable_boxes = [line for line in box_lines if line.sku_id != bag_sku_id and line.qty_per_portion > 0]
    if not usable_boxes:
        warnings.append(f"{meal_label}未设置用盒，餐盒未扣")
    else:
        _add_lines(quantities, warnings, meal_label, count, usable_boxes)

    standards = [line for line in standard_lines if line.sku_id != bag_sku_id and line.qty_per_portion > 0]
    _add_lines(quantities, warnings, meal_label, count, standards)
    return DeductionPlan(quantities=quantities, warnings=warnings)


def _add_lines(
    quantities: dict[int, int],
    warnings: list[str],
    meal_label: str,
    portions: int,
    lines: list[RecipeQty],
) -> None:
    for line in lines:
        if not line.ready:
            warnings.append(f"{meal_label}{line.name}尚未期初或已停用，未扣")
            continue
        quantities[line.sku_id] = quantities.get(line.sku_id, 0) + portions * int(line.qty_per_portion)
