import { request } from '@/utils/api.js'

/**
 * @param {{ dish_id: number, member_address_id: number, delivery_date: string }} body delivery_date: YYYY-MM-DD
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
