import { request } from '@/utils/api.js'
import { createMemberCardOrder, fetchMemberCardWechatJsapiPayParams } from '@/utils/memberCardOrderApi.js'
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
  return { order, orderId }
}
