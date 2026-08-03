"""门店打印场景绑定：配送大表 / 商城零售等。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class StorePrintSceneSetting(Base):
    __tablename__ = "store_print_scene_settings"

    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
    )
    scene: Mapped[str] = mapped_column(String(32), primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("store_print_profiles.id", onupdate="CASCADE", ondelete="SET NULL"), nullable=True
    )
    template_key: Mapped[str] = mapped_column(String(64), default="delivery_meal_full", nullable=False)
    copies_mode: Mapped[str] = mapped_column(String(16), default="per_unit", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
