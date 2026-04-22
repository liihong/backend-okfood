import { request } from '@/utils/api.js'

/**
 * @param {{ card_kind: string, delivery_start_date: string }} body card_kind: 周卡 | 月卡；delivery_start_date: YYYY-MM-DD
 */
export function createMemberCardOrder(body) {
  return request('/api/user/member-card-orders', {
    method: 'POST',
    data: body,
  })
}

/**
 * @param {number} orderId
 * @returns {Promise<{ appId: string, timeStamp: string, nonceStr: string, package: string, signType: string, paySign: string }>}
 */
export function fetchMemberCardWechatJsapiPayParams(orderId) {
  return request(`/api/user/member-card-orders/${orderId}/pay/wechat-jsapi`, {
    method: 'POST',
    data: {},
  })
}
