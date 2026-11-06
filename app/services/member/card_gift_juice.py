"""开卡赠送果蔬汁：按次数逐笔创建普通商城订单。

每笔数量为 1，金额 0，已支付、线下。失败不得回滚开卡入账（调用方用 SAVEPOINT）。
不走礼品券，也不进入晚餐大表。
下个版本退款待办：按备注「开卡工单#id赠送果蔬汁」取消这些单并退库存。本次退款不处理。
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store_retail_product import StoreRetailProduct
from app.schemas.store_retail_order import StoreRetailOrderCreateIn, StoreRetailOrderItemIn
from app.services.client.store_retail_order_service import (
    _FULFILLMENT_AWAITING_ACCEPT,
    _final_out_trade_no,
    _new_temp_out_trade_no,
    _notify_store_retail_order_paid,
)
from app.constants import ADDRESS_USAGE_MEAL, ADDRESS_USAGE_RETAIL
from app.services.member.member_address_service import (
    delivery_region_name_map,
    ensure_retail_address,
    get_default_address,
    routing_area_label,
)
from app.services.retail.retail_order_persist import persist_retail_order_with_items
from app.services.retail.retail_stock_service import assert_retail_stock_available

logger = logging.getLogger(__name__)


def create_gift_juice_orders_for_card(
    db: Session,
    *,
    order: MemberCardOrder,
    template: MembershipCardTemplate | None,
) -> int:
    """按赠送次数创建 N 笔果蔬汁订单。返回成功笔数。条件不够时记日志并返回 0，不抛给开卡。"""
    if template is None:
        return 0
    times = int(getattr(template, "gift_retail_quantity", 0) or 0)
    product_id = getattr(template, "gift_retail_product_id", None)
    if times <= 0 or product_id is None:
        return 0
    member = db.get(Member, int(order.member_id))
    if member is None or member.deleted_at is not None:
        return 0
    product = db.get(StoreRetailProduct, int(product_id))
    if product is None or int(product.store_id) != int(order.store_id):
        logger.warning(
            "开卡赠送果蔬汁跳过：SKU 不存在或不属于本店 order_id=%s product_id=%s",
            int(order.id),
            product_id,
        )
        return 0
    # 一次校验 N 件，避免逐笔下单时前几笔把库存占满后留下半截赠送
    assert_retail_stock_available(db, product_id=int(product.id), need_qty=times)

    addr = get_default_address(db, int(member.id), usage=ADDRESS_USAGE_MEAL)
    if addr is None:
        addr = get_default_address(db, int(member.id), usage=ADDRESS_USAGE_RETAIL)
    store_pickup = False
    addr_id = None
    area = "门店自提"
    if addr is not None:
        retail_addr = ensure_retail_address(db, addr)
        names = delivery_region_name_map(
            db, {int(retail_addr.delivery_region_id)} if retail_addr.delivery_region_id else set()
        )
        area = routing_area_label(retail_addr, names)
        addr_id = int(retail_addr.id)
    elif bool(member.store_pickup):
        store_pickup = True
    else:
        logger.warning(
            "开卡赠送果蔬汁跳过：会员没有收货地址 order_id=%s member_id=%s",
            int(order.id),
            int(member.id),
        )
        return 0

    created = 0
    for index in range(1, times + 1):
        # 一笔一次，数量固定 1。第 index 笔与其余笔是独立商城订单。
        body = StoreRetailOrderCreateIn(
            items=[StoreRetailOrderItemIn(retail_product_id=int(product.id), quantity=1)],
            member_address_id=addr_id,
            store_pickup=store_pickup,
            member_coupon_id=None,
        )
        row = persist_retail_order_with_items(
            db,
            tenant_id=int(order.tenant_id),
            store_id=int(order.store_id),
            member_id=int(member.id),
            body=body,
            out_trade_no_temp=_new_temp_out_trade_no(),
            fulfillment_date=today_shanghai(),
            routing_area=area,
            member_address_id=addr_id,
            pay_status="已支付",
            pay_channel="线下",
            fulfillment_status=_FULFILLMENT_AWAITING_ACCEPT,
            remark=f"开卡工单#{int(order.id)}赠送果蔬汁（{index}/{times}）"[:500],
        )
        row.out_trade_no = _final_out_trade_no(int(row.id))
        row.amount_yuan = Decimal("0.00")
        row.original_amount_yuan = Decimal("0.00")
        db.add(row)
        db.flush()
        _notify_store_retail_order_paid(db, row)
        created += 1
    return created
