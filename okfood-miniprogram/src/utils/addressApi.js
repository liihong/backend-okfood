/**
 * 统一解析地址列表（兼容：纯数组、{ data:[] } 整包）
 * @param {unknown} input
 */
export function normalizeAddressList(input) {
  if (input == null) return []
  let data = input
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch {
      return []
    }
  }
  if (Array.isArray(data)) return data
  if (typeof data !== 'object') return []
  if (Array.isArray(data.data)) return data.data
  if (Array.isArray(data.items)) return data.items
  if (data.data != null && typeof data.data === 'object' && !Array.isArray(data.data)) {
    const nested = normalizeAddressList(data.data)
    if (nested.length) return nested
  }
  return []
}

/** @param {Record<string, unknown>} item */
export function getAddressRecordId(item) {
  if (!item || typeof item !== 'object') return ''
  const id = item.id
  return id != null ? String(id) : ''
}

/** @param {unknown} v */
function addressTextPart(v) {
  if (v == null) return ''
  if (typeof v === 'string') return v.trim()
  if (typeof v === 'number' && Number.isFinite(v)) return String(v)
  return String(v).trim()
}

/**
 * 列表/缓存：优先 map_location_text + door_detail（与后端 full_address 同语义），与接口常见的 camelCase 别名一致；缺省时用 full_address。
 * @param {Record<string, unknown>} item
 */
export function addressLineFromStructured(item) {
  if (!item || typeof item !== 'object') return ''
  const map = addressTextPart(
    item.map_location_text ?? item.mapLocationText,
  )
  const door = addressTextPart(item.door_detail ?? item.doorDetail)
  const joined = [map, door].filter(Boolean).join(' ').trim()
  if (joined) return joined
  return addressTextPart(item.full_address ?? item.fullAddress)
}

/** 是否默认地址（仅看接口字段） */
export function isAddressItemDefault(item) {
  if (!item || typeof item !== 'object') return false
  return (
    item.is_default === true ||
    item.is_default === 1 ||
    item.isDefault === true ||
    item.isDefault === 1
  )
}

/** 默认地址排在最前，其余保持原有顺序 */
export function sortAddressesDefaultFirst(items) {
  if (!Array.isArray(items)) return []
  return [...items].sort((a, b) => {
    const da = isAddressItemDefault(a) ? 1 : 0
    const db = isAddressItemDefault(b) ? 1 : 0
    return db - da
  })
}

/**
 * 列表展示用
 * @param {Record<string, unknown>} item
 * @param {number} index
 */
export function addressListRow(item, index) {
  const id = getAddressRecordId(item)
  const name = addressTextPart(item.contact_name ?? item.contactName)
  const phone = addressTextPart(item.contact_phone ?? item.contactPhone)
  const line = addressLineFromStructured(item)
  const isDefault = isAddressItemDefault(item)
  return { id, name, phone, line, isDefault }
}
