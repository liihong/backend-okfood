from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.core.deps import SessionDep, admin_subject, issue_admin_token
from app.models.member import Member
from app.models.enums import PlanType
from app.core.limiter import limiter
from app.schemas.member_address import MemberAddressUpdateIn
from app.schemas.admin import (
    AdminAddressIn,
    AdminDeliveryMarkIn,
    AdminLoginIn,
    AdminMemberLeaveIn,
    AdminMemberPatchIn,
    CardOrderCreateIn,
    CardOrderPatchIn,
    CategoryCreateIn,
    DishUpsertIn,
    MenuScheduleAssignIn,
    RechargeIn,
    SettingsIn,
    StoreConfigUpdateIn,
    WeeklySlotAssignIn,
    MenuDayTotalStockIn,
    SfSameCityPreviewOut,
    SfSameCityPushIn,
    SfSameCityPushOut,
    SfSameCityPushMonitorRow,
    SfSameCityCancelIn,
    SfSameCityCancelOut,
)
from app.schemas.common import TokenResponse
from app.services.admin_service import (
    admin_delete_member,
    admin_login_user,
    admin_weekly_menu_preview,
    assign_menu_schedule,
    assign_weekly_menu_slot,
    set_weekly_slot_menu_total_stock,
    create_category_admin,
    dashboard_meal_summary,
    delete_dish,
    list_categories_admin,
    list_dishes_admin,
    list_members_paged,
    member_list_overview_counts,
    update_settings,
    upsert_dish,
)
from app.services.sf_order_fulfillment_service import (
    list_sf_same_city_pushes_for_monitor,
)
from app.services.sf_same_city_service import cancel_sf_same_city_push, preview_sf_same_city, push_sf_same_city
from app.services.store_config_service import get_store_config, update_store_config
from app.services.delivery_sheet_service import build_delivery_sheet
from app.services.admin_delivery_fulfillment_service import admin_mark_subscription_fulfilled
from app.services.member_address_service import list_addresses, update_address
from app.services.member_service import (
    admin_member_leave,
    admin_patch_member_profile,
    admin_update_member_address,
)
from app.services.member_card_order_service import (
    create_card_order,
    list_card_orders_paged,
    update_card_order,
)
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/admin", tags=["管理端"])


@router.post("/login")
@limiter.limit("30/minute")
def login(request: Request, body: AdminLoginIn, db: SessionDep):
    admin_login_user(db, body.username, body.password)
    token = TokenResponse(access_token=issue_admin_token(body.username))
    return success(data=dump_model(token), msg="登录成功")


@router.get("/dashboard-summary")
def dashboard_summary(db: SessionDep, admin_username: str = Depends(admin_subject)):
    """今日/明日请假会员数与需准备餐品数（与配送任务同一口径；周日与法定节假日为 0）。"""
    _ = admin_username
    summary = dashboard_meal_summary(db)
    return success(data=dump_model(summary), msg="获取成功")


@router.get("/delivery-sheet")
def delivery_sheet(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    delivery_date: Annotated[date | None, Query(description="配送业务日，默认上海当日")] = None,
    area: Annotated[str | None, Query(description="按默认配送地址所属片区筛选，可选")] = None,
    phone: Annotated[
        str | None,
        Query(description="按会员手机号筛选；可输后几位或完整号码，忽略空格与符号"),
    ] = None,
):
    """配送大表：激活且有余额、已达起送日、排除请假；周日与法定节假日不生成订阅派单；收件信息仅默认 member_addresses；同址聚合餐数。
    配送到家会员带 is_delivered（与 delivery_logs / 骑手确认送达同源）；门店自提不参与到家送达统计。"""
    _ = admin_username
    area_key = (area or "").strip() or None
    phone_key = (phone or "").strip() or None
    payload = build_delivery_sheet(
        db, delivery_date=delivery_date, area=area_key, phone=phone_key
    )
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/delivery-sf/preview", response_model=None)
def delivery_sf_preview(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    delivery_date: Annotated[date | None, Query(description="配送业务日，默认上海当日")] = None,
    area: Annotated[str | None, Query(description="同 delivery-sheet 片区筛选")] = None,
    phone: Annotated[str | None, Query(description="同 delivery-sheet 手机筛选")] = None,
):
    """
    顺丰同城创单前预览：按停靠点合并大表+单点餐，返回 Excel 同结构字段的默认值。
    需配置：``SF_OPEN_*``、``SF_PICKUP_PHONE``、``SF_PICKUP_ADDRESS``。
    """
    _ = admin_username
    out: SfSameCityPreviewOut = preview_sf_same_city(
        db, delivery_date=delivery_date, area=area, phone=phone
    )
    return success(data=dump_model(out), msg="获取成功")


