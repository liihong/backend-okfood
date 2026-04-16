"""本地图片上传：保存到磁盘并生成可对外访问的 URL 路径。"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings

_CT_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _ext_from_filename(name: str) -> str | None:
    lower = name.lower().strip()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if lower.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None


def ensure_upload_root() -> Path:
    root = settings.upload_dir_resolved
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_image_bytes(data: bytes, content_type: str | None, filename: str | None) -> str:
    """校验类型与大小，写入 UPLOAD_DIR，返回可用于 image_url 的 URL 字符串。"""
    max_b = settings.MAX_UPLOAD_BYTES
    if len(data) > max_b:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大允许 {max_b // (1024 * 1024)}MB",
        )
    if not data:
        raise HTTPException(status_code=400, detail="空文件")

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in _CT_TO_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的图片类型：{ct or '未知'}，请使用 JPEG/PNG/WebP/GIF",
        )

    ext_by_name = _ext_from_filename(filename or "")
    ext = _CT_TO_EXT[ct]
    if ext_by_name and ext_by_name != ext:
        raise HTTPException(status_code=400, detail="文件扩展名与图片格式不一致")

    root = ensure_upload_root()
    now = datetime.now()
    rel_dir = Path("static") / "uploads" / "images" / f"{now:%Y}" / f"{now:%m}"
    out_dir = root / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{uuid.uuid4().hex}{ext}"
    out_path = out_dir / safe_name
    out_path.write_bytes(data)

    rel_url_path = f"/static/uploads/images/{now:%Y}/{now:%m}/{safe_name}"
    return settings.public_url_for_upload_path(rel_url_path)
