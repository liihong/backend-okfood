/** 商城零售订单 → LabelItem[] */

function phoneTail(phone) {
  const p = String(phone || '').trim()
  return p.length >= 4 ? p.slice(-4) : p
}

export function retailOrderToLabelItem(row) {
  const pickup = row.store_pickup === true
  return {
    region: row.routing_area || '',
    address: row.address_summary || '',
    name: row.recipient_contact_name || row.member_name || '',
    phone_tail: phoneTail(row.member_phone),
    units: Number(row.quantity) || 1,
    remark: row.remark || row.address_remarks || '',
    delivery_date: row.fulfillment_date || '',
    route_seq: null,
    product_title: row.product_title || '',
    order_no: String(row.id || ''),
    store_pickup: pickup,
  }
}

export function buildRetailLabelItems(rows) {
  return (rows || []).map(retailOrderToLabelItem)
}
