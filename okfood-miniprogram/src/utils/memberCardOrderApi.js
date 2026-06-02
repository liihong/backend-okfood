import { request } from '@/utils/api.js'

/**
 * @param {{ page?: number, page_size?: number, list_status?: string }} [params]
 */
/**
 * @param {number} orderId
 */
export function getMemberCardOrder(orderId) {
  const id = Math.floor(Number(orderId))
  if (!Number.isFinite(id) || id < 1) {
    return Promise.reject(new Error('订单编号无效'))
  }
  return request(`/api/user/member-card-orders/${id}`, {
    method: 'GET',
  })
}

export function listMemberCardOrders(params = {}) {
  const page = Number(params.page) > 0 ? Math.floor(Number(params.page)) : 1
  const page_size =
    Number(params.page_size) > 0 ? Math.min(50, Math.floor(Number(params.page_size))) : 20
  const ls = params.list_status && params.list_status !== 'all' ? String(params.list_status).trim() : ''
  const q = ls
    ? `page=${page}&page_size=${page_size}&list_status=${encodeURIComponent(ls)}`
    : `page=${page}&page_size=${page_size}`
  return request(`/api/user/member-card-orders?${q}`, {
    method: 'GET',
  })
}

/**
 * @param {{ card_kind?: string, delivery_start_date?: string, membership_template_id?: number }} body
 *   - 经典周/月卡：card_kind + delivery_start_date
 *   - 自律卡包：membership_template_id
 */
export function createMemberCardOrder(body) {
  return request('/api/user/member-card-orders', {
    method: 'POST',
    data: body,
  })
}

/**
 * @param {number} orderId
 * @param {number|null|undefined} memberCouponId 用户券 id；不传表示移除已选券
 */
export function applyMemberCardOrderCoupon(orderId, memberCouponId) {
  const data =
    memberCouponId != null ? { member_coupon_id: Math.floor(Number(memberCouponId)) } : {}
  return request(`/api/user/member-card-orders/${orderId}/apply-coupon`, {
    method: 'POST',
    data,
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
export function syncMemberCardWechatPayResult(orderId) {
  const primary = `/api/pay/wechat/member-card-order-sync/${orderId}`
  const legacy = `/api/user/member-card-orders/${orderId}/sync-wechat-pay`
  return request(primary, { method: 'POST', data: {} }).catch(function (e) {
    const st = e && e.status
    const m = (e && e.message) || ''
    if (st === 404 || m.includes('Not Found') || m.includes('404')) {
      return request(legacy, { method: 'POST', data: {} })
    }
    throw e
  })
}
