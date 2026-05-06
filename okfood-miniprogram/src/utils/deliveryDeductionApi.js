import { request } from '@/utils/api.js'

/**
 * 套餐配送：已送达并扣次的业务日列表。
 *
 * @param {{ page?: number, page_size?: number }} [params]
 * @returns {Promise<{ items: { delivery_date: string }[], total: number, page: number, page_size: number }>}
 */
export function listDeliveryDeductions(params = {}) {
  const page = Number(params.page) > 0 ? Math.floor(Number(params.page)) : 1
  const page_size =
    Number(params.page_size) > 0 ? Math.min(50, Math.floor(Number(params.page_size))) : 20
  return request(`/api/user/me/delivery-deductions?page=${page}&page_size=${page_size}`, {
    method: 'GET',
  })
}
