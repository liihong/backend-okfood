import { request } from '@/utils/api.js'
import {
  createMemberCardOrder,
  fetchMemberCardWechatJsapiPayParams,
  syncMemberCardWechatPayResult,
} from '@/utils/memberCardOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

/**
 * 创建开卡工单并调起微信支付（资料页「保存并支付」与个人中心「再次支付」共用）。
 * @param {{ cardKind: string, deliveryStartYmd: string, patchProfile?: boolean }} opts
 * `patchProfile`: 为 true 时先 PATCH plan_type + delivery_start_date（个人中心快捷支付用）
 */
export async function runMemberCardWechatPay({
  cardKind,
  deliveryStartYmd,
  patchProfile = false,
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
  const order = await createMemberCardOrder({
    card_kind: kind,
    delivery_start_date: d0,
  })
  const orderId = order && typeof order === 'object' ? order.id : null
  if (orderId == null) {
    throw new Error('开卡订单创建异常')
  }
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
  // 与微信异步通知互补：公网未收到 notify 时仍可按订单号拉单完成入账
  const maxTries = 6
  for (let i = 0; i < maxTries; i++) {
    try {
      await syncMemberCardWechatPayResult(orderId)
      break
    } catch (e) {
      const m = (e && e.message) || ''
      const maybeWait =
        m.includes('处理中') ||
        m.includes('稍候') ||
        m.includes('稍后再试') ||
        m.includes('未支付') ||
        m.includes('not_paid') ||
        /PAY_USERPAYING/i.test(m)
      if (maybeWait && i < maxTries - 1) {
        await new Promise((r) => setTimeout(r, 1500))
        continue
      }
      if (maybeWait) {
        throw new Error('支付已提交。若「我的」中次数未更新，请下拉刷新或稍后再看；仍无请联客服。')
      }
      throw e
    }
  }
  return { order, orderId }
}
