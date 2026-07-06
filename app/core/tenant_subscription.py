"""租户按年订阅：到期校验与续费提醒口径（业务日均为上海）。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.admin_user import AdminUser
from app.models.tenant import Tenant

# 到期前 N 天起提醒续费（含当天）
TENANT_EXPIRY_REMIND_DAYS = 30

TenantSubscriptionStatus = Literal["ok", "expiring_soon", "expired", "unset"]


def tenant_expires_at_date(tenant: Tenant | None) -> date | None:
    """租户订阅到期日（含当日仍有效）。"""
    if tenant is None:
        return None
    return getattr(tenant, "expires_at", None)


def is_tenant_subscription_expired(
    tenant: Tenant | None, *, today: date | None = None
) -> bool:
    """当前业务日是否已超过订阅到期日。"""
    exp = tenant_expires_at_date(tenant)
    if exp is None:
        return False
    anchor = today if today is not None else today_shanghai()
    return anchor > exp


def days_until_tenant_expiry(
    tenant: Tenant | None, *, today: date | None = None
) -> int | None:
    """距到期日剩余天数；已过期为负数；未设置到期日返回 None。"""
    exp = tenant_expires_at_date(tenant)
    if exp is None:
        return None
    anchor = today if today is not None else today_shanghai()
    return (exp - anchor).days


def tenant_subscription_status(
    tenant: Tenant | None, *, today: date | None = None
) -> TenantSubscriptionStatus:
    """订阅状态：未设置 / 正常 / 即将到期 / 已过期。"""
    exp = tenant_expires_at_date(tenant)
    if exp is None:
        return "unset"
    if is_tenant_subscription_expired(tenant, today=today):
        return "expired"
    days = days_until_tenant_expiry(tenant, today=today)
    if days is not None and days <= TENANT_EXPIRY_REMIND_DAYS:
        return "expiring_soon"
    return "ok"


def build_tenant_subscription_out(tenant: Tenant | None, *, today: date | None = None) -> dict:
    """管理端展示用订阅摘要。"""
    exp = tenant_expires_at_date(tenant)
    return {
        "expires_at": exp.isoformat() if exp is not None else None,
        "days_until_expiry": days_until_tenant_expiry(tenant, today=today),
        "status": tenant_subscription_status(tenant, today=today),
        "remind_days": TENANT_EXPIRY_REMIND_DAYS,
    }


def assert_admin_tenant_subscription_active(
    db: Session,
    admin_user: AdminUser,
    *,
    jwt_role: str | None = None,
    today: date | None = None,
) -> None:
    """非平台管理员须校验所属租户未过期且仍启用。"""
    role_db = (getattr(admin_user, "role", None) or "").strip().lower()
    if role_db == "system" or jwt_role == "admin_system":
        return
    tenant = db.get(Tenant, int(admin_user.tenant_id))
    if tenant is None or not bool(tenant.is_active):
        raise HTTPException(status_code=403, detail="租户已停用，请联系平台管理员")
    if is_tenant_subscription_expired(tenant, today=today):
        raise HTTPException(status_code=403, detail="租户服务已到期，请联系平台续费后重新登录")
