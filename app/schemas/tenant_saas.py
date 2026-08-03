"""SaaS 多租户公开与管理端 Schema。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TenantSaasConfigPatchIn(BaseModel):
    """平台管理：租户 SaaS 展示配置（写入 extra_json.saas）。"""

    tenant_code: str | None = Field(None, max_length=64, description="外部 tenantId，如 t_brand_a")
    app_name: str | None = Field(None, max_length=128)
    default_store_id: int | None = Field(None, ge=1)
    home_template: str | None = Field(None, max_length=32)
    home_layout_preset: str | None = Field(None, max_length=64)
    theme: dict[str, str] | None = None
    features: dict[str, bool] | None = None
    share: dict[str, str] | None = None
    legal: dict[str, str] | None = None
    home_layout: dict[str, Any] | None = Field(None, description="自定义首页 blocks；空对象表示清除")
    subscribe_delivery_tmpl_id: str | None = Field(None, max_length=128)


class WxComponentTicketIn(BaseModel):
    """平台管理：手动写入 component_verify_ticket。"""

    verify_ticket: str = Field(..., min_length=8, max_length=512)


class WxAuthorizerPatchIn(BaseModel):
    """平台管理：authorizer token 运维写入。"""

    authorizer_refresh_token: str | None = Field(None, max_length=512)
    authorizer_access_token: str | None = Field(None, max_length=512)
    authorization_code: str | None = Field(None, max_length=512, description="授权码，用于 exchange-code 接口")
    clear: bool = Field(False, description="true 时清除已落库的 authorizer token")


class WxCodeCommitIn(BaseModel):
    """平台管理：将模板库代码 commit 到已授权小程序（生成体验版）。"""

    template_id: int = Field(1, ge=0, description="普通模板库 template_id，当前默认 1")
    user_version: str = Field(..., min_length=1, max_length=64, description="代码版本号")
    user_desc: str = Field(..., min_length=1, max_length=256, description="代码描述")


class WxCodeAuditItemIn(BaseModel):
    """提审类目项（须为小程序后台已配置类目）。"""

    address: str = Field("pages/home/index", min_length=1, max_length=128, description="小程序页面路径")
    tag: str = Field(..., min_length=1, max_length=128)
    first_class: str = Field(..., min_length=1, max_length=64)
    second_class: str = Field(..., min_length=1, max_length=64)
    first_id: int = Field(..., ge=1)
    second_id: int = Field(..., ge=1)
    title: str = Field("首页", min_length=1, max_length=32)


class WxCodeSubmitAuditIn(BaseModel):
    """平台管理：将体验版代码提交微信审核。"""

    item_list: list[WxCodeAuditItemIn] = Field(..., min_length=1, max_length=5)
    version_desc: str | None = Field(None, max_length=512, description="版本说明")
    feedback_info: str | None = Field(None, max_length=200, description="反馈说明（被拒后重提时可填）")
    skip_privacy_sync: bool = Field(
        False,
        description="true 时跳过提审前自动同步隐私指引（仅运维兜底，正常勿开）",
    )


class WxCodePrivacySettingItemIn(BaseModel):
    """用户隐私保护指引 · 单项收集说明。"""

    privacy_key: str = Field(..., min_length=1, max_length=64)
    privacy_text: str = Field(..., min_length=1, max_length=256)


class WxCodeSyncPrivacyIn(BaseModel):
    """平台管理：同步小程序用户隐私保护指引（开发版 privacy_ver=2）。"""

    contact_phone: str | None = Field(None, max_length=32)
    contact_email: str | None = Field(None, max_length=128)
    contact_qq: str | None = Field(None, max_length=32)
    contact_weixin: str | None = Field(None, max_length=64)
    notice_method: str | None = Field(None, max_length=128, description="隐私变更通知方式，如弹窗提示")
    setting_list: list[WxCodePrivacySettingItemIn] | None = Field(
        None,
        description="不传则使用 OK饭 模板默认四项：手机号/位置/选点/头像",
    )
    privacy_ver: int = Field(2, ge=1, le=2, description="2=开发版（提审前同步）；1=现网版")
