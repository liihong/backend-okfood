import { fetchRetailWechatPayParams, syncRetailWechatPayResult } from '@/utils/retailOrder/retailOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

function delayMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
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

function syncRetailPayWithRetry(orderId, tryIndex, retryDelaysMs, maxTries) {
  return syncRetailWechatPayResult(orderId)
    .then(() => ({ wechatPaid: true, paySynced: true }))
    .catch((e) => {
      if (isPaySyncRetryable(e) && tryIndex < maxTries - 1) {
        const delay = retryDelaysMs[tryIndex] != null ? retryDelaysMs[tryIndex] : 2000
        return delayMs(delay).then(() =>
          syncRetailPayWithRetry(orderId, tryIndex + 1, retryDelaysMs, maxTries),
        )
      }
      if (isPaySyncRetryable(e)) {
        return { wechatPaid: true, paySynced: false }
      }
      throw e
    })
}

function runWechatPayForRetailOrder(orderId) {
  return fetchRetailWechatPayParams(orderId).then((pay) => {
    return new Promise((resolve, reject) => {
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
    }).then(() => {
      const retryDelaysMs = [800, 1200, 1500, 2000, 2500, 3000]
      const maxTries = retryDelaysMs.length + 1
      return syncRetailPayWithRetry(orderId, 0, retryDelaysMs, maxTries)
    })
  })
}

/** @param {number} orderId */
export function payRetailOrderWechat(orderId) {
  return syncWxMiniOpenidFromLogin().then(() => runWechatPayForRetailOrder(orderId))
}
