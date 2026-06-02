import { request } from '@/utils/api.js'
import { showOkAlert } from '@/utils/okAlert.js'
import { runMembershipTemplateWechatPay } from '@/utils/memberCardPay.js'
import { applyMemberCardOrderCoupon } from '@/utils/memberCardOrderApi.js'
import { shouldOpenMemberSetup } from '@/utils/memberProfile.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'
import {
  isUnpaidOrderConflict,
  parsePendingOrderIdFromConflict,
} from '@/utils/unpaidOrderPrompt.js'

const MEMBER_CARD_ORDER_DETAIL_PAGE =
  '/packageOrder/pages/memberCardOrderDetail/memberCardOrderDetail'

function openMemberCardOrderDetail(orderId) {
  const id = Math.floor(Number(orderId))
  if (!Number.isFinite(id) || id < 1) return
  uni.navigateTo({
    url: `${MEMBER_CARD_ORDER_DETAIL_PAGE}?id=${encodeURIComponent(String(id))}`,
  })
}

/** 待支付开卡工单：可选换券后跳转工单详情继续支付 */
function createPendingPayAlertPromise(pendingOrderId, memberCouponId) {
  const msg = `您有未支付的开卡订单（#${pendingOrderId}），请先完成支付后再下单`
  return new Promise((resolveAlert) => {
    showOkAlert({
      title: '待支付订单',
      content: msg,
      confirmText: '去支付',
      cancelText: '知道了',
      success: (alertRes) => {
        if (!alertRes.confirm) {
          resolveAlert(false)
          return
        }
        const finishNavigate = () => {
          openMemberCardOrderDetail(pendingOrderId)
          resolveAlert(true)
        }
        if (memberCouponId == null) {
          finishNavigate()
          return
        }
        applyMemberCardOrderCoupon(pendingOrderId, memberCouponId)
          .then(finishNavigate)
          .catch(finishNavigate)
      },
      fail: () => resolveAlert(false),
    })
  })
}

export function promptGoPayPendingMemberCardOrder(orderIdRaw, memberCouponId) {
  const pendingOrderId = Math.floor(Number(orderIdRaw))
  if (!Number.isFinite(pendingOrderId) || pendingOrderId < 1) {
    return Promise.resolve(false)
  }
  return createPendingPayAlertPromise(pendingOrderId, memberCouponId)
}

async function loadPrePayProfile() {
  try {
    return await request('/api/user/me', { method: 'GET', retry: 0 })
  } catch (_profileErr) {
    return null
  }
}

/**
 * 购卡详情页「立即支付开卡」
 * @param {{ membershipTemplateId: number, memberCouponId?: number | null }} opts
 */
export async function runMembershipCardDetailPay(opts) {
  const membershipTemplateId = Number(opts.membershipTemplateId)
  const memberCouponId = opts.memberCouponId
  const preProfile = await loadPrePayProfile()
  const balBefore = Math.max(0, Math.floor(Number(preProfile?.balance) || 0))
  const activeRenewal =
    balBefore > 0 &&
    preProfile &&
    typeof preProfile === 'object' &&
    !shouldOpenMemberSetup(preProfile)

  const profileStartYmd =
    preProfile?.delivery_start_date != null
      ? String(preProfile.delivery_start_date).trim().slice(0, 10)
      : ''
  const payOut = await runMembershipTemplateWechatPay({
    membershipTemplateId,
    deliveryStartYmd: activeRenewal && profileStartYmd ? profileStartYmd : undefined,
    memberCouponId,
  })
  const paySynced = payOut?.paySynced !== false
  markMinePageNeedsRefresh()

  if (activeRenewal) {
    uni.showToast({
      title: paySynced ? '支付成功' : '支付已提交，状态同步中',
      icon: 'success',
    })
    setTimeout(() => uni.switchTab({ url: '/pages/mine/index' }), 400)
    return
  }
  if (paySynced) {
    uni.showToast({ title: '支付成功', icon: 'success' })
  } else {
    showOkAlert({
      title: '支付已提交',
      content:
        '微信已扣款，订单状态正在同步。请先完善配送信息；若后台长时间仍显示未缴，请联系客服核对。',
      showCancel: false,
    })
  }
  setTimeout(() => {
    uni.redirectTo({
      url: '/packageUser/pages/memberSetup/memberSetup?from=pay',
    })
  }, paySynced ? 400 : 80)
}

export async function runMembershipCardDetailPayWithPrompt(opts) {
  try {
    await runMembershipCardDetailPay(opts)
  } catch (payErr) {
    const pendingOrderId = parsePendingOrderIdFromConflict(payErr)
    if (isUnpaidOrderConflict(payErr) && pendingOrderId) {
      await promptGoPayPendingMemberCardOrder(pendingOrderId, opts.memberCouponId)
    } else {
      const msg =
        payErr instanceof Error
          ? payErr.message
          : typeof payErr === 'string'
            ? payErr
            : '支付未完成'
      if (msg.includes('cancel') || msg.includes('取消')) {
        uni.showToast({ title: '已取消支付', icon: 'none' })
      } else {
        uni.showToast({ title: msg, icon: 'none', duration: 2800 })
      }
    }
  }
}
