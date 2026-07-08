import { request } from '@/utils/api.js'
import { parseApiDateTimeBeijing } from '@/utils/beijingDateTime.js'
import { buildQueryString } from '@/utils/queryString.js'

/**
 * @param {{ page?: number, page_size?: number, list_status?: string }} params
 */
export async function listRetailOrders(params = {}) {
  const qs = buildQueryString({
    page: params.page != null ? params.page : undefined,
    page_size: params.page_size != null ? params.page_size : undefined,
    list_status: params.list_status || undefined,
  })
  const suffix = qs ? `?${qs}` : ''
  const raw = await request(`/api/user/retail-orders${suffix}`, { method: 'GET', retry: 1 })
  return raw && typeof raw === 'object' ? raw : { items: [], total: 0 }
}

/** @param {number} orderId */
export async function getRetailOrder(orderId) {
  const id = Math.floor(Number(orderId))
  return request(`/api/user/retail-orders/${encodeURIComponent(String(id))}`, {
    method: 'GET',
    retry: 1,
  })
}

/** @param {Record<string, unknown>} payload */
export async function createRetailOrder(payload) {
  return request('/api/user/retail-orders', {
    method: 'POST',
    data: payload,
    retry: 0,
  })
}

/** @param {number} orderId */
export async function fetchRetailWechatPayParams(orderId) {
  const id = Math.floor(Number(orderId))
  return request(`/api/user/retail-orders/${encodeURIComponent(String(id))}/pay/wechat-jsapi`, {
    method: 'POST',
    retry: 0,
  })
}

/** @param {number} orderId */
export async function syncRetailWechatPayResult(orderId) {
  const id = Math.floor(Number(orderId))
  return request(`/api/user/retail-orders/${encodeURIComponent(String(id))}/sync-wechat-pay`, {
    method: 'POST',
    retry: 0,
  })
}

/** @param {number} orderId */
export async function cancelRetailOrder(orderId) {
  const id = Math.floor(Number(orderId))
  return request(`/api/user/retail-orders/${encodeURIComponent(String(id))}/cancel`, {
    method: 'POST',
    retry: 0,
  })
}

/** @param {unknown} iso */
export function formatRetailOrderCreatedAt(iso) {
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

/** @param {Record<string, unknown>} o */
export function retailOrderStatusMeta(o) {
  const pay = String(o.pay_status || '')
  const fulfill = String(o.fulfillment_status || '')
  const pickup = !!o.store_pickup
  if (fulfill === 'cancelled') {
    if (pay === '未支付') {
      return { line1: '已关闭', line2: '超时未支付，订单已自动取消', tone: 'warn' }
    }
    if (pay === '已退款') {
      return { line1: '已取消', line2: '订单已取消，款项已原路退回', tone: 'warn' }
    }
    return { line1: '已取消', line2: '订单已取消', tone: 'warn' }
  }
  if (pay === '未支付') {
    return { line1: '待支付', line2: '请尽快完成支付', tone: 'warn' }
  }
  if (pickup) {
    if (fulfill === 'delivered') {
      return { line1: '门店自提 · 已完成', line2: '感谢您的光临', tone: 'ok' }
    }
    if (fulfill === 'awaiting_accept') {
      return { line1: '门店自提 · 待接单', line2: '商家确认中', tone: 'info' }
    }
    return { line1: '门店自提 · 待取货', line2: '请到店出示订单', tone: 'info' }
  }
  if (fulfill === 'delivered') {
    return { line1: '已完成', line2: '商品已送达', tone: 'ok' }
  }
  if (fulfill === 'accepted' || fulfill === 'sf_awaiting_pickup') {
    return { line1: '配送中', line2: '请留意配送通知', tone: 'info' }
  }
  if (fulfill === 'awaiting_accept') {
    return { line1: '待接单', line2: '商家确认中', tone: 'info' }
  }
  if (fulfill === 'pending') {
    return { line1: '待发货', line2: '商家备货中', tone: 'info' }
  }
  return { line1: pay || '—', line2: '', tone: 'info' }
}

/** @param {Record<string, unknown>} o */
export function canCancelRetailOrder(o) {
  if (!o || typeof o !== 'object') return false
  const pay = String(o.pay_status || '').trim()
  const f = String(o.fulfillment_status || '').trim().toLowerCase()
  if (pay === '已退款' || f === 'delivered' || f === 'cancelled') return false
  if (pay === '未支付') return f === 'pending'
  if (pay !== '已支付') return false
  if (o.store_pickup) return f === 'awaiting_accept'
  return f === 'awaiting_accept' || f === 'pending'
}
