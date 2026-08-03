"""门店打印任务日志。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class StorePrintJob(Base):
    __tablename__ = "store_print_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    scene: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    template_key: Mapped[str] = mapped_column(String(64), nullable=False)
    brand: Mapped[str] = mapped_column(String(32), nullable=False)
    cloud_sn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    provider_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_msg: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_admin: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
