"""某一餐的自动扣库是否已经跑过。有记录就不再回写，避免 22 点后改日总份导致重复扣。"""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class PackagingConsumeRun(Base):
    """门店 + 供餐日 + 餐段唯一。午餐和晚餐各记一行。"""

    __tablename__ = "packaging_consume_run"
    __table_args__ = (
        UniqueConstraint(
            "store_id", "biz_date", "meal_period", name="uk_packaging_consume_run"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    biz_date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_period: Mapped[str] = mapped_column(String(16), nullable=False)
    portions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    portion_source: Mapped[str] = mapped_column(String(16), nullable=False, comment="kitchen 或 delivered")
    note: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="这餐没扣干净的原因")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
