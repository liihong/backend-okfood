import { apiJson } from '../../admin/core.js'

function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

export function listPackagingSkus() {
  return adminJson('/api/admin/packaging/skus')
}

export function createPackagingSku(body) {
  return adminJson('/api/admin/packaging/skus', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function patchPackagingSku(id, body) {
  return adminJson(`/api/admin/packaging/skus/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export function deletePackagingSku(id) {
  return adminJson(`/api/admin/packaging/skus/${id}`, { method: 'DELETE' })
}

export function importDefaultPackagingSkus() {
  return adminJson('/api/admin/packaging/skus/import-defaults', { method: 'POST' })
}
