"""当前门店可导入的常用打包耗材。不在启动时写入，避免灌进其他租户。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedSku:
    name: str
    usage_note: str
    supplier_name: str
    unit: str
    is_meal_bag: bool = False


# 手写清单。Pdd 记为拼多多，tb 记为淘宝。只有「打包袋」是每餐一只。
DEFAULT_PACKAGING_SKUS: tuple[SeedSku, ...] = (
    SeedSku("900圆", "", "吴宝", "个"),
    SeedSku("650方", "", "拼多多", "个"),
    SeedSku("400圆", "", "拼多多", "个"),
    SeedSku("550均分", "", "顶塑", "个"),
    SeedSku("100斗笠", "", "顶塑", "个"),
    SeedSku("小汤", "", "拼多多", "个"),
    SeedSku("大汤", "", "淘宝", "个"),
    SeedSku("椭圆圆盒", "", "志慧", "个"),
    SeedSku("六角碗", "", "顶塑", "个"),
    SeedSku("四格匀盒", "", "吴宝", "个"),
    SeedSku("450圆", "沙拉", "志慧", "个"),
    SeedSku("200圆", "料汁", "志慧", "个"),
    SeedSku("P1连盖盒", "小料", "志慧", "个"),
    SeedSku("筷子", "", "顶塑", "双"),
    SeedSku("小勺", "", "志慧", "个"),
    SeedSku("一次性手套", "", "拼多多", "只"),
    SeedSku("打包袋", "", "李江", "个", True),
    SeedSku("保温袋", "", "拼多多", "个"),
    SeedSku("赠饮瓶", "", "拼多多", "个"),
    SeedSku("1000方", "", "吴宝", "个"),
)
