import logging
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, decode_token
from app.db.session import get_db

logger = logging.getLogger(__name__)

ROLE_MEMBER = "member"
ROLE_COURIER = "courier"
ROLE_ADMIN = "admin"

bearer_scheme = HTTPBearer(auto_error=False)


def _subject_from_bearer(creds: HTTPAuthorizationCredentials | None) -> tuple[str, str]:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="未登录或令牌缺失")
    try:
        payload = decode_token(creds.credentials)
    except JWTError as e:
        logger.debug("JWT 校验失败: %s", e)
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    sub = payload.get("sub")
    role = payload.get("role")
    if not sub or not role:
        raise HTTPException(status_code=401, detail="令牌内容不完整")
    return str(sub), str(role)


def require_roles(*allowed: str):
    """依赖工厂：限制 JWT role。"""

    def _inner(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
        sub, role = _subject_from_bearer(creds)
        if role not in allowed:
            raise HTTPException(status_code=403, detail="无权访问该资源")
        return sub

    return _inner


def member_subject(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> int:
    sub, role = _subject_from_bearer(creds)
    if role != ROLE_MEMBER:
        raise HTTPException(status_code=403, detail="需要会员令牌")
    try:
        return int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="令牌内容无效")


def courier_subject(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    sub, role = _subject_from_bearer(creds)
    if role != ROLE_COURIER:
        raise HTTPException(status_code=403, detail="需要配送员令牌")
    return sub


def admin_subject(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    sub, role = _subject_from_bearer(creds)
    if role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员令牌")
    return sub


def issue_member_token(member_id: int) -> str:
    """会员 JWT（当前仅微信小程序登录签发）；`sub` 为 members.id。"""
    return create_access_token(
        subject=str(member_id),
        role=ROLE_MEMBER,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES_MEMBER),
    )


def issue_courier_token(courier_id: str) -> str:
    return create_access_token(
        subject=courier_id,
        role=ROLE_COURIER,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES_COURIER),
    )


def issue_admin_token(username: str) -> str:
    return create_access_token(
        subject=username,
        role=ROLE_ADMIN,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES_ADMIN),
    )


SessionDep = Annotated[Session, Depends(get_db)]
