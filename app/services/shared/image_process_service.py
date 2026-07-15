"""上传图片：压缩原图并生成 WebP 缩略/中图变体（与 image_url_service 后缀约定一致）。"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

# 与 image_url_service 变体文件名约定一致
THUMB_WIDTH = 480
MEDIUM_WIDTH = 1080

# 原图最长边上限（Banner/海报/菜品）
MAX_ORIGINAL_EDGE = 1920
ORIGINAL_JPEG_QUALITY = 88
THUMB_WEBP_QUALITY = 82
MEDIUM_WEBP_QUALITY = 85

_CACHE_CONTROL = "public, max-age=31536000, immutable"


@dataclass(frozen=True)
class ProcessedImageVariants:
    """上传产物：原图字节 + 两个 WebP 变体。"""

    original_bytes: bytes
    original_content_type: str
    original_ext: str
    thumb_bytes: bytes
    medium_bytes: bytes


def _open_normalized(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _resize_max_edge(img: Image.Image, max_edge: int) -> Image.Image:
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    edge = max(w, h)
    if edge <= max_edge:
        return img
    scale = max_edge / float(edge)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def _resize_to_width(img: Image.Image, width: int) -> Image.Image:
    w, h = img.size
    if w <= 0 or h <= 0:
        return img
    if w <= width:
        return img
    nh = max(1, int(round(h * (width / float(w)))))
    return img.resize((width, nh), Image.Resampling.LANCZOS)


def _encode_jpeg(img: Image.Image, *, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue()


def _encode_webp(img: Image.Image, *, quality: int) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    return buf.getvalue()


def process_image_upload_bytes(data: bytes, content_type: str | None, filename: str | None) -> ProcessedImageVariants:
    """将上传图规范为 JPEG 原图 + _w480/_w1080 WebP 变体。"""
    from app.services.shared.upload_service import validate_image_bytes

    ct, ext = validate_image_bytes(data, content_type, filename)
    img = _open_normalized(data)
    img = _resize_max_edge(img, MAX_ORIGINAL_EDGE)

    thumb_img = _resize_to_width(img, THUMB_WIDTH)
    medium_img = _resize_to_width(img, MEDIUM_WIDTH)

    original_bytes = _encode_jpeg(img, quality=ORIGINAL_JPEG_QUALITY)
    # 统一原图为 .jpg，便于变体后缀推导
    original_ext = ".jpg"
    original_ct = "image/jpeg"

    return ProcessedImageVariants(
        original_bytes=original_bytes,
        original_content_type=original_ct,
        original_ext=original_ext,
        thumb_bytes=_encode_webp(thumb_img, quality=THUMB_WEBP_QUALITY),
        medium_bytes=_encode_webp(medium_img, quality=MEDIUM_WEBP_QUALITY),
    )


def upload_cache_control_header() -> str:
    return _CACHE_CONTROL


def process_avatar_upload_bytes(data: bytes, content_type: str | None, filename: str | None) -> bytes:
    """头像：最长边 512px JPEG。"""
    from app.services.shared.upload_service import validate_image_bytes

    validate_image_bytes(data, content_type, filename)
    img = _open_normalized(data)
    img = _resize_max_edge(img, 512)
    return _encode_jpeg(img, quality=85)
