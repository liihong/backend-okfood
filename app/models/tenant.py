"""租户：骑手与配送片区归属租户；其下可有多门店。"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # SaaS 外部标识（ext_json.ext.tenantId）；主租户 OK饭 可留空，不影响仅 X-Store-Id 的旧客户端
    code: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # 按年订阅到期日（含当日仍有效）；未设置则不做到期拦截（兼容历史租户）
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
