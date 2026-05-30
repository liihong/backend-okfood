import { request } from '@/utils/api.js'
import { parseApiDateTimeBeijing } from '@/utils/beijingDateTime.js'

/**
 * 订单 created_at：库内北京时间 naive；`Z` 结尾兼容旧 UTC 响应。按 Asia/Shanghai 展示。
 * @param {unknown} iso
 * @returns {string}
 */
export function formatSingleOrderCreatedAt(iso) {
  if (iso == null || iso === '') return '—'
  const d = parseApiDateTimeBeijing(iso)
  if (Number.isNaN(d.getTime())) {
    return String(iso).replace('T', ' ').replace(/\.\d+Z?$/, '').slice(0, 19)
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const g = (t) => parts.find((p) => p.type === t)?.value ?? ''
  return `${g('year')}-${g('month')}-${g('day')} ${g('hour')}:${g('minute')}:${g('second')}`
}

/**
 * @param {Record<string, unknown>} o
 * @returns {{ line1: string, line2: string, tone: 'warn' | 'ok' | 'info' }}
 */
/**
 * @param {Record<string, unknown>} o
 * @returns {boolean}
 */
export function canCancelSingleMealOrder(o) {
  if (!o || typeof o !== 'object') return false
  const pay = String(o.pay_status || '').trim()
  const f = String(o.fulfillment_status || '').trim().toLowerCase()
  if (pay === '已退款' || f === 'delivered' || f === 'cancelled') return false
  if (pay === '未支付') return f === 'pending'
  if (pay === '已支付') return f === 'pending' || f === 'sf_awaiting_pickup' || f === 'accepted' || f === 'sf_cancelled'
  return false
}

export function singleOrderStatusMeta(o) {
  const pay = String(o.pay_status || '')
  const fulfill = String(o.fulfillment_status || '')
  const pickup = !!o.store_pickup
  if (fulfill === 'cancelled') {
    if (pay === '未支付') {
      return { line1: '已关闭', line2: '超时未支付，订单已自动取消', tone: 'warn' }
    }
    return { line1: '已取消', line2: '订单已取消，款项未自动退款', tone: 'warn' }
  }
  if (pay === '未支付') {
    return { line1: '待支付', line2: '请尽快完成支付', tone: 'warn' }
  }
  if (pickup) {
    if (fulfill === 'delivered') {
      return { line1: '门店自提 · 已完成', line2: '感谢您的光临', tone: 'ok' }
    }
    if (fulfill === 'sf_cancelled') {
      return { line1: '顺丰取消', line2: '如有疑问请联系客服', tone: 'warn' }
    }
    return { line1: '待取货', line2: '请按供餐日到店自提', tone: 'info' }
  }
  if (fulfill === 'delivered') {
    return { line1: '已送达', line2: '配送已完成', tone: 'ok' }
  }
  if (fulfill === 'sf_cancelled') {
    return { line1: '顺丰取消', line2: '配送已取消，如有疑问请联系客服', tone: 'warn' }
  }
  if (fulfill === 'sf_awaiting_pickup') {
    return { line1: '待取货', line2: '已推顺丰，等待配送员取货', tone: 'info' }
  }
  if (fulfill === 'accepted') {
    return { line1: '配送中', line2: '骑手正在配送', tone: 'info' }
  }
  return { line1: '待发货', line2: '等待商家安排配送', tone: 'info' }
}

/**
 * @param {{ page?: number, page_size?: number, list_status?: string }} [params]
 *   list_status: all（省略）| pending_pay | pending_delivery | completed
 * @returns {Promise<{ items: unknown[], total: number, page: number, page_size: number }>}
 */
export function listSingleMealOrders(params = {}) {
  const page = Number(params.page) > 0 ? Math.floor(Number(params.page)) : 1
  const page_size =
    Number(params.page_size) > 0 ? Math.min(50, Math.floor(Number(params.page_size))) : 20
  const ls = params.list_status && params.list_status !== 'all' ? String(params.list_status).trim() : ''
  const q = ls
    ? `page=${page}&page_size=${page_size}&list_status=${encodeURIComponent(ls)}`
    : `page=${page}&page_size=${page_size}`
  return request(`/api/user/single-orders?${q}`, {
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

/**
 * @param {number} orderId
 */
export function cancelSingleMealOrder(orderId) {
  return request(`/api/user/single-orders/${orderId}/cancel`, {
    method: 'POST',
    data: {},
  })
}
