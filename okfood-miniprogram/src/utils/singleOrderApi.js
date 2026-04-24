import { request } from '@/utils/api.js'

/**
 * @param {Record<string, unknown>} o
 * @returns {{ line1: string, line2: string, tone: 'warn' | 'ok' | 'info' }}
 */
export function singleOrderStatusMeta(o) {
  const pay = String(o.pay_status || '')
  const fulfill = String(o.fulfillment_status || '')
  const pickup = !!o.store_pickup
  if (pay === '未支付') {
    return { line1: '待支付', line2: '请尽快完成支付', tone: 'warn' }
  }
  if (pickup) {
    return { line1: '门店自提 · 已完成', line2: '请按供餐日到店取餐', tone: 'ok' }
  }
  if (fulfill === 'delivered') {
    return { line1: '已送达', line2: '配送已完成', tone: 'ok' }
  }
  return { line1: '待送达', line2: '骑手配餐配送中', tone: 'info' }
}

/**
 * @param {{ page?: number, page_size?: number }} [params]
 * @returns {Promise<{ items: unknown[], total: number, page: number, page_size: number }>}
 */
export function listSingleMealOrders(params = {}) {
  const page = Number(params.page) > 0 ? Math.floor(Number(params.page)) : 1
  const page_size =
    Number(params.page_size) > 0 ? Math.min(50, Math.floor(Number(params.page_size))) : 20
  return request(`/api/user/single-orders?page=${page}&page_size=${page_size}`, {
    method: 'GET',
  })
}

/**
 * @param {number} orderId
 */
export function getSingleMealOrder(orderId) {
  return request(`/api/user/single-orders/${orderId}`, {
    method: 'GET',
  })
}

/**
 * @param {{
 *   dish_id: number,
 *   delivery_date: string,
 *   store_pickup?: boolean,
 *   quantity?: number,
 *   member_address_id?: number,
 * }} body delivery_date: YYYY-MM-DD；配送到家须带 member_address_id；自提勿传地址
 */
export function createSingleMealOrder(body) {
  return request('/api/user/single-orders', {
    method: 'POST',
    data: body,
  })
}

/**
 * @param {number} orderId
 * @returns {Promise<{ appId: string, timeStamp: string, nonceStr: string, package: string, signType: string, paySign: string }>}
 */
export function fetchWechatJsapiPayParams(orderId) {
  return request(`/api/user/single-orders/${orderId}/pay/wechat-jsapi`, {
    method: 'POST',
    data: {},
  })
}
