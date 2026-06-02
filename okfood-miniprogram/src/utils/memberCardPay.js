import { request } from '@/utils/api.js'
import {
  createMemberCardOrder,
  fetchMemberCardWechatJsapiPayParams,
  listMemberCardOrders,
  syncMemberCardWechatPayResult,
} from '@/utils/memberCardOrderApi.js'
import { syncWxMiniOpenidFromLogin } from '@/utils/wxMemberLogin.js'

/** 纯 Promise 实现，避免上传时「编译为 ES5」注入 @babel/runtime 导致白屏 */

function delayMs(ms) {
  return new Promise(function (resolve) {
    setTimeout(resolve, ms)
  })
}

function fetchPendingMemberCardOrderId() {
  return listMemberCardOrders({
    page: 1,
    page_size: 1,
    list_status: 'pending_pay',
  })
    .then(function (data) {
      const items = data && data.items
      const first = Array.isArray(items) ? items[0] : null
      const id = first && first.id != null ? Number(first.id) : NaN
      return Number.isFinite(id) && id > 0 ? id : null
    })
    .catch(function () {
      return null
    })
}

function throwPendingMemberCardOrderConflict(orderId) {
  const err = new Error(`您有未支付的开卡订单（#${orderId}），请先完成支付后再下单`)
  err.status = 409
  throw err
}

function resolveMemberCardOrderId(createBody) {
  return fetchPendingMemberCardOrderId().then(function (pendingId) {
    if (pendingId) {
      throwPendingMemberCardOrderConflict(pendingId)
    }
    return createMemberCardOrder(createBody).then(function (order) {
      const orderId = order && typeof order === 'object' ? order.id : null
      if (orderId == null) {
        throw new Error('开卡订单创建异常')
      }
      return { order: order, orderId: orderId }
    })
  })
}

function isPaySyncRetryable(err) {
  const m = (err && err.message) || ''
  return (
    m.includes('处理中') ||
    m.includes('稍候') ||
    m.includes('稍后再试') ||
    m.includes('未支付') ||
    m.includes('未缴') ||
    m.includes('not_paid') ||
    /PAY_USERPAYING/i.test(m)
  )
}

function syncMemberCardPayWithRetry(orderId, tryIndex, retryDelaysMs, maxTries) {
  return syncMemberCardWechatPayResult(orderId)
    .then(function () {
      return { wechatPaid: true, paySynced: true }
    })
    .catch(function (e) {
      if (isPaySyncRetryable(e) && tryIndex < maxTries - 1) {
        const delay = retryDelaysMs[tryIndex] != null ? retryDelaysMs[tryIndex] : 2000
        return delayMs(delay).then(function () {
          return syncMemberCardPayWithRetry(orderId, tryIndex + 1, retryDelaysMs, maxTries)
        })
      }
      if (isPaySyncRetryable(e)) {
        return { wechatPaid: true, paySynced: false }
      }
      throw e
    })
}

function runWechatPayForMemberCardOrder(orderId) {
  return fetchMemberCardWechatJsapiPayParams(orderId).then(function (pay) {
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
      return syncMemberCardPayWithRetry(orderId, 0, retryDelaysMs, maxTries)
    })
  })
}

function mergePayResult(order, orderId, payResult) {
  return {
    order: order,
    orderId: orderId,
    wechatPaid: payResult.wechatPaid,
    paySynced: payResult.paySynced,
  }
}

/**
 * 对已有开卡工单调起微信支付并同步入账。
 * @param {number} orderId
 */
export function payMemberCardOrderWechat(orderId) {
  return syncWxMiniOpenidFromLogin().then(function () {
    return runWechatPayForMemberCardOrder(orderId)
  })
}

/**
 * 创建开卡工单并调起微信支付（资料页「保存并支付」与个人中心「再次支付」共用）。
 */
export function runMemberCardWechatPay(opts) {
  const o = opts || {}
  const d0 = String(o.deliveryStartYmd || '').trim().slice(0, 10)
  if (!d0) {
    return Promise.reject(new Error('缺少开始配送日期'))
  }
  const kind = String(o.cardKind || '').trim()
  if (kind !== '周卡' && kind !== '月卡') {
    return Promise.reject(new Error('请选择周卡或月卡'))
  }
  let chain = Promise.resolve()
  if (o.patchProfile) {
    chain = request('/api/user/profile', {
      method: 'PATCH',
      data: { plan_type: kind, delivery_start_date: d0 },
    })
  }
  return chain
    .then(function () {
      return syncWxMiniOpenidFromLogin()
    })
    .then(function () {
      const createBody = {
        card_kind: kind,
        delivery_start_date: d0,
      }
      if (o.memberCouponId != null) {
        createBody.member_coupon_id = Math.floor(Number(o.memberCouponId))
      }
      return resolveMemberCardOrderId(createBody)
    })
    .then(function (resolved) {
      return runWechatPayForMemberCardOrder(resolved.orderId).then(function (payResult) {
        return mergePayResult(resolved.order, resolved.orderId, payResult)
      })
    })
}

/**
 * 自律卡包：按后台模版创建订单并微信支付。
 */
export function runMembershipTemplateWechatPay(opts) {
  const o = opts || {}
  const tid = Number(o.membershipTemplateId)
  if (!Number.isFinite(tid) || tid < 1) {
    return Promise.reject(new Error('卡包无效'))
  }
  const body = { membership_template_id: Math.floor(tid) }
  const d0 = String(o.deliveryStartYmd || '').trim().slice(0, 10)
  if (d0) {
    body.delivery_start_date = d0
  }
  if (o.memberCouponId != null) {
    body.member_coupon_id = Math.floor(Number(o.memberCouponId))
  }
  return syncWxMiniOpenidFromLogin()
    .then(function () {
      return resolveMemberCardOrderId(body)
    })
    .then(function (resolved) {
      return runWechatPayForMemberCardOrder(resolved.orderId).then(function (payResult) {
        return mergePayResult(resolved.order, resolved.orderId, payResult)
      })
    })
}
