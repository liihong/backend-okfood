"""会员端：套餐配送确认送达时的扣次记录（按配送业务日）。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.enums import DeliveryStatus
from app.schemas.user import DeliveryDeductionOut


def list_member_delivery_deductions(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DeliveryDeductionOut], int]:
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    mid = int(member_id)
    filt = (DeliveryLog.member_id == mid) & (DeliveryLog.status == DeliveryStatus.DELIVERED.value)
    total = int(db.scalar(select(func.count()).select_from(DeliveryLog).where(filt)) or 0)
    base = select(DeliveryLog).where(filt).order_by(DeliveryLog.delivery_date.desc(), DeliveryLog.id.desc())
    offset = (page - 1) * page_size
    rows = db.scalars(base.offset(offset).limit(page_size)).all()
    return [DeliveryDeductionOut(delivery_date=r.delivery_date) for r in rows], total
