from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
    change: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(20))
    operator: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
