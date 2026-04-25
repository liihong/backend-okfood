/**
 * 统一解析地址列表（兼容：纯数组、{ data:[] } 整包、items/list/addresses 等）
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
  if (Array.isArray(data.list)) return data.list
  if (Array.isArray(data.addresses)) return data.addresses
  if (Array.isArray(data.records)) return data.records
  if (Array.isArray(data.result)) return data.result
  if (data.data != null && typeof data.data === 'object' && !Array.isArray(data.data)) {
    const nested = normalizeAddressList(data.data)
    if (nested.length) return nested
  }
  return []
}

/** @param {Record<string, unknown>} item */
export function getAddressRecordId(item) {
  if (!item || typeof item !== 'object') return ''
  const id = item.id ?? item.address_id ?? item.addressId
  return id != null ? String(id) : ''
}

/** 是否默认地址（仅看接口字段，不用列表序号猜测） */
export function isAddressItemDefault(item) {
  if (!item || typeof item !== 'object') return false
  return (
    item.is_default === true ||
    item.is_default === 1 ||
    item.default === true ||
    item.default === 1 ||
    (typeof item.isDefault === 'boolean' && item.isDefault)
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
  const name =
    (typeof item.contact_name === 'string' && item.contact_name) ||
    (typeof item.name === 'string' && item.name) ||
    (typeof item.recipient_name === 'string' && item.recipient_name) ||
    ''
  const phone =
    (typeof item.contact_phone === 'string' && item.contact_phone) ||
    (typeof item.phone === 'string' && item.phone) ||
    ''
  const addr =
    (typeof item.detail_address === 'string' && item.detail_address) ||
    (typeof item.address === 'string' && item.address) ||
    ''
  // 用户端不展示所属片区，仅展示详细地址；片区仍由接口返回供后台/路由使用
  const line = addr.trim()
  const isDefault = isAddressItemDefault(item)
  return { id, name, phone, line, isDefault }
}
