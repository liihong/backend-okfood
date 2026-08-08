"""商城零售：富文本详情白名单过滤（防 XSS）。"""

from __future__ import annotations

import bleach

# 允许的基础 HTML 标签与属性
_ALLOWED_TAGS = frozenset(
    {
        "p",
        "br",
        "strong",
        "b",
        "em",
        "i",
        "u",
        "h1",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "img",
        "a",
        "div",
        "span",
        "blockquote",
    }
)

_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target"],
    "img": ["src", "alt", "width", "height"],
}

_ALLOWED_PROTOCOLS = ["http", "https"]


def sanitize_retail_detail_html(raw: str | None) -> str | None:
    """过滤商品详情 HTML，仅保留安全标签与属性。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    cleaned = bleach.clean(
        text,
        tags=list(_ALLOWED_TAGS),
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
    )
    return cleaned.strip() or None


def normalize_retail_gallery_urls(urls: list[str] | None) -> list[str] | None:
    """轮播图 URL 白名单：仅 https（或站内相对路径）。"""
    if not urls:
        return None
    out: list[str] = []
    for u in urls:
        if not isinstance(u, str):
            continue
        s = u.strip()
        if not s:
            continue
        if s.startswith("/"):
            out.append(s)
            continue
        if s.startswith("https://"):
            out.append(s)
    return out or None
