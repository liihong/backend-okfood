import { request, getMemberToken, getCourierToken } from '@/utils/api.js'
import { getMemberCouponReminder } from '@/utils/memberCouponApi.js'

const STORAGE_PREFIX = 'okfood_member_coupon_reminder_shown_v1'
const MEMBER_CARD_LIST_URL = '/packageUser/pages/membershipCardList/membershipCardList'

/** @param {string|number} memberId */
function reminderStorageKey(memberId) {
  return `${STORAGE_PREFIX}:${String(memberId)}`
}

/** @param {string|number} memberId */
function hasReminderShown(memberId) {
  if (memberId == null || memberId === '') return true
  try {
    return !!uni.getStorageSync(reminderStorageKey(memberId))
  } catch {
    return false
  }
}

/** @param {string|number} memberId */
function markReminderShown(memberId) {
  if (memberId == null || memberId === '') return
  try {
    uni.setStorageSync(reminderStorageKey(memberId), '1')
  } catch {
    /* ignore */
  }
}

/** @returns {Promise<string>} */
async function resolveMemberId() {
  try {
    const cached = uni.getStorageSync('memberId') || ''
    if (cached) return String(cached)
  } catch {
    /* ignore */
  }
  const profile = await request('/api/user/me', { method: 'GET' })
  const id = profile?.id != null ? String(profile.id) : ''
  if (id) {
    try {
      uni.setStorageSync('memberId', id)
    } catch {
      /* ignore */
    }
  }
  return id
}

let reminderInFlight = false

/**
 * 进小程序后提醒用户有购卡优惠券（每会员仅弹一次；需已登录）。
 */
export async function tryShowMemberCouponReminder() {
  if (reminderInFlight) return
  if (!getMemberToken() || getCourierToken()) return

  reminderInFlight = true
  try {
    const memberId = await resolveMemberId()
    if (!memberId || hasReminderShown(memberId)) return

    const data = await getMemberCouponReminder()
    const count = Math.max(0, Math.floor(Number(data?.count) || 0))
    if (count <= 0) return

    const maxDisc = data?.max_discount_yuan != null ? String(data.max_discount_yuan).trim() : ''
    const content =
      maxDisc && maxDisc !== '0' && maxDisc !== '0.00'
        ? `您有 ${count} 张购卡优惠券可用，最高可减 ¥${maxDisc}，开卡时可自动抵扣。`
        : `您有 ${count} 张购卡优惠券可用，开卡时可自动抵扣。`

    markReminderShown(memberId)
    uni.showModal({
      title: '优惠券提醒',
      content,
      confirmText: '去购卡',
      cancelText: '知道了',
      success: (res) => {
        if (res.confirm) {
          uni.navigateTo({ url: MEMBER_CARD_LIST_URL })
        }
      },
    })
  } catch {
    /* 静默失败，不影响主流程 */
  } finally {
    reminderInFlight = false
  }
}
