import { MEMBER_STUB_NAME, SINGLE_ORDER_STATUS_ZH } from '../constants.js'

/** 列表/弹窗会员名：优先 API 的 member_name / recipient_contact_name */
export function resolveSingleOrderMemberDisplayName(row, addrDraft) {
  if (!row) return '—'
  const profile = String(row.member_name || '').trim()
  if (profile && profile !== MEMBER_STUB_NAME) return profile
  const recipient = String(row.recipient_contact_name || '').trim()
  if (recipient) return recipient
  const contact = String(addrDraft?.contact_name || '').trim()
  if (contact) return contact
  return profile || '—'
}

/** 门店自提且未核销完成前：pending 展示为待自提 */
export function singleOrderStatusLabelZh(row) {
  if (!row) return '—'
  const s = row.fulfillment_status
  if (s == null || s === '') return '—'
  const k = String(s).trim().toLowerCase()
  if (k === 'pending' && row.store_pickup) return '待自提'
  return SINGLE_ORDER_STATUS_ZH[k] ?? String(s).trim()
}

export function singlePayClass(s) {
  if (s === '已支付') return 'member-pill member-pill--emerald'
  if (s === '已退款') return 'member-pill member-pill--rose'
  return 'member-pill member-pill--amber'
}

export function mallPayClass(s) {
  if (s === '已缴') return 'member-pill member-pill--emerald'
  if (s === '已退款') return 'member-pill member-pill--rose'
  if (s === '已取消') return 'member-pill member-pill--rose'
  return 'member-pill member-pill--amber'
}

export function mallSyncClass(row) {
  return row?.applied_to_member ? 'member-pill member-pill--emerald' : 'member-pill member-pill--slate'
}

export function singleOrderStatusClass(row) {
  const x = ((row && row.fulfillment_status) || '').toLowerCase()
  if (x === 'delivered') return 'member-pill member-pill--emerald'
  if (x === 'sf_cancelled' || x === 'cancelled') return 'member-pill member-pill--rose'
  if (x === 'accepted') return 'member-pill member-pill--sky'
  if (x === 'sf_awaiting_pickup') return 'member-pill member-pill--amber'
  if (x === 'pending') return 'member-pill member-pill--amber'
  return 'member-pill member-pill--slate'
}

export function mallPayFilterApiValue(tabValue) {
  const v = String(tabValue ?? '').trim()
  if (v === '已支付') return '已缴'
  if (v === '未支付') return '未缴'
  if (v === '已取消') return '已退款'
  return v
}
