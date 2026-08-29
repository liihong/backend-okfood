"""开卡入账后的礼品券自动补发。弱依赖：任何异常只记日志，不得阻断开卡。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gift_coupon_campaign import GiftCouponCampaign
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.services.gift_coupon.audience import order_matches_active_campaign_rule
from app.services.gift_coupon.constants import CAMPAIGN_ACTIVE, GRANT_SOURCE_RULE
from app.services.gift_coupon.service import _insert_entitlement_if_absent

logger = logging.getLogger(__name__)


def try_auto_grant_after_card_credit(db: Session, order: MemberCardOrder) -> None:
    """
    开卡入账成功后调用。活动须为 active，且本张工单命中其入账日/卡型规则。

    使用 SAVEPOINT：补发失败回滚礼品券写入，不污染开卡入账事务。
    """
    try:
        with db.begin_nested():
            _auto_grant_after_card_credit(db, order)
    except Exception:
        logger.exception(
            "礼品券自动补发失败（不影响开卡入账） order_id=%s member_id=%s",
            getattr(order, "id", None),
            getattr(order, "member_id", None),
        )


def _auto_grant_after_card_credit(db: Session, order: MemberCardOrder) -> None:
    member = db.get(Member, int(order.member_id))
    if member is None or member.deleted_at is not None:
        return
    tpl = None
    if order.membership_template_id is not None:
        tpl = db.get(MembershipCardTemplate, int(order.membership_template_id))
    campaigns = db.scalars(
        select(GiftCouponCampaign).where(
            GiftCouponCampaign.store_id == int(order.store_id),
            GiftCouponCampaign.tenant_id == int(order.tenant_id),
            GiftCouponCampaign.status == CAMPAIGN_ACTIVE,
        )
    ).all()
    op = "card_credit_auto"
    for camp in campaigns:
        if not order_matches_active_campaign_rule(
            db,
            order=order,
            member=member,
            tpl=tpl,
            plan_kinds=list(camp.plan_kinds or []),
            credited_from=camp.credited_from,
            credited_to=camp.credited_to,
            exclude_membership_refunded=bool(camp.exclude_membership_refunded),
        ):
            continue
        _insert_entitlement_if_absent(
            db, campaign=camp, member_id=int(member.id), operator=op, source=GRANT_SOURCE_RULE
        )
    db.flush()
