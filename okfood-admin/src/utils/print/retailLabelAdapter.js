/** 零售 / 商城订单 → 备餐面单 LabelItem（与配送标签同款 layout） */

function phoneTail(phone) {
  const p = String(phone || '').trim()
  return p.length >= 4 ? p.slice(-4) : p
}

function maskPhone(phone) {
  const p = String(phone || '').trim()
  if (p.length >= 11) return `${p.slice(0, 3)}****${p.slice(-4)}`
  if (p.length >= 7) return `${p.slice(0, 3)}****${p.slice(-4)}`
  return p
}

/**
 * @param {Record<string, unknown>} row
 * @param {{ storeName?: string }} [opts]
 */
export function mallOrderToLabelItem(row, opts = {}) {
  const store = String(opts.storeName || 'OK饭').trim() || 'OK饭'
  const phone = row.member_phone != null ? String(row.member_phone) : ''
  const items = Array.isArray(row.items) ? row.items : []
  let productTitle = row.product_title || ''
  let units = Number(row.quantity) || 1
  if (items.length) {
    productTitle = items
      .map((it) => {
        const t = String(it.product_title || '').trim() || '商品'
        const q = Math.max(1, Number(it.quantity) || 1)
        return q > 1 ? `${t} ×${q}` : t
      })
      .join('\n')
    units = items.reduce((sum, it) => sum + Math.max(1, Number(it.quantity) || 1), 0)
  }
  return {
    region: row.routing_area || '',
    store_name: store,
    address: row.address_summary || '',
    name: row.recipient_contact_name || row.member_name || '',
    phone_tail: phoneTail(phone),
    phone_masked: maskPhone(phone),
    units,
    remark: row.remark || row.address_remarks || '',
    delivery_date: row.fulfillment_date || '',
    route_seq: null,
    product_title: productTitle,
    order_no: String(row.out_trade_no || '').trim() || (row.id != null ? `OKF${row.id}` : ''),
    shop_order_id: '',
    sf_order_id: row.sf_order_id != null ? String(row.sf_order_id) : '',
    store_pickup: row.store_pickup === true,
    order_kind: 'mall',
  }
}

/** @deprecated 使用 mallOrderToLabelItem */
export function retailOrderToLabelItem(row, opts = {}) {
  return mallOrderToLabelItem(row, opts)
}

/**
 * 零售单次订单（single_meal_orders）
 * @param {Record<string, unknown>} row
 * @param {{ storeName?: string }} [opts]
 */
export function singleMealOrderToLabelItem(row, opts = {}) {
  const store = String(opts.storeName || 'OK饭').trim() || 'OK饭'
  const phone = row.member_phone != null ? String(row.member_phone) : ''
  return {
    region: row.routing_area || '',
    store_name: store,
    address: row.address_summary || '',
    name: row.recipient_contact_name || row.member_name || '',
    phone_tail: phoneTail(phone),
    phone_masked: maskPhone(phone),
    units: Number(row.quantity) || 1,
    remark: row.address_remarks || '',
    delivery_date: row.delivery_date || '',
    route_seq: null,
    product_title: row.dish_title || '',
    order_no: String(row.out_trade_no || '').trim() || (row.id != null ? `OKF${row.id}` : ''),
    shop_order_id: '',
    sf_order_id: row.sf_order_id != null ? String(row.sf_order_id) : '',
    store_pickup: row.store_pickup === true,
    order_kind: 'retail',
  }
}

export function buildRetailLabelItems(rows, opts = {}) {
  return (rows || []).map((row) => mallOrderToLabelItem(row, opts))
}
