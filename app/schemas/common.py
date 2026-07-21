from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminTenantSubscriptionOut(BaseModel):
    """租户订阅摘要（店主/配送/客服登录后用于续费提醒）。"""

    expires_at: str | None = None
    days_until_expiry: int | None = None
    status: Literal["ok", "expiring_soon", "expired", "unset"] = "unset"
    remind_days: int = 30


class AdminStoreBrandingOut(BaseModel):
    """侧栏门店品牌：名称与 Logo（读门店配置，全员可见）。"""

    store_name: str | None = None
    store_logo_url: str | None = None


class AdminLoginTokenOut(TokenResponse):
    """登录响应：`admin_kind` 与 JWT `role`（admin / admin_delivery / admin_support / admin_system）一致。"""

    admin_kind: Literal["full", "delivery", "support", "system"] = "full"
    display_name: str | None = None
    tenant_subscription: AdminTenantSubscriptionOut | None = None


class Pagination(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
