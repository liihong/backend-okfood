"""会员端：抖音验券、我的优惠券。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import MemberIdScoped, SessionDep
from app.schemas.douyin import DouyinCertificateRedeemIn
from app.services.douyin import redeem_douyin_certificate
from app.services.marketing.member_coupon_service import list_member_coupons_for_user_wallet
from app.utils.response import dump_model, success

router = APIRouter(prefix="/user", tags=["会员端-抖音团购"])


@router.get("/member-coupons/wallet")
def list_member_coupons_wallet_me(
    db: SessionDep,
    member_id: MemberIdScoped,
    status: Annotated[str | None, Query(description="available/used/expired/revoked")] = None,
):
    """我的优惠券：持券列表（不按结算场景过滤）。"""
    from app.models.member import Member

    mem = db.get(Member, int(member_id))
    if not mem or mem.deleted_at is not None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="用户不存在")
    items = list_member_coupons_for_user_wallet(
        db,
        member_id=int(member_id),
        store_id=int(mem.store_id),
        status=status,
    )
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/douyin-certificates/redeem")
def redeem_douyin_certificate_me(
    db: SessionDep,
    member_id: MemberIdScoped,
    body: DouyinCertificateRedeemIn,
):
    """粘贴抖音券码兑换本地权益。"""
    out = redeem_douyin_certificate(db, member_id=int(member_id), body=body)
    return success(data=dump_model(out), msg=out.message)
