import { courierRequest, setCourierToken } from '@/utils/api.js'

export function fetchCourierMe() {
  return courierRequest('/api/courier/me', { method: 'GET' })
}

/**
 * @param {string} phone
 * @returns {Promise<{ access_token: string }>}
 */
export function courierLoginPhone(phone) {
  return courierRequest('/api/courier/login-phone', {
    method: 'POST',
    data: { phone },
    skipAuth: true,
  })
}

/**
 * @param {string} [dateYmd] 配送业务日 YYYY-MM-DD，默认后端上海当日
 * @returns {Promise<{ delivery_date: string, assigned_areas: string[], groups: { area: string, items: object[] }[] }>}
 */
export function fetchCourierTasks(dateYmd) {
  const q = dateYmd ? `?date=${encodeURIComponent(dateYmd)}` : ''
  return courierRequest(`/api/courier/tasks${q}`, { method: 'GET' })
}

/**
 * @param {number} memberId
 * @param {string} [dateYmd]
 */
export function confirmCourierDelivery(memberId, dateYmd) {
  const body = { member_id: memberId }
  if (dateYmd) body.date = dateYmd
  return courierRequest('/api/courier/confirm', {
    method: 'POST',
    data: body,
  })
}

/** @param {number} orderId single_meal_orders.id */
export function confirmSingleOrderDelivery(orderId) {
  return courierRequest('/api/courier/single-order/confirm', {
    method: 'POST',
    data: { order_id: orderId },
  })
}

export { setCourierToken }