@router.post("/delivery-sf/push", response_model=None)
def delivery_sf_push(
    body: SfSameCityPushIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """
    提交勾选的行到顺丰 ``createorder``；未勾选行忽略；同停靠点同业务日已成功的行会拒绝防重复。

    开发环境若无顺丰账号会失败并写入 ``sf_same_city_pushes`` 的 error_ 字段便于排查。
    """
    _ = admin_username
    try:
        out: SfSameCityPushOut = push_sf_same_city(db, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=dump_model(out), msg="处理完成")


@router.get("/delivery-sf/pushes", response_model=None)
def delivery_sf_pushes(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    delivery_date: Annotated[date | None, Query(description="业务日，不传则全部")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """顺丰同城创单落地记录列表（控制台回调状态），用于后台订单监控。"""
    _ = admin_username
    items_raw, total = list_sf_same_city_pushes_for_monitor(
        db, delivery_date=delivery_date, page=page, page_size=page_size
    )
    items = [SfSameCityPushMonitorRow.model_validate(x) for x in items_raw]
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.post("/delivery-sf/pushes/{push_id}/cancel", response_model=None)
def delivery_sf_cancel_push(
    push_id: int,
    body: SfSameCityCancelIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """调用顺丰 ``cancelorder`` 取消配送（商家异常场景）；同步返回顺丰响应 JSON。"""
    _ = admin_username
    raw = cancel_sf_same_city_push(db, push_id=push_id, cancel_reason=body.cancel_reason)
    out = SfSameCityCancelOut.model_validate(raw)
    return success(data=dump_model(out), msg="取消请求已提交")


@router.post("/delivery-mark")
def delivery_mark(
    body: AdminDeliveryMarkIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """大表人工标记：配送到家 / 门店自提完成（扣次、写 delivery_logs；不增加骑手待结算）。"""
    admin_mark_subscription_fulfilled(
        db,
        member_id=body.member_id,
        delivery_date=body.delivery_date,
        admin_username=admin_username,
        kind=body.kind,
    )
    return success(msg="已标记")


@router.get("/users/stats")
def users_stats(
    response: Response,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """会员档案库顶栏：总会员数、生效中、已过期（与列表 validity 口径一致）。"""
    response.headers["Cache-Control"] = "no-store"
    _ = admin_username
    out = member_list_overview_counts(db)
    return success(data=dump_model(out), msg="获取成功")


@router.get("/users")
def users(
    response: Response,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    validity: Annotated[
        str | None,
        Query(description="不传或空=全部；active=剩余次数>0；expired=剩余次数=0"),
    ] = None,
    plan_type: Annotated[
        str | None,
        Query(description="套餐筛选：周卡 | 月卡；不传或空=不限"),
    ] = None,
    inactive_only: Annotated[bool, Query(description="true=仅未开卡 is_active=false")] = False,
    delivery_region_id: Annotated[
        int | None,
        Query(ge=1, description="默认地址 delivery_region_id；与 unassigned_region 互斥"),
    ] = None,
    unassigned_region: Annotated[
        bool,
        Query(description="true=仅片区未分配（无默认地址或 delivery_region_id 为空）"),
    ] = False,
    on_leave_only: Annotated[
        bool,
        Query(description="true=仅当前请假中（与列表「请假中」状态一致：区间含今日或明日请假未过期）"),
    ] = False,
):
    response.headers["Cache-Control"] = "no-store"
    _ = admin_username
    v = (validity or "").strip().lower()
    if v not in ("", "active", "expired"):
        v = ""
    pt = (plan_type or "").strip()
    if pt not in ("", PlanType.WEEK.value, PlanType.MONTH.value):
        raise HTTPException(status_code=400, detail="plan_type 仅支持 周卡 或 月卡")
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    if delivery_region_id is not None and unassigned_region:
        raise HTTPException(status_code=400, detail="不能同时指定 delivery_region_id 与 unassigned_region")
    items, total = list_members_paged(
        db,
        q_phone=q,
        page=page,
        page_size=page_size,
        validity=v or None,
        inactive_only=inactive_only,
        delivery_region_id=delivery_region_id,
        unassigned_region=unassigned_region,
        plan_type=pt or None,
        on_leave_only=on_leave_only,
    )
    serialized = [dump_model(i) for i in items]
    return page_response(items=serialized, total=total, page=page, page_size=page_size, msg="获取成功")


@router.delete("/users/{member_id}")
def admin_delete_member_route(
    member_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """删除会员：无业务流水时物理删除；否则逻辑删除并保留追溯数据。"""
    _ = admin_username
    out = admin_delete_member(db, member_id)
    return success(data=out, msg=out.get("msg") or "已删除")


@router.post("/recharge")
def recharge(
    body: RechargeIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """已废弃：次数入账须走开卡工单并同步，以便留存工单与 balance_logs.detail。"""
    _ = body, db, admin_username
    raise HTTPException(
        status_code=400,
        detail="续卡与次数调整请使用「开卡工单」：创建工单、标记已缴后执行同步入账；不再支持档案页直连接口。",
    )


@router.get("/card-orders")
def card_orders(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    q: str | None = None,
    pay_status: Annotated[str | None, Query(description="未缴 | 已缴")] = None,
    include_history: Annotated[
        bool,
        Query(description="true=含已缴且已入账等全部历史；默认 false 仅待处理工单"),
    ] = False,
    page: int = 1,
    page_size: int = 20,
):
    """会员开卡工单列表（分页）。"""
    _ = admin_username
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    items, total = list_card_orders_paged(
        db,
        q=q,
        pay_status=pay_status,
        page=page,
        page_size=page_size,
        include_history=include_history,
    )
    serialized = [dump_model(i) for i in items]
    return page_response(
        items=serialized, total=total, page=page, page_size=page_size, msg="获取成功"
    )


@router.post("/card-orders")
def card_orders_create(
    body: CardOrderCreateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    out = create_card_order(db, body, operator=admin_username)
    return success(data=dump_model(out), msg="工单已创建")


@router.patch("/card-orders/{order_id}")
def card_orders_patch(
    order_id: int,
    body: CardOrderPatchIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    out = update_card_order(db, order_id, body, operator=admin_username)
    return success(data=dump_model(out), msg="工单已更新")


@router.post("/member/profile")
def member_profile_patch(body: AdminMemberPatchIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    fs = body.model_fields_set
    member = admin_patch_member_profile(
        db,
        phone=body.phone,
        name=body.name,
        remarks=body.remarks,
        address=body.address,
        use_auto_area=body.use_auto_area,
        operator=admin_username,
        daily_meal_units=body.daily_meal_units,
        plan_type=body.plan_type,
        set_balance="balance" in fs,
        balance=body.balance,
        set_delivery_start_date="delivery_start_date" in fs,
        delivery_start_date=body.delivery_start_date,
        set_store_pickup="store_pickup" in fs,
        store_pickup=body.store_pickup,
        set_delivery_region_id="delivery_region_id" in fs,
        delivery_region_id=body.delivery_region_id,
        set_delivery_deferred="delivery_deferred" in fs,
        delivery_deferred=body.delivery_deferred,
        set_remarks="remarks" in fs,
    )
    return success(data=dump_model(member), msg="会员信息已更新")


@router.post("/member/leave")
def member_leave(body: AdminMemberLeaveIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """代会员设置请假（明日 / 区间 / 取消），不受小程序当日请假截止时间限制。"""
    _ = admin_username
    member = admin_member_leave(
        db,
        phone=body.phone,
        typ=body.type,
        start=body.start,
        end=body.end,
    )
    return success(data=dump_model(member), msg="请假状态已更新")


@router.get("/users/{member_id}/addresses")
def admin_member_addresses_list(
    member_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """会员档案：列出该会员全部配送地址（含地图文案、门牌、经纬度与省市区）。"""
    _ = admin_username
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    items = list_addresses(db, member_id)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.patch("/users/{member_id}/addresses/{address_id}")
def admin_member_address_patch(
    member_id: int,
    address_id: int,
    body: MemberAddressUpdateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """管理端保存会员地址：可与小程序拆分一致（地点文案 / 门牌），坐标变更时服务端逆地理写入省市区并重算片区。"""
    _ = admin_username
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    out = update_address(db, member_id, address_id, body)
    return success(data=dump_model(out), msg="地址已保存")


@router.get("/dishes")
def dishes(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    enabled_only: bool = False,
    q: Annotated[str | None, Query(description="按名称模糊筛选")] = None,
):
    """菜品库列表，排期时可从中选 `dish_id`。"""
    _ = admin_username
    items = list_dishes_admin(db, enabled_only=enabled_only, q=q)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.post("/dish")
def dish_upsert(body: DishUpsertIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    _ = admin_username
    out = upsert_dish(db, body)
    return success(data=dump_model(out), msg="菜品已保存")


@router.delete("/dish/{dish_id}")
def dish_delete(
    dish_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    _ = admin_username
    delete_dish(db, dish_id)
    return success(msg="菜品已删除")


@router.post("/menu/schedule")
def menu_schedule(body: MenuScheduleAssignIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """将某日排期绑定到菜品库中的 `dish_id`（同月同一菜仅能排一天）。"""
    _ = admin_username
    assign_menu_schedule(db, body)
    return success(msg="排期已保存")


@router.get("/categories")
def categories(db: SessionDep, admin_username: str = Depends(admin_subject)):
    """商品分类列表（含 code=weekly 的「每周餐品」）。"""
    _ = admin_username
    items = list_categories_admin(db)
    return success(data=[dump_model(i) for i in items], msg="获取成功")


@router.post("/category")
def category_create(body: CategoryCreateIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    _ = admin_username
    out = create_category_admin(db, body)
    return success(data=dump_model(out), msg="分类已创建")


@router.get("/menu/weekly-slots")
def menu_weekly_slots(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    week_start: Annotated[date | None, Query(description="指定周任意一天则只返回该周槽位；不传则返回本周+下周")] = None,
):
    """每周餐品槽位：不传参数时同时返回本周与下周，便于预告维护（无需翻周拷贝数据）。"""
    _ = admin_username
    return success(data=admin_weekly_menu_preview(db, week_start), msg="获取成功")


@router.post("/menu/weekly-slot")
def menu_weekly_slot(body: WeeklySlotAssignIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """设置某周 slot（1–7）对应的菜品；`dish_id` 为空则清空该槽。"""
    _ = admin_username
    assign_weekly_menu_slot(db, body)
    return success(msg="周槽位已保存")


@router.post("/menu/day-total-stock")
def menu_day_total_stock(body: MenuDayTotalStockIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """设置该周某一天对应菜品的日总份数；用于单次卡可售=总份数−当日应配送−已付单次。"""
    _ = admin_username
    set_weekly_slot_menu_total_stock(db, body)
    return success(msg="日总库存已保存")


@router.post("/settings")
def update_app_settings(body: SettingsIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    _ = admin_username
    update_settings(db, body)
    return success(msg="设置已更新")


@router.get("/store-config")
def admin_store_config_get(db: SessionDep, admin_username: str = Depends(admin_subject)):
    """门店基础信息：名称、Logo、地图锚点坐标（GCJ-02）。"""
    _ = admin_username
    cfg = get_store_config(db)
    return success(data=dump_model(cfg), msg="获取成功")


@router.put("/store-config")
def admin_store_config_put(
    body: StoreConfigUpdateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
):
    """更新门店配置；未传的字段保持不变（PATCH 语义）。"""
    _ = admin_username
    cfg = update_store_config(db, body)
    return success(data=dump_model(cfg), msg="已保存")


@router.post("/member/address")
def member_address(body: AdminAddressIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """修改会员地址并触发高德地理编码（失败则清空坐标）。"""
    member = admin_update_member_address(db, body.phone, body.address, operator=admin_username)
    return success(data=dump_model(member), msg="地址已更新")
