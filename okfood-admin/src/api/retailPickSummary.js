import { apiJson } from '../admin/core.js'

/** @param {string} path @param {RequestInit} [init] */
function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

/**
 * 厨师看板：商城 SKU 备货汇总
 * @param {{ storeId?: number }} [opts]
 */
export async function fetchRetailPickSummary(opts = {}) {
  const storeId = Number(opts.storeId) > 0 ? Number(opts.storeId) : 1
  const q = new URLSearchParams({ store_id: String(storeId) })
  return adminJson(`/api/admin/orders/retail-orders/pick-summary?${q.toString()}`)
}