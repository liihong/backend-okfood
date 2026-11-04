import { apiJson } from '../../admin/core.js'

function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

export function listPackagingStocks() {
  return adminJson('/api/admin/packaging/stocks')
}

export function listPackagingAlerts() {
  return adminJson('/api/admin/packaging/alerts')
}

export function purchasePackaging(body) {
  return adminJson('/api/admin/packaging/purchase', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function stocktakePackaging(body) {
  return adminJson('/api/admin/packaging/stocktake', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function listPackagingTxns(query) {
  const params = new URLSearchParams()
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  const qs = params.toString()
  return adminJson(`/api/admin/packaging/txns${qs ? `?${qs}` : ''}`)
}
