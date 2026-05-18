from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile



from app.core.deps import (
    SessionDep,
    issue_member_token,
    member_auth_scope,
    MemberAuthScope,
    MemberIdScoped,
    public_store_dep,
    PublicStoreContext,
)

from app.core.limiter import limiter

from app.integrations.wechat_mini import (
    WeChatMiniError,
    get_phone_pure_number,
    jscode2session,
    wx_mini_configured_for_tenant,
)

from app.schemas.common import TokenResponse

from app.schemas.member_address import (
    DeliveryRegionCheckIn,
    DeliveryRegionCheckOut,
    MemberAddressCreateIn,
    MemberAddressUpdateIn,
)

from app.schemas.admin import FileUploadOut

from sqlalchemy import select

from app.models.member import Member

from app.schemas.user import (
    ActivateIn,
    LeaveIn,
    MemberCardPricesOut,
    MembershipCardTemplateMemberOut,
    ProfilePatchIn,
    RegisterIn,
    UserMemberCardOrderCreateIn,
    UserMemberCardOrderOut,
    WxMiniJsCodeIn,
    WxMiniLoginIn,
)

from app.services.member_delivery_deduction_service import list_member_delivery_deductions
from app.services.oss_upload_service import upload_member_avatar_bytes

from app.services.member_address_service import (
    check_coords_in_delivery_region,
    create_address,
    delete_address,
    list_addresses,
    update_address,
)

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
    sync_member_card_from_wechat_or_raise,
)
from app.services.catalog_admin_service import (
    list_membership_templates,
    membership_template_public_dump,
)
from app.services.single_meal_order_service import (
    create_single_meal_order,
    get_member_single_meal_order,
    list_member_single_meal_orders,
    prepare_wechat_jsapi_for_order,
)

from app.services.store_config_service import get_member_card_prices_extended

from app.integrations.wechat_pay_v2 import resolve_request_client_ip

from app.utils.response import dump_model, page_response, success



router = APIRouter(prefix="/user", tags=["会员端"])





@router.post("/wx/mini/login")

@limiter.limit("30/minute")

def login_wx_mini(
    request: Request,
    body: WxMiniLoginIn,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):

    """

    微信小程序手机号授权登录：校验 `js_code`，用 `phone_code` 调微信接口取手机号，签发会员 JWT。

    需在环境变量中配置 WX_MINI_APPID、WX_MINI_SECRET。

    门店由请求头 ``X-Store-Id`` 解析（未传则默认门店）；档案按门店隔离。

    """

    if not wx_mini_configured_for_tenant(db, int(store_ctx.tenant_id)):
        raise HTTPException(status_code=503, detail="微信小程序登录未配置或未开放")

    try:

        sess = jscode2session(body.js_code, db=db, tenant_id=int(store_ctx.tenant_id))

        phone = get_phone_pure_number(body.phone_code, db=db, tenant_id=int(store_ctx.tenant_id))

    except WeChatMiniError as e:

        raise HTTPException(status_code=e.status_code, detail=str(e))

    openid = str(sess.get("openid") or "").strip() or None

    member_id = ensure_member_stub(
        db,
        phone,
        tenant_id=int(store_ctx.tenant_id),
        store_id=int(store_ctx.store_id),
        wx_mini_openid=openid,
    )

    token = TokenResponse(access_token=issue_member_token(member_id))

    return success(data=dump_model(token), msg="登录成功")


@router.post("/wx/mini/sync-openid")
@limiter.limit("30/minute")
def sync_wx_mini_openid(
    request: Request,
    body: WxMiniJsCodeIn,
    db: SessionDep,
    auth: MemberAuthScope = Depends(member_auth_scope),
):
    """已持会员 JWT 时，用当前小程序会话的 `js_code` 写入 `members.wx_mini_openid`，便于 JSAPI 支付。"""
    _ = request
    member_id = auth.member_id
    member = auth.member
    if not wx_mini_configured_for_tenant(db, int(member.tenant_id)):
        raise HTTPException(status_code=503, detail="微信小程序登录未配置或未开放")
    try:
        sess = jscode2session(body.js_code, db=db, tenant_id=int(member.tenant_id))
    except WeChatMiniError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    openid = str(sess.get("openid") or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="微信未返回用户标识，请稍后重试")
    bound_id = db.scalar(
        select(Member.id).where(
            Member.wx_mini_openid == openid,
            Member.deleted_at.is_(None),
            Member.store_id == member.store_id,
        )
    )
    if bound_id is not None and int(bound_id) != int(member_id):
        raise HTTPException(
            status_code=400,
            detail="当前微信已绑定其他会员账号，请使用对应账号登录或联系客服",
        )
    member.wx_mini_openid = openid
    db.commit()
    return success(msg="已同步微信标识")


