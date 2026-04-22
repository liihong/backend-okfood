from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile



from app.core.deps import SessionDep, issue_member_token, member_subject

from app.core.limiter import limiter

from app.integrations.wechat_mini import (

    WeChatMiniError,

    get_phone_pure_number,

    jscode2session,

    wx_mini_configured,

)

from app.schemas.common import TokenResponse

from app.schemas.member_address import MemberAddressCreateIn, MemberAddressUpdateIn

from app.schemas.admin import FileUploadOut

from sqlalchemy import select

from app.models.member import Member

from app.schemas.user import (
    ActivateIn,
    LeaveIn,
    MemberCardPricesOut,
    ProfilePatchIn,
    RegisterIn,
    UserMemberCardOrderCreateIn,
    UserMemberCardOrderOut,
    WxMiniJsCodeIn,
    WxMiniLoginIn,
)

from app.services.oss_upload_service import upload_member_avatar_bytes

from app.services.member_address_service import create_address, delete_address, list_addresses, update_address

from app.services.member_service import (

    activate_member,

    ensure_member_stub,

    get_member,

    leave_request,

    patch_member_profile,

    register_member,

)

from app.schemas.single_meal_order import SingleMealOrderCreateIn

from app.services.member_card_pay_service import (
    create_miniprogram_member_card_order,
    member_card_order_user_dict,
    prepare_wechat_jsapi_for_member_card_order,
)
from app.services.single_meal_order_service import create_single_meal_order, prepare_wechat_jsapi_for_order

from app.services.store_config_service import get_member_card_prices_yuan

from app.integrations.wechat_pay_v2 import resolve_request_client_ip

from app.utils.response import dump_model, success



router = APIRouter(prefix="/user", tags=["会员端"])





@router.post("/wx/mini/login")

@limiter.limit("30/minute")

def login_wx_mini(request: Request, body: WxMiniLoginIn, db: SessionDep):

    """

    微信小程序手机号授权登录：校验 `js_code`，用 `phone_code` 调微信接口取手机号，签发会员 JWT。

    需在环境变量中配置 WX_MINI_APPID、WX_MINI_SECRET。

    """

    if not wx_mini_configured():

        raise HTTPException(status_code=503, detail="微信小程序登录未配置或未开放")

    try:

        sess = jscode2session(body.js_code)

        phone = get_phone_pure_number(body.phone_code)

    except WeChatMiniError as e:

        raise HTTPException(status_code=e.status_code, detail=str(e))

    openid = str(sess.get("openid") or "").strip() or None

    member_id = ensure_member_stub(db, phone, wx_mini_openid=openid)

    token = TokenResponse(access_token=issue_member_token(member_id))

    return success(data=dump_model(token), msg="登录成功")


@router.post("/wx/mini/sync-openid")
@limiter.limit("30/minute")
def sync_wx_mini_openid(
    request: Request,
    body: WxMiniJsCodeIn,
    db: SessionDep,
    member_id: int = Depends(member_subject),
):
    """已持会员 JWT 时，用当前小程序会话的 `js_code` 写入 `members.wx_mini_openid`，便于 JSAPI 支付。"""
    _ = request
    if not wx_mini_configured():
        raise HTTPException(status_code=503, detail="微信小程序登录未配置或未开放")
    try:
        sess = jscode2session(body.js_code)
    except WeChatMiniError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    openid = str(sess.get("openid") or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="微信未返回用户标识，请稍后重试")
    bound_id = db.scalar(select(Member.id).where(Member.wx_mini_openid == openid))
    if bound_id is not None and int(bound_id) != int(member_id):
        raise HTTPException(
            status_code=400,
            detail="当前微信已绑定其他会员账号，请使用对应账号登录或联系客服",
        )
    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="用户不存在")
    member.wx_mini_openid = openid
    db.commit()
    return success(msg="已同步微信标识")


@router.post("/register")

@limiter.limit("20/minute")

def register(request: Request, body: RegisterIn, db: SessionDep):

    """新成员登记：写入前尝试高德地理编码（无 Key 或失败时坐标为空）。"""

    member = register_member(db, body)

    return success(data=dump_model(member), msg="注册成功")





@router.post("/activate")

def activate(body: ActivateIn, db: SessionDep, member_id: int = Depends(member_subject)):

    _ = body

    member = activate_member(db, member_id)

    return success(data=dump_model(member), msg="激活成功")





@router.post("/leave")

def leave(body: LeaveIn, db: SessionDep, member_id: int = Depends(member_subject)):

    """请假 / 取消：`clear_tomorrow` 仅取消「明天请假」；`cancel` 清空明天与区间。"""

    member = leave_request(db, member_id, body.type, body.start, body.end)

    return success(data=dump_model(member), msg="请假状态已更新")





@router.get("/me")

def read_member_me(db: SessionDep, member_id: int = Depends(member_subject)):

    """当前登录会员档案：JWT sub 为 members.id。"""

    member = get_member(db, member_id)

    return success(data=dump_model(member), msg="获取成功")


@router.get("/member-card-prices")
def read_member_card_prices(db: SessionDep, member_id: int = Depends(member_subject)):
    """周卡/月卡当前标价（与自助开卡下单金额一致，数据来自后台门店配置）。"""
    _ = member_id
    wk, mo = get_member_card_prices_yuan(db)

    def fmt(d: Decimal) -> str:
        return format(d.quantize(Decimal("0.01")), "f")

    payload = MemberCardPricesOut(week_price_yuan=fmt(wk), month_price_yuan=fmt(mo))
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/me/addresses")

