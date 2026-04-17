from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.deps import SessionDep, courier_subject, issue_courier_token
from app.core.limiter import limiter
from app.core.timeutil import today_shanghai
from app.schemas.common import TokenResponse
from app.models.courier import Courier
from app.schemas.courier import ConfirmDeliveryIn, ConfirmSingleOrderIn, CourierLoginIn, CourierPhoneLoginIn, CourierSelfOut
from app.services.courier_admin_service import regions_for_courier
from app.services.courier_service import (
    confirm_delivery,
    courier_login,
    courier_login_by_phone,
    group_task_rows,
    list_tasks_for_courier,
)
from app.services.single_meal_order_service import confirm_single_order_delivery
from app.utils.response import dump_model, success

router = APIRouter(prefix="/courier", tags=["配送端"])


@router.post("/login")
@limiter.limit("30/minute")
def login(request: Request, body: CourierLoginIn, db: SessionDep):
    courier_login(db, body.courier_id, body.pin)
    token = TokenResponse(access_token=issue_courier_token(body.courier_id))
    return success(data=dump_model(token), msg="登录成功")


@router.post("/login-phone")
@limiter.limit("30/minute")
def login_phone(request: Request, body: CourierPhoneLoginIn, db: SessionDep):
    c = courier_login_by_phone(db, body.phone)
    token = TokenResponse(access_token=issue_courier_token(c.courier_id))
    return success(data=dump_model(token), msg="登录成功")


@router.get("/me")
def courier_me(db: SessionDep, courier_id: str = Depends(courier_subject)):
    c = db.get(Courier, courier_id)
    if not c or not c.is_active:
        raise HTTPException(status_code=401, detail="账号无效或已停用")
    assigned = regions_for_courier(db, courier_id)
    allowed_names = sorted({(r.name or "").strip() for r in assigned if r.name and (r.name or "").strip()})
    phone = (c.phone or "").strip()
    masked = ""
    if len(phone) >= 7:
        masked = f"{phone[:3]}****{phone[-4:]}"
    payload = CourierSelfOut(
        courier_id=c.courier_id,
        name=(c.name or "").strip(),
        phone_masked=masked,
        fee_pending=f"{c.fee_pending:.2f}" if c.fee_pending is not None else "0.00",
        fee_settled=f"{c.fee_settled:.2f}" if c.fee_settled is not None else "0.00",
        assigned_areas=allowed_names,
    )
    return success(data=payload.model_dump(mode="json"), msg="获取成功")


@router.get("/tasks")
def tasks(
    db: SessionDep,
    courier_id: str = Depends(courier_subject),
    area: str | None = None,
    delivery_date: date | None = Query(None, alias="date", description="配送业务日，默认上海当日"),
):
    assigned = regions_for_courier(db, courier_id)
    allowed_names = {(r.name or "").strip() for r in assigned if r.name and (r.name or "").strip()}
    d = delivery_date or today_shanghai()

    rows, d = list_tasks_for_courier(db, courier_id, delivery_date=delivery_date)
    if area is not None and (area or "").strip() != "":
        an = area.strip()
        if an not in allowed_names:
            raise HTTPException(status_code=403, detail="无权查看该片区")
        rows = [m for m in rows if (m.area or "").strip() == an]
    groups = group_task_rows(rows)

    payload = {
        "delivery_date": d.isoformat(),
        "assigned_areas": sorted(allowed_names),
        "groups": groups,
    }
    return success(data=payload, msg="获取成功")


@router.post("/confirm")
def confirm(body: ConfirmDeliveryIn, db: SessionDep, courier_id: str = Depends(courier_subject)):
    """确认送达：扣减 1 次并记账；已送达重复提交幂等。"""
    confirm_delivery(db, courier_id, body.member_id, body.delivery_date)
    return success(msg="送达已确认")


@router.post("/single-order/confirm")
def confirm_single_order(body: ConfirmSingleOrderIn, db: SessionDep, courier_id: str = Depends(courier_subject)):
    """单次点餐确认送达：不扣会员次卡，仅更新订单履约状态。"""
    confirm_single_order_delivery(db, courier_id, body.order_id)
    return success(msg="单次订单已确认送达")
