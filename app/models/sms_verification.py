from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SmsVerification(Base):
    """登录验证码持久化：多进程/多实例下可一致校验，避免内存字典模拟。"""

    __tablename__ = "sms_verification"

    phone: Mapped[str] = mapped_column(String(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(10))
    expire_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
