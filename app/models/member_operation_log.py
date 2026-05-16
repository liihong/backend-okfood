from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.timeutil import beijing_now_naive
from app.db.base import Base


class MemberOperationLog(Base):
    """会员自助操作审计日志：暂停/恢复配送、修改配送份数、修改配送地址等。"""

    __tablename__ = "member_operation_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )
    member_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("members.id", onupdate="CASCADE"),
        index=True,
    )
    # 渠道：miniprogram / admin（管理端代操作）；默认 miniprogram
    source: Mapped[str] = mapped_column(String(20), default="miniprogram")
    # 操作类型代码，见 app.constants.OPERATION_TYPE_*
    operation_type: Mapped[str] = mapped_column(String(50), index=True)
    # 摘要：用于管理端列表直观阅读，如 "暂停配送" / "修改每日送达份数 2→3"
    summary: Mapped[str] = mapped_column(String(200))
    # 变更前后数据（JSON 字符串），便于争议时还原具体字段
    before_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    after_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 客户端 IP；不做强校验，仅供追踪
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 操作者标识：会员操作填 "member:<id>"；管理端代操作填 "admin:<username>"
    operator: Mapped[str] = mapped_column(String(100), default="")
    # 北京时间（naive），与运营查看库表、对账一致；非 UTC。
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, index=True)
