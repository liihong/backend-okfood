/** 单次点餐 / 商城：是否可推送顺丰、指派配送员等 */
export function canDispatchActions(row) {
  if (!row || row.pay_status !== '已支付') return false
  const f = String(row.fulfillment_status || '').toLowerCase()
  if (f === 'cancelled') return false
  return f === 'pending' || f === 'sf_cancelled'
}

export function isSfCancelledRedispatch(row) {
  return String(row?.fulfillment_status || '').trim().toLowerCase() === 'sf_cancelled'
}

export function canCancelOrder(row) {
  if (!row) return false
  const pay = String(row.pay_status || '').trim()
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  if (f === 'delivered' || f === 'cancelled') return false
  if (pay === '已退款') return f !== 'cancelled'
  if (pay === '未支付') return f === 'pending'
  if (pay === '已支付') return f === 'pending' || f === 'sf_awaiting_pickup' || f === 'accepted' || f === 'sf_cancelled'
  return false
}

export function canMarkOrderComplete(row) {
  if (!row || row.pay_status !== '已支付') return false
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  return f === 'pending' || f === 'sf_awaiting_pickup' || f === 'accepted'
}

export function canModifyOrder(row) {
  if (!row) return false
  const pay = String(row.pay_status || '').trim()
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  if (pay === '已退款' || f === 'cancelled' || f === 'accepted' || f === 'sf_awaiting_pickup') return false
  return f === 'pending' || f === 'sf_cancelled' || f === 'delivered'
}

export function isSingleRowSelectable(row) {
  return canDispatchActions(row) || canCancelOrder(row) || canMarkOrderComplete(row)
}

export function canRefundWechatSingle(row) {
  if (!row || row.pay_status !== '已支付') return false
  return String(row.pay_channel || '').trim() === '微信'
}

export function canRefundWechatMall(row) {
  if (!row) return false
  const ps = String(row.pay_status || '').trim()
  if (ps !== '已缴') return false
  return String(row.pay_channel || '').trim() === '微信'
}

export function canRefundWechatRetail(row) {
  if (!row || row.pay_status !== '已支付') return false
  return String(row.pay_channel || '').trim() === '微信'
}
