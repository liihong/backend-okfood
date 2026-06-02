/**
 * 我的优惠券 API
 */
import { request } from '@/utils/api.js'
import { buildQueryString } from '@/utils/queryString.js'

/**
 * @param {{ status?: string }} [params]
 */
export function listMemberCouponsWallet(params = {}) {
  const qs = buildQueryString(
    params.status ? { status: String(params.status) } : {},
  )
  return request(`/api/user/member-coupons/wallet${qs ? `?${qs}` : ''}`, { method: 'GET' })
}
