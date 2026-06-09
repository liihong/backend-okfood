from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.schemas.user import MembershipCardTemplateMemberOut
from app.services.catalog_admin_service import list_membership_templates, membership_template_public_dump
from app.services.home_banner_service import list_active_home_banners
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
