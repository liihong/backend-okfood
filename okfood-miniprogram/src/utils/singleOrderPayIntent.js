/** 待支付单点订单的支付方式意向（创建后、入账前 pay_channel 仍为空） */

const STORAGE_PREFIX = 'okfood_single_order_pay_intent_'

/**
 * @param {number} orderId
 * @param {'wechat' | 'balance'} method
 */
export function setSingleOrderPayIntent(orderId, method) {
  const id = Math.floor(Number(orderId))
  if (!Number.isFinite(id) || id < 1) return
  try {
    if (method === 'balance') {
      uni.setStorageSync(`${STORAGE_PREFIX}${id}`, 'balance')
    } else {
      uni.removeStorageSync(`${STORAGE_PREFIX}${id}`)
    }
  } catch {
    /* ignore */
  }
}

/**
 * @param {number} orderId
 * @param {string} [queryPayMethod] 路由参数 pay_method
 * @returns {'wechat' | 'balance'}
 */
export function getSingleOrderPayIntent(orderId, queryPayMethod) {
  const q = String(queryPayMethod || '').trim().toLowerCase()
  if (q === 'balance') return 'balance'
  const id = Math.floor(Number(orderId))
  if (!Number.isFinite(id) || id < 1) return 'wechat'
  try {
    return uni.getStorageSync(`${STORAGE_PREFIX}${id}`) === 'balance' ? 'balance' : 'wechat'
  } catch {
    return 'wechat'
  }
}

/** @param {number} orderId */
export function clearSingleOrderPayIntent(orderId) {
  setSingleOrderPayIntent(orderId, 'wechat')
}

/** @param {Record<string, unknown> | null | undefined} order */
export function isMemberCardSingleMealOrder(order) {
  if (!order || typeof order !== 'object') return false
  return String(order.pay_channel || '').trim() === '会员卡'
}

/**
 * 订单列表右上角金额/支付方式文案
 * @param {Record<string, unknown> | null | undefined} row
 */
export function singleMealOrderAmountLabel(row) {
  if (!row || typeof row !== 'object') return '¥ 0.00'
  if (isMemberCardSingleMealOrder(row)) return '会员卡支付'
  const ps = String(row.pay_status || '').trim()
  if (ps === '未支付' && getSingleOrderPayIntent(row.id) === 'balance') {
    return '会员卡支付'
  }
  const amt = row.amount_yuan
  return `¥ ${amt != null && amt !== '' ? amt : '0.00'}`
}
