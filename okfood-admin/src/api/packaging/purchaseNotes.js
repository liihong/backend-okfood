import { apiJson } from '../../admin/core.js'

/**
 * @typedef {'ingredient' | 'consumable'} PurchaseNoteCategory
 * @typedef {'link' | 'wechat' | 'phone' | 'other'} PurchaseNoteMethod
 * @typedef {Object} PurchaseNote
 * @property {number} id
 * @property {PurchaseNoteCategory} category
 * @property {string} name
 * @property {PurchaseNoteMethod} record_method
 * @property {string} contact_value
 * @property {string} platform
 * @property {string} supplier_label
 * @property {string} remark
 */

function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

/**
 * @param {string} [query] 已带 ? 的筛选串
 * @returns {Promise<PurchaseNote[]>}
 */
export function listPurchaseNotes(query) {
  return adminJson(`/api/admin/packaging/purchase-notes${query || ''}`)
}

/** @param {Omit<PurchaseNote, 'id'>} body */
export function createPurchaseNote(body) {
  return adminJson('/api/admin/packaging/purchase-notes', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/** @param {number} id @param {Omit<PurchaseNote, 'id'>} body */
export function patchPurchaseNote(id, body) {
  return adminJson(`/api/admin/packaging/purchase-notes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

/** @param {number} id */
export function deletePurchaseNote(id) {
  return adminJson(`/api/admin/packaging/purchase-notes/${id}`, { method: 'DELETE' })
}
