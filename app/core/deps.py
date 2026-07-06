import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, decode_token
from app.core.store_scope import (
    PublicStoreContext,
    assert_member_belongs_to_header_store,
    parse_store_id_from_header_or_default,
    resolve_public_store,
)
from app.db.session import get_db
from app.models.admin_user import AdminUser
from app.models.member import Member
from app.models.store import Store
from app.models.tenant import Tenant
from app.core.tenant_subscription import assert_admin_tenant_subscription_active

logger = logging.getLogger(__name__)

ROLE_MEMBER = "member"
ROLE_COURIER = "courier"
ROLE_ADMIN = "admin"
ROLE_ADMIN_DELIVERY = "admin_delivery"
ROLE_ADMIN_SUPPORT = "admin_support"
ROLE_ADMIN_SYSTEM = "admin_system"

ADMIN_ACCOUNT_FULL = "full"
ADMIN_ACCOUNT_DELIVERY = "delivery"
ADMIN_ACCOUNT_SUPPORT = "support"
ADMIN_ACCOUNT_SYSTEM = "system"

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


def _ensure_admin_tenant_subscription(db: Session, *, admin_username: str, jwt_role: str) -> None:
    """非平台管理员访问管理端 API 时校验租户订阅未过期。"""
    if jwt_role == ROLE_ADMIN_SYSTEM:
        return
    u = db.scalar(select(AdminUser).where(AdminUser.username == admin_username))
    if not u:
        raise HTTPException(status_code=401, detail="账号不存在")
    assert_admin_tenant_subscription_active(db, u, jwt_role=jwt_role)


def admin_subject(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    sub, role = _subject_from_bearer(creds)
    if role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="需要管理员令牌")
    _ensure_admin_tenant_subscription(db, admin_username=sub, jwt_role=role)
    return sub


def admin_staff_subject(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    """完整管理员或客服账号（不含财务中心、门店配置等「店主」专属接口）。"""
    sub, role = _subject_from_bearer(creds)
    if role not in (ROLE_ADMIN, ROLE_ADMIN_SUPPORT):
        raise HTTPException(status_code=403, detail="需要管理端令牌")
    _ensure_admin_tenant_subscription(db, admin_username=sub, jwt_role=role)
    return sub


def admin_full_subject(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    """仅完整管理员（店主）：财务汇总、门店配置等。"""
    return admin_subject(creds, db)


def admin_system_subject(creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> str:
    """平台管理员：租户与跨租户账号维护（JWT role=admin_system）。"""
    sub, role = _subject_from_bearer(creds)
    if role != ROLE_ADMIN_SYSTEM:
        raise HTTPException(status_code=403, detail="需要平台管理员令牌")
    return sub


def admin_or_delivery_staff_subject(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> str:
    """完整管理员、客服或「仅配送管理」后台账号 JWT。"""
    sub, role = _subject_from_bearer(creds)
    if role not in (ROLE_ADMIN, ROLE_ADMIN_DELIVERY, ROLE_ADMIN_SUPPORT):
        raise HTTPException(status_code=403, detail="需要管理员或配送管理账号令牌")
    _ensure_admin_tenant_subscription(db, admin_username=sub, jwt_role=role)
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


def issue_admin_token(username: str, *, jwt_role: str | None = None) -> str:
    role = jwt_role if jwt_role is not None else ROLE_ADMIN
    return create_access_token(
        subject=username,
        role=role,
        expires_delta=timedelta(minutes=settings.JWT_EXPIRE_MINUTES_ADMIN),
    )


SessionDep = Annotated[Session, Depends(get_db)]


@dataclass(frozen=True)
class MemberAuthScope:
    """会员 JWT + 门店一致性（header 可选，不传则沿用档案门店）。"""

    member_id: int
    member: Member
    store_id: int


def member_auth_scope(
    request: Request,
    member_id: int = Depends(member_subject),
    db: Session = Depends(get_db),
) -> MemberAuthScope:
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    sid = assert_member_belongs_to_header_store(request, m)
    return MemberAuthScope(member_id=int(member_id), member=m, store_id=sid)


def member_id_scoped(auth: MemberAuthScope = Depends(member_auth_scope)) -> int:
    """与 member_auth_scope 相同校验（含 X-Store-Id 与档案一致）；供仅需 member_id 的路由。"""

    return auth.member_id


MemberIdScoped = Annotated[int, Depends(member_id_scoped)]


def public_store_dep(request: Request, db: Session = Depends(get_db)) -> PublicStoreContext:
    sid = parse_store_id_from_header_or_default(request)
    return resolve_public_store(db, sid)


def require_admin_tenant_store(db: Session, *, admin_username: str, store_id: int) -> tuple[int, int]:
    """返回 (tenant_id, store_id)；门店须属于该管理员租户。

    兼容多租户管理端仍默认传 ``store_id=DEFAULT_STORE_ID``（多为 1）的情况：若该门店不属于本租户
    或不可用，则回退为「本租户下 id 最小的启用门店」。
    """
    u = db.scalar(select(AdminUser).where(AdminUser.username == admin_username))
    if not u:
        raise HTTPException(status_code=401, detail="账号不存在")
    tid = int(u.tenant_id)
    sid_req = int(store_id)
    st = db.get(Store, sid_req)
    if st is not None and st.is_active and int(st.tenant_id) == tid:
        return tid, int(st.id)

    if sid_req == int(settings.DEFAULT_STORE_ID):
        alt_id = db.scalar(
            select(Store.id)
            .where(Store.tenant_id == tid, Store.is_active.is_(True))
            .order_by(Store.id.asc())
            .limit(1)
        )
        if alt_id is not None:
            return tid, int(alt_id)

    if st is None or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    raise HTTPException(status_code=403, detail="无权操作该门店")


def require_admin_tenant_id(db: Session, *, admin_username: str) -> int:
    """当前登录管理员所属租户 id。"""
    u = db.scalar(select(AdminUser).where(AdminUser.username == admin_username))
    if not u:
        raise HTTPException(status_code=401, detail="账号不存在")
    return int(u.tenant_id)
