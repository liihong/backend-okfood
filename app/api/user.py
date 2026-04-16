from fastapi import APIRouter, Depends, HTTPException, Request



from app.core.config import settings

from app.core.deps import SessionDep, issue_member_token, issue_member_token_wx_mini, member_subject

from app.core.limiter import limiter

from app.integrations.sms_dispatch import SmsDispatchError

from app.integrations.wechat_mini import (

    WeChatMiniError,

    get_phone_pure_number,

    jscode2session,

    wx_mini_configured,

)

from app.schemas.common import TokenResponse

from app.schemas.member_address import MemberAddressCreateIn, MemberAddressUpdateIn

from app.schemas.user import ActivateIn, LeaveIn, ProfilePatchIn, RegisterIn, SmsLoginIn, SmsSendIn, WxMiniLoginIn

from app.services import sms as sms_service

from app.services.member_address_service import create_address, delete_address, list_addresses, update_address

from app.services.member_service import (

    activate_member,

    ensure_member_stub,

    get_member,

    leave_request,

    patch_member_profile,

    register_member,

)

from app.utils.response import dump_model, success



router = APIRouter(prefix="/user", tags=["会员端"])





@router.post("/sms/send")

@limiter.limit("6/minute")

def send_sms(request: Request, body: SmsSendIn, db: SessionDep):

    """发送短信验证码：经 SMS_PROVIDER 调用真实通道；响应中不包含验证码。"""

    if not settings.SMS_ENABLED:

        raise HTTPException(status_code=503, detail="短信验证码功能暂未开放")

    try:

        sms_service.send_login_code(db, body.phone)

    except SmsDispatchError:

        raise HTTPException(status_code=502, detail="短信发送失败，请稍后重试或联系管理员")

    return success(msg="验证码已发送")





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

        jscode2session(body.js_code)

        phone = get_phone_pure_number(body.phone_code)

    except WeChatMiniError as e:

        raise HTTPException(status_code=e.status_code, detail=str(e))

    member_id = ensure_member_stub(db, phone)

    token = TokenResponse(access_token=issue_member_token_wx_mini(member_id))

    return success(data=dump_model(token), msg="登录成功")





@router.post("/sms/login")

@limiter.limit("30/minute")

def login_via_sms(request: Request, body: SmsLoginIn, db: SessionDep):

    if not settings.SMS_ENABLED:

        raise HTTPException(status_code=503, detail="短信验证码功能暂未开放")

    if not sms_service.verify_login_code(db, body.phone, body.code):

        raise HTTPException(status_code=400, detail="验证码错误或已过期")

    member_id = ensure_member_stub(db, body.phone)

    token = TokenResponse(access_token=issue_member_token(member_id))

    return success(data=dump_model(token), msg="登录成功")





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

