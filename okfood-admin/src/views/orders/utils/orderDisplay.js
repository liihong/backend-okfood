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
  const pay = String(row.pay_status || '').trim()
  const s = row.fulfillment_status
  if (s == null || s === '') return '—'
  const k = String(s).trim().toLowerCase()
  if (k === 'awaiting_accept') return '待接单'
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
  if (x === 'pending' || x === 'awaiting_accept') return 'member-pill member-pill--amber'
  return 'member-pill member-pill--slate'
}

export function mallPayFilterApiValue(tabValue) {
  const v = String(tabValue ?? '').trim()
  if (v === '已支付') return '已缴'
  if (v === '未支付') return '未缴'
  if (v === '已取消') return '已退款'
  return v
}

/**
 * 从商城商品标题识别果蔬汁套餐天数，用于列表快速区分 1 日 / 3 日。
 * @returns {{ days: 1 | 3, badge: string, className: string } | null}
 */
export function retailJuiceDurationBadge(title) {
  const t = String(title || '').trim()
  if (!t) return null
  if (t.includes('3日') || t.includes('液断')) {
    return { days: 3, badge: '3日液断', className: 'retail-juice-duration-badge--3' }
  }
  if (t.includes('1日') || t.includes('体验')) {
    return { days: 1, badge: '1日体验', className: 'retail-juice-duration-badge--1' }
  }
  return null
}
