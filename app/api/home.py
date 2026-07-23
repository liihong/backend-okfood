from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.schemas.user import MembershipCardTemplateMemberOut
from app.services.admin.catalog_admin_service import list_membership_templates, membership_template_public_dump
from app.services.client.home_banner_service import list_active_home_banners
from app.services.client.home_entry_poster_service import get_active_entry_poster, get_active_menu_poster
from app.services.client.tenant_saas_service import build_home_layout_public
from app.services.shared.store_config_service import get_store_base_delivery_fee_yuan, get_store_config
from app.services.shared.tenant_integration_service import merged_sf_integration_namespace
from app.services.shared.image_url_service import image_logo_url
from app.utils.response import dump_model, success

router = APIRouter(prefix="/home", tags=["首页"])


@router.get("/banners")
def home_banners(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序首页 Banner 列表（仅启用项）。"""
    items = list_active_home_banners(db, store_id=int(store_ctx.store_id))
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.get("/membership-card-templates")
def home_membership_card_templates(
    db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)
):
    """小程序首页会员卡包列表（仅启用项，无需登录）。"""
    rows = list_membership_templates(
        db,
        tenant_id=int(store_ctx.tenant_id),
        store_id=int(store_ctx.store_id),
        active_only=True,
    )
    items = [
        dump_model(
            MembershipCardTemplateMemberOut.model_validate(membership_template_public_dump(r))
        )
        for r in rows
    ]
    return success(data=items, msg="获取成功")


@router.get("/entry-poster")
def home_entry_poster(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序进入弹窗海报（仅启用且有图片时返回）。"""
    item = get_active_entry_poster(db, store_id=int(store_ctx.store_id))
    return success(data=dump_model(item) if item else None, msg="获取成功")


@router.get("/menu-poster")
def home_menu_page_poster(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页弹窗海报（仅启用且有图片时返回）。"""
    item = get_active_menu_poster(db, store_id=int(store_ctx.store_id))
    return success(data=dump_model(item) if item else None, msg="获取成功")


@router.get("/store-info")
def home_store_info(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页门店信息（无需登录）。"""
    cfg = get_store_config(db, store_id=int(store_ctx.store_id))
    sf = merged_sf_integration_namespace(db, int(store_ctx.tenant_id))
    pickup_addr = (sf.SF_PICKUP_ADDRESS or "").strip() or None
    return success(
        data={
            "store_id": int(cfg.store_id),
            "store_name": cfg.store_name,
            "store_logo_url": cfg.store_logo_url,
            "store_logo_thumb_url": image_logo_url(cfg.store_logo_url),
            "store_contact_phone": cfg.store_contact_phone,
            "store_lng": cfg.store_lng,
            "store_lat": cfg.store_lat,
            "store_pickup_address": pickup_addr,
            "base_delivery_fee_yuan": float(
                get_store_base_delivery_fee_yuan(db, store_id=int(store_ctx.store_id))
            ),
        },
        msg="获取成功",
    )


@router.get("/layout")
def home_layout(
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):
    """
    首页定制 layout（方案 B）：按租户返回 template + blocks。

    未配置时返回 preset 默认编排；模板库接口不可用时 fallback ext.homeLayoutPreset。
    """
    payload = build_home_layout_public(db, store_ctx)
    return success(data=payload, msg="获取成功")
