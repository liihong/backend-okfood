from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.schemas.user import MembershipCardTemplateMemberOut
from app.services.catalog_admin_service import list_membership_templates, membership_template_public_dump
from app.services.home_banner_service import list_active_home_banners
from app.services.home_entry_poster_service import get_active_entry_poster
from app.services.store_config_service import get_store_config
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


@router.get("/store-info")
def home_store_info(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页门店信息（无需登录）。"""
    cfg = get_store_config(db, store_id=int(store_ctx.store_id))
    return success(
        data={
            "store_id": int(cfg.store_id),
            "store_name": cfg.store_name,
            "store_logo_url": cfg.store_logo_url,
            "store_contact_phone": cfg.store_contact_phone,
        },
        msg="获取成功",
    )


@router.get("/store-info")
def home_store_info(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页门店信息（无需登录）。"""
    cfg = get_store_config(db, store_id=int(store_ctx.store_id))
    return success(
        data={
            "store_id": int(cfg.store_id),
            "store_name": cfg.store_name,
            "store_logo_url": cfg.store_logo_url,
            "store_contact_phone": cfg.store_contact_phone,
        },
        msg="获取成功",
    )
