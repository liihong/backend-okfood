import { request } from '@/utils/api.js'

/**
 * 商城结算试算（商品 + 配送费 + 券后应付）
 * @param {object} body 与创建订单相同
 */
export async function quoteRetailOrder(body) {
  return request('/api/user/retail-orders/quote', {
    method: 'POST',
    body,
    retry: 0,
  })
}