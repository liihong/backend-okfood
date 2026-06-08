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

function createPendingPayAlertPromise(pendingOrderId, memberCouponId) {
  const msg = `您有未支付的开卡订单（#${pendingOrderId}），请先完成支付后再下单`
  return new Promise(function (resolveAlert) {
    showOkAlert({
      title: '待支付订单',
      content: msg,
      confirmText: '去支付',
      cancelText: '知道了',
      success: function (alertRes) {
        if (!alertRes.confirm) {
          resolveAlert(false)
          return
        }
        const finishNavigate = function () {
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
      fail: function () {
        resolveAlert(false)
      },
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

function loadPrePayProfile() {
  return request('/api/user/me', { method: 'GET', retry: 0 }).catch(function () {
    return null
  })
}

function afterMembershipCardPaySuccess(activeRenewal, paySynced) {
  markMinePageNeedsRefresh()
  if (activeRenewal) {
    uni.showToast({
      title: paySynced ? '支付成功' : '支付已提交，状态同步中',
      icon: 'success',
    })
    setTimeout(function () {
      uni.switchTab({ url: '/pages/mine/index' })
    }, 400)
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
  setTimeout(
    function () {
      uni.redirectTo({
        url: '/packageUser/pages/memberSetup/memberSetup?from=pay',
      })
    },
    paySynced ? 400 : 80
  )
}

/**
 * 购卡详情页「立即支付开卡」
 */
export function runMembershipCardDetailPay(opts) {
  const o = opts || {}
  const membershipTemplateId = Number(o.membershipTemplateId)
  const memberCouponId = o.memberCouponId
  return loadPrePayProfile().then(function (preProfile) {
    const balBefore = Math.max(0, Math.floor(Number(preProfile && preProfile.balance) || 0))
    const activeRenewal =
      balBefore > 0 &&
      preProfile &&
      typeof preProfile === 'object' &&
      !shouldOpenMemberSetup(preProfile)
    const payOpts = {
      membershipTemplateId: membershipTemplateId,
      memberCouponId: memberCouponId,
    }
    return runMembershipTemplateWechatPay(payOpts).then(function (payOut) {
      const paySynced = payOut && payOut.paySynced !== false
      afterMembershipCardPaySuccess(activeRenewal, paySynced)
    })
  })
}

export function runMembershipCardDetailPayWithPrompt(opts) {
  return runMembershipCardDetailPay(opts).catch(function (payErr) {
    const pendingOrderId = parsePendingOrderIdFromConflict(payErr)
    if (isUnpaidOrderConflict(payErr) && pendingOrderId) {
      const o = opts || {}
      return promptGoPayPendingMemberCardOrder(pendingOrderId, o.memberCouponId)
    }
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
  })
}
