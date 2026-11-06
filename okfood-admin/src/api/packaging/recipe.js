import { apiJson } from '../../admin/core.js'

function adminJson(path, init) {
  return apiJson(path, init || {}, { auth: true })
}

export function listDishPackaging() {
  return adminJson('/api/admin/packaging/recipe/dishes')
}

export function saveDishPackaging(dishId, lines) {
  return adminJson(`/api/admin/packaging/recipe/dishes/${dishId}`, {
    method: 'PUT',
    body: JSON.stringify({ lines }),
  })
}

export function listStandardPackaging() {
  return adminJson('/api/admin/packaging/recipe/standard')
}

export function saveStandardPackaging(lines) {
  return adminJson('/api/admin/packaging/recipe/standard', {
    method: 'PUT',
    body: JSON.stringify({ lines }),
  })
}

export function getSlotPackaging(query) {
  const params = new URLSearchParams()
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  return adminJson(`/api/admin/packaging/recipe/slot?${params.toString()}`)
}

export function saveSlotPackaging(body) {
  return adminJson('/api/admin/packaging/recipe/slot', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export function listSlotPackagingUsage(weekStart) {
  return adminJson(`/api/admin/packaging/recipe/slot-usage?week_start=${encodeURIComponent(weekStart)}`)
}
