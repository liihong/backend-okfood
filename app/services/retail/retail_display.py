"""商城零售：展示文案、金额格式化等通用工具。"""

from __future__ import annotations

from decimal import Decimal


def decimal_to_str_money(v: Decimal | None) -> str | None:
    """金额转字符串，保留两位小数。"""
    if v is None:
        return None
    return format(Decimal(v), "f")


def retail_sku_display_title(*, spu_title: str, spec_label: str | None) -> str:
    """组合 SKU 展示名：商品名 · 规格。"""
    base = (spu_title or "").strip() or "商品"
    spec = (spec_label or "").strip()
    if spec:
        return f"{base} · {spec}"
    return base


def retail_gallery_cover(gallery_urls: list | None) -> str | None:
    """取轮播图首项作为封面。"""
    if not gallery_urls or not isinstance(gallery_urls, list):
        return None
    for url in gallery_urls:
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def retail_price_range_yuan(prices: list[Decimal]) -> tuple[str | None, str | None]:
    """计算 SKU 列表的价格区间。"""
    if not prices:
        return None, None
    nums = [Decimal(p).quantize(Decimal("0.01")) for p in prices]
    lo, hi = min(nums), max(nums)
    return decimal_to_str_money(lo), decimal_to_str_money(hi)
