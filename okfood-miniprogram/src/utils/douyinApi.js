/**
 * 抖音验券 API（会员端）
 */
import { request } from '@/utils/api.js'

/**
 * @param {{ code: string, delivery_start_date?: string|null }} body
 */
export function redeemDouyinCertificate(body) {
  return request('/api/user/douyin-certificates/redeem', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
