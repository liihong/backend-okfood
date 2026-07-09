/** 零售订单（单次点餐）：发货状态 Tab（与接口 fulfillment_phase 对应） */
export const SINGLE_FULFILLMENT_TABS = [
  { label: '待发货', value: 'pending_ship' },
  { label: '配送中', value: 'in_delivery' },
  { label: '已完成', value: 'delivered' },
  { label: '售后', value: 'after_sale' },
]

/** 商城订单：配送状态 Tab（与接口 fulfillment_phase 对应） */
export const RETAIL_DELIVERY_TABS = [
  { label: '待接单', value: 'awaiting_accept' },
  { label: '待发货', value: 'pending_ship' },
  { label: '配送中', value: 'in_delivery' },
  { label: '已完成', value: 'delivered' },
  { label: '退单/售后', value: 'after_sale' },
]

/** 卡包订单：支付状态 Tab */
export const MALL_PAY_TABS = [
  { label: '全部', value: 'all' },
  { label: '已支付', value: '已支付' },
  { label: '未支付', value: '未支付' },
  { label: '已取消', value: '已取消' },
]

/** 单次点餐 / 商城订单状态（与接口 fulfillment_status 对应） */
export const SINGLE_ORDER_STATUS_ZH = {
  awaiting_accept: '待接单',
  pending: '待发货',
  sf_awaiting_pickup: '待取货',
  accepted: '配送中',
  delivered: '已完成',
  sf_cancelled: '顺丰取消',
  cancelled: '已取消',
}

/** 与后端 STUB_MEMBER_NAME 一致：档案占位时展示地址收件人 */
export const MEMBER_STUB_NAME = '待完善'

/** provide/inject 键 */
export const ORDERS_MANAGE_KEY = Symbol('ordersManage')
