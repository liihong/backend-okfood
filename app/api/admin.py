from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.core.deps import SessionDep, admin_subject, issue_admin_token
from app.core.limiter import limiter
from app.schemas.admin import (
    AdminAddressIn,
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
    WeeklySlotAssignIn,
)
from app.schemas.common import TokenResponse
from app.services.admin_service import (
    admin_login_user,
    admin_weekly_menu_preview,
    assign_menu_schedule,
    assign_weekly_menu_slot,
    create_category_admin,
    dashboard_meal_summary,
    delete_dish,
    list_categories_admin,
    list_dishes_admin,
    list_members_paged,
    update_settings,
    upsert_dish,
)
from app.services.delivery_sheet_service import build_delivery_sheet
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
    """今日/明日请假会员数与需准备餐品数（与配送任务同一口径）。"""
    _ = admin_username
    summary = dashboard_meal_summary(db)
    return success(data=dump_model(summary), msg="获取成功")


@router.get("/delivery-sheet")
def delivery_sheet(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    delivery_date: Annotated[date | None, Query(description="配送业务日，默认上海当日")] = None,
    area: Annotated[str | None, Query(description="按默认配送地址所属片区筛选，可选")] = None,
):
    """配送大表：激活且有余额、已达起送日、排除请假；收件信息仅默认 member_addresses；同址聚合餐数。"""
    _ = admin_username
    area_key = (area or "").strip() or None
    payload = build_delivery_sheet(db, delivery_date=delivery_date, area=area_key)
    return success(data=dump_model(payload), msg="获取成功")


@router.get("/users")
def users(
    db: SessionDep,
    admin_username: str = Depends(admin_subject),
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    validity: Annotated[str | None, Query(description="active=剩余次数>0，expired=剩余次数=0")] = None,
    inactive_only: Annotated[bool, Query(description="true=仅未开卡 is_active=false")] = False,
    delivery_region_id: Annotated[
        int | None,
        Query(ge=1, description="默认地址 delivery_region_id；与 unassigned_region 互斥"),
    ] = None,
    unassigned_region: Annotated[
        bool,
        Query(description="true=仅片区未分配（无默认地址或 delivery_region_id 为空）"),
    ] = False,
):
    _ = admin_username
    v = (validity or "").strip().lower()
    if v not in ("", "active", "expired"):
        v = ""
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
    )
    serialized = [dump_model(i) for i in items]
    return page_response(items=serialized, total=total, page=page, page_size=page_size, msg="获取成功")


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
    page: int = 1,
    page_size: int = 20,
):
    """会员开卡工单列表（分页）。"""
    _ = admin_username
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    items, total = list_card_orders_paged(
        db, q=q, pay_status=pay_status, page=page, page_size=page_size
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


@router.post("/settings")
def update_app_settings(body: SettingsIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    _ = admin_username
    update_settings(db, body)
    return success(msg="设置已更新")


@router.post("/member/address")
def member_address(body: AdminAddressIn, db: SessionDep, admin_username: str = Depends(admin_subject)):
    """修改会员地址并触发高德地理编码（失败则清空坐标）。"""
    member = admin_update_member_address(db, body.phone, body.address, operator=admin_username)
    return success(data=dump_model(member), msg="地址已更新")
