"""阿里云 OSS 上传；未配置完整时由调用方回退本地存储。"""

from __future__ import annotations

import uuid
from datetime import datetime
import oss2
from fastapi import HTTPException

from app.core.config import settings
from app.services.shared.upload_service import save_image_bytes, validate_image_bytes


def oss_configured() -> bool:
    provider = settings.OSS_PROVIDER.strip().lower()
    if provider in ("", "local", "disk"):
        return False
    if provider != "aliyun":
        # 其他云厂商未接 SDK前走本地，避免误配导致启动或上传异常
        return False
    return bool(
        settings.OSS_ENDPOINT.strip()
        and settings.OSS_BUCKET.strip()
        and settings.OSS_ACCESS_KEY_ID.strip()
        and settings.OSS_ACCESS_KEY_SECRET.strip()
    )


def _public_url_for_key(key: str) -> str:
    key = key.lstrip("/")
    base = settings.oss_public_url_prefix
    if base:
        return f"{base}/{key}"
    ep = settings.OSS_ENDPOINT.strip().replace("https://", "").replace("http://", "").rstrip("/")
    b = settings.OSS_BUCKET.strip()
    return f"https://{b}.{ep}/{key}"


def _build_object_key(*segments: str) -> str:
    prefix = settings.OSS_KEY_PREFIX.strip().strip("/")
    parts = [s.strip("/") for s in segments if s]
    if prefix:
        return f"{prefix}/" + "/".join(parts)
    return "/".join(parts)


def _put_object_to_oss(data: bytes, content_type: str, object_key: str) -> str:
    endpoint = settings.OSS_ENDPOINT.strip()
    if not endpoint.startswith("http://") and not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"

    try:
        auth = oss2.Auth(
            settings.OSS_ACCESS_KEY_ID.strip(),
            settings.OSS_ACCESS_KEY_SECRET.strip(),
        )
        bucket = oss2.Bucket(auth, endpoint, settings.OSS_BUCKET.strip())
        headers = {"Content-Type": content_type}
        bucket.put_object(object_key, data, headers=headers)
    except oss2.exceptions.OssError as e:
        msg = getattr(getattr(e, "result", None), "message", None) or str(e)
        raise HTTPException(status_code=502, detail=f"对象存储上传失败：{msg}") from e
    except Exception as e:
        raise HTTPException(status_code=502, detail="对象存储上传失败，请稍后重试") from e

    return _public_url_for_key(object_key)


def upload_image_bytes(data: bytes, content_type: str | None, filename: str | None) -> str:
    """管理端通用图片（菜品、Banner 等）：优先 OSS，否则写入本地 UPLOAD_DIR。"""
    ct, ext = validate_image_bytes(data, content_type, filename)

    if not oss_configured():
        return save_image_bytes(data, content_type, filename)

    now = datetime.now()
    object_key = _build_object_key("images", f"{now:%Y}", f"{now:%m}", f"{uuid.uuid4().hex}{ext}")
    return _put_object_to_oss(data, ct, object_key)


def upload_member_avatar_bytes(data: bytes, content_type: str | None, filename: str | None) -> str:
    """会员头像：优先 OSS，否则与菜品图相同写入本地 UPLOAD_DIR。"""
    ct, ext = validate_image_bytes(data, content_type, filename)

    if not oss_configured():
        return save_image_bytes(data, content_type, filename)

    now = datetime.now()
    object_key = _build_object_key("avatars", f"{now:%Y}", f"{now:%m}", f"{uuid.uuid4().hex}{ext}")
    return _put_object_to_oss(data, ct, object_key)
