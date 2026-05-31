import { request } from '@/utils/api.js'
import {
  applyMemberCardOrderCoupon,
  createMemberCardOrder,
  fetchMemberCardWechatJsapiPayParams,
  syncMemberCardWechatPayResult,
} from '@/utils/memberCardOrderApi.js'
import {
  confirmContinueExistingMallOrderPay,
  isUnpaidOrderConflict,
} from '@/utils/unpaidOrderPrompt.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

async function resolveMemberCardOrderId(createBody) {
  try {
    const order = await createMemberCardOrder(createBody)
    const orderId = order && typeof order === 'object' ? order.id : null
    if (orderId == null) {
      throw new Error('开卡订单创建异常')
    }
    return { order, orderId }
  } catch (e) {
    const existingId = await confirmContinueExistingMallOrderPay(e)
    if (existingId) {
      let order = { id: existingId }
      if (createBody.member_coupon_id != null) {
        order = await applyMemberCardOrderCoupon(
          existingId,
          createBody.member_coupon_id,
        )
      }
      return { order, orderId: existingId }
    }
    if (isUnpaidOrderConflict(e)) {
      throw new Error(
        e instanceof Error ? e.message : '您有待支付的开卡订单，请先完成支付',
      )
    }
    throw e
  }
}

/** 微信扣款成功后拉单同步；返回是否已在服务端记为已缴 */
async function runWechatPayForMemberCardOrder(orderId) {
  const pay = await fetchMemberCardWechatJsapiPayParams(orderId)
  await new Promise((resolve, reject) => {
    uni.requestPayment({
      provider: 'wxpay',
      timeStamp: String(pay.timeStamp),
      nonceStr: pay.nonceStr,
      package: pay.package,
      signType: pay.signType || 'MD5',
      paySign: pay.paySign,
      success: resolve,
      fail: reject,
    })
  })
  const retryDelaysMs = [800, 1200, 1500, 2000, 2500, 3000, 3500, 4000]
  const maxTries = retryDelaysMs.length + 1
  let lastErr = null
  for (let i = 0; i < maxTries; i++) {
    try {
      await syncMemberCardWechatPayResult(orderId)
      return { wechatPaid: true, paySynced: true }
    } catch (e) {
      lastErr = e
      const m = (e && e.message) || ''
      const maybeWait =
        m.includes('处理中') ||
        m.includes('稍候') ||
        m.includes('稍后再试') ||
        m.includes('未支付') ||
        m.includes('not_paid') ||
        /PAY_USERPAYING/i.test(m)
      if (maybeWait && i < maxTries - 1) {
        await new Promise((r) => setTimeout(r, retryDelaysMs[i] ?? 2000))
        continue
      }
      if (maybeWait) {
        return { wechatPaid: true, paySynced: false }
      }
      throw e
    }
  }
  if (lastErr) throw lastErr
  return { wechatPaid: true, paySynced: false }
}

/**
 * 创建开卡工单并调起微信支付（资料页「保存并支付」与个人中心「再次支付」共用）。
 * @param {{ cardKind: string, deliveryStartYmd: string, patchProfile?: boolean }} opts
 * `patchProfile`: 为 true 时先 PATCH plan_type + delivery_start_date（个人中心快捷支付用）
 */
export async function runMemberCardWechatPay({
  cardKind,
  deliveryStartYmd,
  patchProfile = false,
  memberCouponId = null,
}) {
  const d0 = String(deliveryStartYmd || '').trim().slice(0, 10)
  if (!d0) {
    throw new Error('缺少开始配送日期')
  }
  const kind = String(cardKind || '').trim()
  if (kind !== '周卡' && kind !== '月卡') {
    throw new Error('请选择周卡或月卡')
  }
  if (patchProfile) {
    await request('/api/user/profile', {
      method: 'PATCH',
      data: { plan_type: kind, delivery_start_date: d0 },
    })
  }
  await syncWxMiniOpenidFromLogin()
  const createBody = {
    card_kind: kind,
    delivery_start_date: d0,
  }
  if (memberCouponId != null) {
    createBody.member_coupon_id = Math.floor(Number(memberCouponId))
  }
  const { order, orderId } = await resolveMemberCardOrderId(createBody)
  const payResult = await runWechatPayForMemberCardOrder(orderId)
  return { order, orderId, ...payResult }
}

/**
 * 自律卡包：按后台模版创建订单并微信支付（成功后跳转「完善配送信息」页）。
 * @param {{ membershipTemplateId: number, deliveryStartYmd?: string }} opts
 * `deliveryStartYmd`: 续卡等档案已有起送日时可随单写入工单
 */
export async function runMembershipTemplateWechatPay({
  membershipTemplateId,
  deliveryStartYmd,
  memberCouponId = null,
}) {
  const tid = Number(membershipTemplateId)
  if (!Number.isFinite(tid) || tid < 1) {
    throw new Error('卡包无效')
  }
  const body = { membership_template_id: Math.floor(tid) }
  const d0 = String(deliveryStartYmd || '').trim().slice(0, 10)
  if (d0) {
    body.delivery_start_date = d0
  }
  if (memberCouponId != null) {
    body.member_coupon_id = Math.floor(Number(memberCouponId))
  }
  await syncWxMiniOpenidFromLogin()
  const { order, orderId } = await resolveMemberCardOrderId(body)
  const payResult = await runWechatPayForMemberCardOrder(orderId)
  return { order, orderId, ...payResult }
}