@router.post("/register")

@limiter.limit("20/minute")

def register(
    request: Request,
    body: RegisterIn,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):

    """新成员登记：写入前尝试高德地理编码（无 Key 或失败时坐标为空）。"""

    member = register_member(
        db,
        body,
        tenant_id=int(store_ctx.tenant_id),
        store_id=int(store_ctx.store_id),
    )

    return success(data=dump_model(member), msg="注册成功")





@router.post("/activate")

def activate(body: ActivateIn, db: SessionDep, member_id: MemberIdScoped):

    _ = body

    member = activate_member(db, member_id)

    return success(data=dump_model(member), msg="激活成功")





@router.post("/leave")

def leave(request: Request, body: LeaveIn, db: SessionDep, member_id: MemberIdScoped):

    """请假 / 取消：`clear_tomorrow` 仅取消「明天请假」；`cancel` 清空明天与区间。"""

    ip = resolve_request_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    member = leave_request(db, member_id, body.type, body.start, body.end, ip_address=ip)

    return success(data=dump_model(member), msg="请假状态已更新")





@router.get("/me")

def read_member_me(db: SessionDep, member_id: MemberIdScoped):

    """当前登录会员档案：JWT sub 为 members.id。"""

    member = get_member(db, member_id)

    return success(data=dump_model(member), msg="获取成功")


@router.get("/member-card-prices")
def read_member_card_prices(db: SessionDep, auth: MemberAuthScope = Depends(member_auth_scope)):
    """周卡/月卡当前标价（与自助开卡下单金额一致，数据来自后台门店配置）。"""
    ext = get_member_card_prices_extended(db, store_id=int(auth.store_id))

    def fmt(d: Decimal) -> str:
        return format(d.quantize(Decimal("0.01")), "f")

    def fmt_opt(d: Decimal | None) -> str | None:
        if d is None:
            return None
        return fmt(d)

    payload = MemberCardPricesOut(
        week_price_yuan=fmt(ext.week_price_yuan),
        month_price_yuan=fmt(ext.month_price_yuan),
        week_list_price_yuan=fmt_opt(ext.week_list_price_yuan),
        month_list_price_yuan=fmt_opt(ext.month_list_price_yuan),
        promotion_active=ext.promotion_active,
    )
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/membership-card-templates")
def read_membership_card_templates_catalog(
    db: SessionDep, auth: MemberAuthScope = Depends(member_auth_scope)
):
    """当前门店已启用的会员卡模版（样式图、划线价/优惠价与文案）；不计价，自助开卡仍以门店周/月卡配置为准。"""
    tid = int(auth.member.tenant_id)
    sid = int(auth.store_id)
    rows = list_membership_templates(db, tenant_id=tid, store_id=sid, active_only=True)
    items = [
        dump_model(MembershipCardTemplateMemberOut.model_validate(membership_template_public_dump(r)))
        for r in rows
    ]
    return success(data=items, msg="获取成功")


@router.get("/me/addresses")

def read_addresses_me(db: SessionDep, member_id: MemberIdScoped):

    """会员配送地址列表（多地址）；默认地址优先。"""

    items = list_addresses(db, member_id)

    return success(data=[dump_model(x) for x in items], msg="获取成功")




@router.post("/me/delivery-region/check")
@limiter.limit("60/minute")
def check_delivery_region_me(
    request: Request,
    body: DeliveryRegionCheckIn,
    db: SessionDep,
    auth: MemberAuthScope = Depends(member_auth_scope),
):
    """地图选点是否落在启用配送片区内：命中返回片区 id/名称；未命中 in_region=false。"""
    _ = request
    in_region, rid, name = check_coords_in_delivery_region(
        db,
        float(body.location.lng),
        float(body.location.lat),
        tenant_id=int(auth.member.tenant_id),
    )
    payload = DeliveryRegionCheckOut(in_region=in_region, delivery_region_id=rid, region_name=name)
    return success(data=dump_model(payload), msg="校验完成")





@router.post("/me/addresses")

@limiter.limit("30/minute")

def add_address_me(request: Request, body: MemberAddressCreateIn, db: SessionDep, member_id: MemberIdScoped):

    """新增配送地址：高德地理编码（失败则坐标为空，区域保留客户端或「未分配」）；首条地址自动设为默认。"""

    ip = resolve_request_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    out = create_address(db, member_id, body, ip_address=ip)

    return success(data=dump_model(out), msg="保存成功")





@router.patch("/me/addresses/{address_id}")

