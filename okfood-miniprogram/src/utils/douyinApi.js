/**
 * 抖音验券 API（会员端）
 */
import { request } from '@/utils/api.js'

/**
 * 起送日不在验券页设置，核销后于「我的」完善配送或购卡/用券兑换时选择。
 * @param {{ code: string }} body
 */
export function redeemDouyinCertificate(body) {
  return request('/api/user/douyin-certificates/redeem', {
    method: 'POST',
    data: body,
  })
}
