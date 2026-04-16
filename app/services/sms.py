import random
import string
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.sms_dispatch import SmsDispatchError, dispatch_login_code
from app.models.sms_verification import SmsVerification


def send_login_code(db: Session, phone: str) -> None:
    """
    生成验证码、写入数据库后调用真实短信通道。
    若通道失败，删除本条验证码记录并抛出 SmsDispatchError。
    """
    settings = get_settings()
    code = "".join(random.choices(string.digits, k=6))
    expire_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        minutes=settings.SMS_CODE_TTL_MINUTES
    )

    row = db.get(SmsVerification, phone)
    if row:
        row.code = code
        row.expire_at = expire_at
    else:
        row = SmsVerification(phone=phone, code=code, expire_at=expire_at)
        db.add(row)
    db.commit()

    try:
        dispatch_login_code(phone, code, settings)
    except SmsDispatchError:
        stale = db.get(SmsVerification, phone)
        if stale:
            db.delete(stale)
            db.commit()
        raise


def verify_login_code(db: Session, phone: str, code: str) -> bool:
    row = db.get(SmsVerification, phone)
    if not row:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if row.expire_at < now:
        db.delete(row)
        db.commit()
        return False
    if row.code != code:
        return False
    db.delete(row)
    db.commit()
    return True
