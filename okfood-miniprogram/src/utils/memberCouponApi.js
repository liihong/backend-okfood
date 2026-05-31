import { request } from '@/utils/api.js'

/**
 * 结算页可用优惠券
 * @param {{ biz_type: string, card_kind?: string, membership_template_id?: number, dish_id?: number, quantity?: number, retail_product_id?: number }} params
 */
export function listAvailableMemberCoupons(params) {
  const q = new URLSearchParams()
  const biz = String(params?.biz_type || '').trim()
  if (!biz) throw new Error('缺少 biz_type')
  q.set('biz_type', biz)
  if (params.membership_template_id != null) {
    q.set('membership_template_id', String(Math.floor(Number(params.membership_template_id))))
  }
  if (params.card_kind) q.set('card_kind', String(params.card_kind).trim())
  if (params.dish_id != null) q.set('dish_id', String(Math.floor(Number(params.dish_id))))
  if (params.quantity != null) q.set('quantity', String(Math.max(1, Math.floor(Number(params.quantity)))))
  if (params.retail_product_id != null) {
    q.set('retail_product_id', String(Math.floor(Number(params.retail_product_id))))
  }
  return request(`/api/user/member-coupons/available?${q.toString()}`, { method: 'GET' })
}
