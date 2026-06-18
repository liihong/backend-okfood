from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class BalanceLog(Base):
    __tablename__ = "balance_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", onupdate="CASCADE"),
        index=True,
    )
    #: lunch=午餐次数池（members.balance）；dinner=晚餐次数池（member_meal_period_state）
    meal_period: Mapped[str] = mapped_column(String(16), default="lunch", nullable=False)
    change: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(20))
    operator: Mapped[str] = mapped_column(String(50))
    # 人工/业务说明：如开卡工单同步入账时的工单号与备注摘要
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
