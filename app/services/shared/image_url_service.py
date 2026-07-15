"""会员端图片 URL：列表缩略 / Banner / 详情 / Logo；OSS 动态处理 + 本地上传变体后缀。"""

from __future__ import annotations

import re
from urllib.parse import quote, urlparse, urlunparse

from app.core.config import settings

# 与 image_process_service 变体文件名约定一致
THUMB_WIDTH = 480
MEDIUM_WIDTH = 1080
BANNER_WIDTH = 750
LOGO_WIDTH = 128

_VARIANT_SUFFIX_RE = re.compile(r"_w\d+\.webp$", re.I)
_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp)$", re.I)


def _strip_query(url: str) -> str:
    return (url or "").strip().split("?", 1)[0]


def _is_http_url(url: str) -> bool:
    u = (url or "").strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def _is_oss_public_asset_url(url: str) -> bool:
    """是否为本项目 OSS 自定义域名或 bucket 域名下的资源。"""
    if not _is_http_url(url):
        return False
    u = _strip_query(url)
    prefix = settings.oss_public_url_prefix
    if prefix and u.startswith(prefix.rstrip("/") + "/"):
        return True
    ep = settings.OSS_ENDPOINT.strip().replace("https://", "").replace("http://", "").rstrip("/")
    bucket = settings.OSS_BUCKET.strip()
    if ep and bucket and f"{bucket}.{ep}" in u:
        return True
    return False


def _append_oss_process(url: str, *, width: int, quality: int = 82) -> str:
    """阿里云 OSS 图片处理（旧图无需预生成变体即可生效）。"""
    base = (url or "").strip()
    if not base or "x-oss-process=" in base:
        return base
    process = f"image/resize,w_{int(width)}/quality,q_{int(quality)}/format,webp"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}x-oss-process={quote(process, safe='')}"


def variant_sibling_url(original_url: str | None, *, width: int) -> str | None:
    """由原图 URL 推导本地上传时写入的 ``_w{width}.webp`` 变体地址。"""
    if not original_url:
        return None
    raw = original_url.strip()
    if not raw or _VARIANT_SUFFIX_RE.search(_strip_query(raw)):
        return raw or None
    path_only = raw
    if _is_http_url(raw):
        parsed = urlparse(raw)
        path_only = parsed.path or raw
    if not _EXT_RE.search(path_only):
        sibling_path = f"{path_only}_w{width}.webp"
    else:
        sibling_path = _EXT_RE.sub(f"_w{width}.webp", path_only)
    if _is_http_url(raw):
        parsed = urlparse(raw)
        return urlunparse(parsed._replace(path=sibling_path, query="", fragment=""))
    return sibling_path


def resolve_member_image_url(
    original_url: str | None,
    *,
    width: int,
    quality: int = 82,
    prefer_variant_file: bool = True,
) -> str | None:
    """会员端展示用 URL：OSS 走 x-oss-process；本地优先变体文件 URL。"""
    if not original_url:
        return None
    raw = original_url.strip()
    if not raw:
        return None
    if not _is_http_url(raw):
        # 相对路径 /static/...：变体后缀
        if prefer_variant_file:
            sibling = variant_sibling_url(raw, width=width)
            return sibling or raw
        return raw

    from app.services.shared.oss_upload_service import oss_configured

    if oss_configured() and _is_oss_public_asset_url(raw):
        return _append_oss_process(raw, width=width, quality=quality)

    if prefer_variant_file:
        sibling = variant_sibling_url(raw, width=width)
        if sibling:
            return sibling
    return raw


def image_list_thumb_url(original_url: str | None) -> str | None:
    """菜单列表 / 首页推荐（约 160–200rpx）。"""
    return resolve_member_image_url(original_url, width=THUMB_WIDTH, quality=82)


def image_detail_medium_url(original_url: str | None) -> str | None:
    """详情页中等清晰度。"""
    return resolve_member_image_url(original_url, width=MEDIUM_WIDTH, quality=88)


def image_banner_url(original_url: str | None) -> str | None:
    """首页 Banner 轮播。"""
    return resolve_member_image_url(original_url, width=BANNER_WIDTH, quality=85)


def image_logo_url(original_url: str | None) -> str | None:
    """门店小 Logo。"""
    return resolve_member_image_url(original_url, width=LOGO_WIDTH, quality=85)


def image_poster_url(original_url: str | None) -> str | None:
    """弹窗海报（宽度限制，体积适中）。"""
    return resolve_member_image_url(original_url, width=BANNER_WIDTH, quality=85)


def member_dish_image_fields(image_url: str | None) -> dict[str, str | None]:
    """周菜单/今日餐谱：原图 + 列表缩略（字段 additive，不影响 pic）。"""
    if not image_url or not str(image_url).strip():
        return {"pic": None, "pic_thumb": None}
    orig = str(image_url).strip()
    return {"pic": orig, "pic_thumb": image_list_thumb_url(orig)}
