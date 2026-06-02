import { fetchWechatJsapiPayParams, syncSingleMealWechatPayResult } from '@/utils/singleOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

function delayMs(ms) {
  return new Promise(function (resolve) {
    setTimeout(resolve, ms)
  })
}

function isPaySyncRetryable(err) {
  const m = (err && err.message) || ''
  return (
    m.includes('处理中') ||
    m.includes('稍候') ||
    m.includes('稍后再试') ||
    m.includes('未支付') ||
    m.includes('not_paid') ||
    /PAY_USERPAYING/i.test(m)
  )
}

function syncSingleMealPayWithRetry(orderId, tryIndex, retryDelaysMs, maxTries) {
  return syncSingleMealWechatPayResult(orderId)
    .then(function () {
      return { wechatPaid: true, paySynced: true }
    })
    .catch(function (e) {
      if (isPaySyncRetryable(e) && tryIndex < maxTries - 1) {
        const delay = retryDelaysMs[tryIndex] != null ? retryDelaysMs[tryIndex] : 2000
        return delayMs(delay).then(function () {
          return syncSingleMealPayWithRetry(orderId, tryIndex + 1, retryDelaysMs, maxTries)
        })
      }
      if (isPaySyncRetryable(e)) {
        return { wechatPaid: true, paySynced: false }
      }
      throw e
    })
}

function runWechatPayForSingleMealOrder(orderId) {
  return fetchWechatJsapiPayParams(orderId).then(function (pay) {
    return new Promise(function (resolve, reject) {
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
    }).then(function () {
      const retryDelaysMs = [800, 1200, 1500, 2000, 2500, 3000, 3500, 4000]
      const maxTries = retryDelaysMs.length + 1
      return syncSingleMealPayWithRetry(orderId, 0, retryDelaysMs, maxTries)
    })
  })
}

/**
 * 对已有单次零售订单调起微信支付并同步入账。
 * @param {number} orderId
 */
export function paySingleMealOrderWechat(orderId) {
  return syncWxMiniOpenidFromLogin().then(function () {
    return runWechatPayForSingleMealOrder(orderId)
  })
}
