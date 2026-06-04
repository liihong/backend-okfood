import { request } from '@/utils/api.js'

/**
 * 消费记录：套餐送达扣次 + 单次购买（会员卡）扣次。
 *
 * @param {{ page?: number, page_size?: number }} [params]
 * @returns {Promise<{ items: { delivery_date: string, meal_units?: number, deduction_kind?: string }[], total: number, total_meal_units?: number, page: number, page_size: number }>}
 */
export function listDeliveryDeductions(params = {}) {
  const page = Number(params.page) > 0 ? Math.floor(Number(params.page)) : 1
  const page_size =
    Number(params.page_size) > 0 ? Math.min(50, Math.floor(Number(params.page_size))) : 20
  return request(`/api/user/me/delivery-deductions?page=${page}&page_size=${page_size}`, {
    method: 'GET',
  })
}