def read_addresses_me(db: SessionDep, member_id: int = Depends(member_subject)):

    """会员配送地址列表（多地址）；默认地址优先。"""

    items = list_addresses(db, member_id)

    return success(data=[dump_model(x) for x in items], msg="获取成功")





@router.post("/me/addresses")

@limiter.limit("30/minute")

def add_address_me(request: Request, body: MemberAddressCreateIn, db: SessionDep, member_id: int = Depends(member_subject)):

    """新增配送地址：高德地理编码（失败则坐标为空，区域保留客户端或「未分配」）；首条地址自动设为默认。"""

    out = create_address(db, member_id, body)

    return success(data=dump_model(out), msg="保存成功")





@router.patch("/me/addresses/{address_id}")

def patch_address_me(

    address_id: int,

    body: MemberAddressUpdateIn,

    db: SessionDep,

    member_id: int = Depends(member_subject),

):

    out = update_address(db, member_id, address_id, body)

    return success(data=dump_model(out), msg="已更新")





@router.delete("/me/addresses/{address_id}")

def remove_address_me(address_id: int, db: SessionDep, member_id: int = Depends(member_subject)):

    delete_address(db, member_id, address_id)

    return success(msg="已删除")





@router.post("/single-orders")

@limiter.limit("30/minute")

def create_single_order_me(

    request: Request,

    body: SingleMealOrderCreateIn,

    db: SessionDep,

    member_id: int = Depends(member_subject),

):

    """单次点餐：创建未支付订单；支付与派单在微信支付回调中完成。随后调 `POST .../pay/wechat-jsapi` 调起支付。"""

    _ = request

    out = create_single_meal_order(db, member_id, body)

    return success(data=dump_model(out), msg="订单已创建，请继续支付")


@router.post("/single-orders/{order_id}/pay/wechat-jsapi")

@limiter.limit("30/minute")

def prepay_single_order_wechat(

    request: Request,

    order_id: int,

    db: SessionDep,

    member_id: int = Depends(member_subject),

):

    """微信统一下单（JSAPI），返回小程序 `uni.requestPayment` / `wx.requestPayment` 所需字段。"""

    xf = request.headers.get("x-forwarded-for")

    ip = resolve_request_client_ip(xf, request.client.host if request.client else None)

    params = prepare_wechat_jsapi_for_order(db, member_id, order_id, ip)

    return success(data=params, msg="获取支付参数成功")


@router.post("/member-card-orders")
@limiter.limit("30/minute")
def create_member_card_order_me(
    request: Request,
    body: UserMemberCardOrderCreateIn,
    db: SessionDep,
    member_id: int = Depends(member_subject),
):
    """自助开卡/续卡：创建未缴工单；支付成功后在微信回调中叠加剩余次数与总配额。"""
    _ = request
    row = create_miniprogram_member_card_order(
        db,
        member_id,
        card_kind=body.card_kind.value,
        delivery_start_date=body.delivery_start_date,
    )
    payload = UserMemberCardOrderOut.model_validate(member_card_order_user_dict(row))
    return success(data=dump_model(payload), msg="订单已创建，请继续支付")


@router.post("/member-card-orders/{order_id}/pay/wechat-jsapi")
@limiter.limit("30/minute")
def prepay_member_card_order_wechat(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: int = Depends(member_subject),
):
    """开卡工单微信统一下单（JSAPI）。"""
    xf = request.headers.get("x-forwarded-for")
    ip = resolve_request_client_ip(xf, request.client.host if request.client else None)
    params = prepare_wechat_jsapi_for_member_card_order(db, member_id, order_id, ip)
    return success(data=params, msg="获取支付参数成功")


@router.patch("/profile")

def patch_profile(body: ProfilePatchIn, db: SessionDep, member_id: int = Depends(member_subject)):

    updates = body.model_dump(exclude_unset=True)

    if not updates:

        member = get_member(db, member_id)

        return success(data=dump_model(member), msg="获取成功")

    set_avatar = "avatar_url" in updates

    set_wx = "wechat_name" in updates

    set_name = "name" in updates

    set_plan = "plan_type" in updates

    set_delivery = "delivery_start_date" in updates

    avatar_val = updates["avatar_url"] if set_avatar else None

    wechat_val: str | None = None

    if set_wx:

        raw = updates["wechat_name"]

        if raw is None:

            wechat_val = None

        else:

            s = str(raw).strip()

            wechat_val = s[:100] if s else None

    name_val = updates.get("name") if set_name else None

    plan_val = body.plan_type if set_plan else None

    delivery_val = body.delivery_start_date if set_delivery else None

    member = patch_member_profile(

        db,

        member_id,

        set_avatar=set_avatar,

        avatar_url=avatar_val,

        set_wechat_name=set_wx,

        wechat_name=wechat_val,

        set_name=set_name,

        name=name_val if isinstance(name_val, str) else None,

        set_plan_type=set_plan,

        plan_type=plan_val,

        set_delivery_start=set_delivery,

        delivery_start_date=delivery_val,

    )

    return success(data=dump_model(member), msg="资料已更新")





@router.post("/me/avatar")

@limiter.limit("30/minute")

async def upload_member_avatar_me(

    request: Request,

    file: UploadFile = File(..., description="头像图片"),

    member_id: int = Depends(member_subject),

):

    """上传会员头像至 OSS（未配置 OSS 时写入本地磁盘，行为与管理端上传一致）。"""

    _ = request

    _ = member_id

    data = await file.read()

    url = upload_member_avatar_bytes(data, file.content_type, file.filename)

    return success(data=dump_model(FileUploadOut(url=url)), msg="上传成功")

