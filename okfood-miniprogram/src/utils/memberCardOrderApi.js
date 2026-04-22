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

/**
 * 支付 `success` 后主动拉单同步入账（与微信异步通知二选一或互补）。
 * 主路径在 `/api/pay/wechat/...`；仅当 404 时回退旧路径（兼容只部署了会员路由的旧服务）。
 * @param {number} orderId
 * @returns {Promise<object>} 与 GET /api/user/me 同结构（见 `request` 解包后的 `data`）
 */
export async function syncMemberCardWechatPayResult(orderId) {
  const primary = `/api/pay/wechat/member-card-order-sync/${orderId}`
  const legacy = `/api/user/member-card-orders/${orderId}/sync-wechat-pay`
  try {
    return await request(primary, { method: 'POST', data: {} })
  } catch (e) {
    const st = e && e.status
    const m = (e && e.message) || ''
    if (st === 404 || m.includes('Not Found') || m.includes('404')) {
      return request(legacy, { method: 'POST', data: {} })
    }
    throw e
  }
}
