import { apiJson } from '../admin/core.js'

/** @param {string} path @param {RequestInit} [init] */
function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

export function listPrepIngredients() {
  return adminJson('/api/admin/prep-menu/ingredients')
}

/** @param {{ name: string, unit: 'g' | 'piece', yield_rate: string }} body */
export function createPrepIngredient(body) {
  return adminJson('/api/admin/prep-menu/ingredients', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** @param {number} id @param {Record<string, string>} body */
export function patchPrepIngredient(id, body) {
  return adminJson(`/api/admin/prep-menu/ingredients/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** @param {number} id */
export function deletePrepIngredient(id) {
  return adminJson(`/api/admin/prep-menu/ingredients/${id}`, { method: 'DELETE' })
}

/** @param {number} dishId */
export function getDishPrepSop(dishId) {
  return adminJson(`/api/admin/prep-menu/sops/${dishId}`)
}

/**
 * @param {number} dishId
 * @param {{ ingredient_id: number, gross_qty_per_portion: string }[]} lines
 */
export function saveDishPrepSop(dishId, lines) {
  return adminJson(`/api/admin/prep-menu/sops/${dishId}`, {
    method: 'PUT',
    body: JSON.stringify({ lines }),
  })
}

/**
 * @param {{
 *   week_start: string,
 *   portion_overrides: { meal_period: string, slot: number, portions: number | null }[],
 * }} body
 */
export function estimatePrepMenu(body) {
  return adminJson('/api/admin/prep-menu/estimate', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** 出成率小数转百分比文案。按个计或空值显示横线。 */
export function formatYield(rate, unit) {
  if (unit === 'piece' || rate == null || rate === '') return '—'
  const percent = Math.round(Number(rate) * 10000) / 100
  if (!Number.isFinite(percent)) return '—'
  return `${percent}%`
}

/** 百分比（如 70）转给出成率字符串（0.7000）。非法返回 null。 */
export function percentToYieldRate(percent) {
  const value = Number(percent)
  if (!Number.isFinite(value) || value <= 0 || value > 100) return null
  return (Math.round(value * 100) / 10000).toFixed(4)
}

/** 出成率字符串转百分比数字，供输入框回填。 */
export function yieldRateToPercent(rate) {
  const value = Number(rate)
  if (!Number.isFinite(value)) return 100
  return Math.round(value * 10000) / 100
}

/** @param {string | null | undefined} qty @param {string | undefined} unit */
export function formatPerPortion(qty, unit) {
  if (qty == null || qty === '') return '—'
  return unit === 'piece' ? `${qty} 个` : `${qty} 克`
}

/** @param {{ unit?: string, gross_jin?: string | null, gross_count?: string | null }} row */
export function formatGrossAmount(row) {
  if (row.unit === 'piece') return row.gross_count ? `${row.gross_count} 个` : '—'
  return row.gross_jin ? `${row.gross_jin} 斤` : '—'
}

/** @param {{ unit?: string, net_jin?: string | null }} row */
export function formatNetAmount(row) {
  if (row.unit === 'piece') return '—'
  return row.net_jin ? `${row.net_jin} 斤` : '—'
}
