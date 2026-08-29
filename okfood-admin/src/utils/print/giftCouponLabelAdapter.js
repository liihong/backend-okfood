/**
 * 礼品券厨房标签：复用配送标签机与模板字段，不改普通配送标签内容。
 * remark / meal_category / product_title 放礼品名，便于后厨辨认。
 */

function maskPhone(phone) {
  const p = String(phone || '').trim()
  if (p.length >= 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  if (p.length >= 7) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return p
}

/**
 * @param {Array<{ name?: string, phone?: string, area?: string, address_line?: string, sheet_label?: string, store_pickup?: boolean }>} rows
 * @param {string} deliveryDate
 * @param {string} storeName
 */
export function buildGiftCouponLabelItems(rows, deliveryDate, storeName) {
  const store = String(storeName || 'OK饭').trim() || 'OK饭'
  const d = String(deliveryDate || '').trim()
  const out = []
  for (const r of rows || []) {
    const phone = r.phone != null ? String(r.phone) : ''
    const gift = String(r.sheet_label || '礼品券').trim() || '礼品券'
    out.push({
      region: String(r.area || '').trim(),
      store_name: store,
      address: String(r.address_line || '').trim(),
      name: r.name != null ? String(r.name) : '',
      phone_tail: phone.length >= 4 ? phone.slice(-4) : phone,
      phone_masked: maskPhone(phone),
      plan_type: '',
      meal_category: '礼品券',
      units: 1,
      remark: gift,
      product_title: gift,
      delivery_date: d,
      route_seq: null,
      shop_order_id: '',
      sf_order_id: '',
      order_no: '',
      store_pickup: r.store_pickup === true,
      order_kind: 'delivery',
    })
  }
  return out
}
