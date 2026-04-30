from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminLoginTokenOut(TokenResponse):
    """登录响应：`admin_kind` 与 JWT `role`（admin / admin_delivery）一致。"""

    admin_kind: Literal["full", "delivery"] = "full"


class Pagination(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
