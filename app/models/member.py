from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.core.timeutil import beijing_now_naive


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("store_id", "phone", name="uk_members_store_phone"),
        UniqueConstraint("store_id", "wx_mini_openid", name="uk_members_store_wx_mini_openid"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", onupdate="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stores.id", onupdate="CASCADE"), nullable=False, index=True
    )
    phone: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(100))
    wechat_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wx_mini_openid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    balance: Mapped[int] = mapped_column(Integer, default=0)
    # 每配送日份数：确认送达一次按该倍数扣 balance（默认 1）
    daily_meal_units: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 周卡/月卡累计「总次数」分母；入账时与 balance 同步按卡型 +6 / +24（剩余/总 展示）
    meal_quota_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 与 MySQL ENUM 取值一致，业务校验在 Pydantic / Service
    plan_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_leaved_tomorrow: Mapped[bool] = mapped_column(Boolean, default=False)
    # 与 is_leaved_tomorrow 同时生效：不配送的「目标业务日」（上海），便于配送命中与请假日全天展示「请假中」
    tomorrow_leave_target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    leave_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_low_balance_notify_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 续费提醒订阅消息：用户在完善资料页授权后 +1，扣次触达低余额阈值并成功下发后 -1
    wx_renew_remind_quota: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_deferred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    store_pickup: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 固定周六不参与订阅履约（当周六十 global 仍为履约日时）；默认关闭
    skip_subscription_saturday: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=beijing_now_naive, onupdate=beijing_now_naive)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    membership_refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)


@event.listens_for(Member, "before_update")
def _member_set_updated_at(_mapper, _connection, target: Member) -> None:
    changed = {attr.key for attr in inspect(target).attrs if attr.history.has_changes()}
    # 微信登录 / 同步 openid 不刷新档案最近操作时间
    if changed <= {"wx_mini_openid"}:
        return
    target.updated_at = beijing_now_naive()
