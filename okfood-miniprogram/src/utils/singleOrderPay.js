import { fetchWechatJsapiPayParams, syncSingleMealWechatPayResult } from '@/utils/singleOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

/** 微信扣款成功后拉单同步；返回是否已在服务端记为已支付 */
async function runWechatPayForSingleMealOrder(orderId) {
  const pay = await fetchWechatJsapiPayParams(orderId)
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
      await syncSingleMealWechatPayResult(orderId)
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
 * 对已有单次零售订单调起微信支付并同步入账。
 * @param {number} orderId
 */
export async function paySingleMealOrderWechat(orderId) {
  await syncWxMiniOpenidFromLogin()
  return runWechatPayForSingleMealOrder(orderId)
}
