from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SfSameCityCallback(Base):
    """顺丰开放平台推送到我方 URL 的原始记录（验签结果与 JSON 正文）。"""

    __tablename__ = "sf_same_city_callbacks"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    route_kind: Mapped[str] = mapped_column(String(64), index=True)
    sign_ok: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    shop_order_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sf_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    raw_body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
