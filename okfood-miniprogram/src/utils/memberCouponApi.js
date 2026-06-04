import { request } from '@/utils/api.js'
import { buildQueryString } from '@/utils/queryString.js'

/**
 * 结算页可用优惠券
 * @param {{ biz_type: string, card_kind?: string, membership_template_id?: number, dish_id?: number, quantity?: number, retail_product_id?: number, store_pickup?: boolean }} params
 */
export function listAvailableMemberCoupons(params) {
  const biz = String(params?.biz_type || '').trim()
  if (!biz) throw new Error('缺少 biz_type')
  /** @type {Record<string, string>} */
  const query = { biz_type: biz }
  if (params.membership_template_id != null) {
    query.membership_template_id = String(Math.floor(Number(params.membership_template_id)))
  }
  if (params.card_kind) query.card_kind = String(params.card_kind).trim()
  if (params.dish_id != null) query.dish_id = String(Math.floor(Number(params.dish_id)))
  if (params.quantity != null) {
    query.quantity = String(Math.max(1, Math.floor(Number(params.quantity))))
  }
  if (params.retail_product_id != null) {
    query.retail_product_id = String(Math.floor(Number(params.retail_product_id)))
  }
  if (params.store_pickup === true) {
    query.store_pickup = 'true'
  }
  return request(`/api/user/member-coupons/available?${buildQueryString(query)}`, { method: 'GET' })
}

/** 进小程序购卡提醒：购卡线可用券汇总 */
export function getMemberCouponReminder() {
  return request('/api/user/member-coupons/reminder', { method: 'GET' })
}