def patch_address_me(

    request: Request,

    address_id: int,

    body: MemberAddressUpdateIn,

    db: SessionDep,

    member_id: MemberIdScoped,

):

    ip = resolve_request_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    out = update_address(db, member_id, address_id, body, ip_address=ip)

    return success(data=dump_model(out), msg="已更新")





@router.delete("/me/addresses/{address_id}")

def remove_address_me(request: Request, address_id: int, db: SessionDep, member_id: MemberIdScoped):

    ip = resolve_request_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )
    delete_address(db, member_id, address_id, ip_address=ip)

    return success(msg="已删除")




@router.get("/me/delivery-deductions")
def list_delivery_deductions_me(
    db: SessionDep,
    member_id: MemberIdScoped,
    page: int = 1,
    page_size: int = 20,
):
    """套餐配送：已确认送达并扣减剩余餐次的业务日列表（按配送日倒序）。"""
    items, total = list_member_delivery_deductions(db, member_id, page=page, page_size=page_size)
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )





@router.get("/single-orders")
def list_single_orders_me(
    db: SessionDep,
    member_id: MemberIdScoped,
    page: int = 1,
    page_size: int = 20,
):
    """当前会员的单次点餐订单列表（按下单时间倒序）。"""
    items, total = list_member_single_meal_orders(db, member_id, page=page, page_size=page_size)
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.get("/single-orders/{order_id}")
def read_single_order_me(
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """单次点餐订单详情（仅本人）。"""
    out = get_member_single_meal_order(db, member_id, order_id)
    return success(data=dump_model(out), msg="获取成功")


@router.post("/single-orders")

@limiter.limit("30/minute")

def create_single_order_me(

    request: Request,

    body: SingleMealOrderCreateIn,

    db: SessionDep,

    member_id: MemberIdScoped,

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

    member_id: MemberIdScoped,

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
    member_id: MemberIdScoped,
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
    member_id: MemberIdScoped,
):
    """开卡工单微信统一下单（JSAPI）。"""
    xf = request.headers.get("x-forwarded-for")
    ip = resolve_request_client_ip(xf, request.client.host if request.client else None)
    params = prepare_wechat_jsapi_for_member_card_order(db, member_id, order_id, ip)
    return success(data=params, msg="获取支付参数成功")


@router.post("/member-card-orders/{order_id}/sync-wechat-pay")
@limiter.limit("30/minute")
def sync_member_card_order_after_pay(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """
    小程序在 `requestPayment` 成功（`success`）后立即调用：向微信查询订单并执行与支付通知相同的入账逻辑。

    用于弥补异步通知不可达或延迟时「已扣款但次数未到账」。
    """
    _ = request
    sync_member_card_from_wechat_or_raise(db, member_id, order_id)
    member = get_member(db, member_id)
    return success(data=dump_model(member), msg="支付结果已同步")


@router.patch("/profile")

def patch_profile(request: Request, body: ProfilePatchIn, db: SessionDep, member_id: MemberIdScoped):

    updates = body.model_dump(exclude_unset=True)

    if not updates:

        member = get_member(db, member_id)

        return success(data=dump_model(member), msg="获取成功")

    ip = resolve_request_client_ip(
        request.headers.get("x-forwarded-for"),
        request.client.host if request.client else None,
    )

    set_avatar = "avatar_url" in updates

    set_wx = "wechat_name" in updates

    set_name = "name" in updates

    set_plan = "plan_type" in updates

    set_delivery = "delivery_start_date" in updates

    set_defer = "delivery_deferred" in updates

    defer_val = body.delivery_deferred if set_defer else None

    set_pickup = "store_pickup" in updates

    pickup_val = body.store_pickup if set_pickup else None

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

    card_pay_mode_val = body.card_pay_mode if "card_pay_mode" in updates else None

    set_units = "daily_meal_units" in updates

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

        set_delivery_deferred=set_defer,

        delivery_deferred=defer_val,

        card_pay_mode=card_pay_mode_val,

        set_store_pickup=set_pickup,

        store_pickup=pickup_val,

        set_daily_meal_units=set_units,

        daily_meal_units=body.daily_meal_units if set_units else None,

        ip_address=ip,

    )

    return success(data=dump_model(member), msg="资料已更新")





@router.post("/me/avatar")

@limiter.limit("30/minute")

async def upload_member_avatar_me(

    request: Request,

    member_id: MemberIdScoped,

    file: UploadFile = File(..., description="头像图片"),

):

    """上传会员头像至 OSS（未配置 OSS 时写入本地磁盘，行为与管理端上传一致）。"""

    _ = request

    _ = member_id

    data = await file.read()

    url = upload_member_avatar_bytes(data, file.content_type, file.filename)

    return success(data=dump_model(FileUploadOut(url=url)), msg="上传成功")

