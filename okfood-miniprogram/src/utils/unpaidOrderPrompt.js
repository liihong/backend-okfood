/** 后端 409：会员已有未支付订单，不宜重复下单。 */

/** @param {unknown} err */
export function isUnpaidOrderConflict(err) {
  return (
    err &&
    typeof err === 'object' &&
    /** @type {{ status?: number }} */ (err).status === 409
  )
}

/** @param {unknown} err */
export function parsePendingOrderIdFromConflict(err) {
  const msg = err instanceof Error ? err.message : ''
  const m = String(msg || '').match(/#(\d+)/)
  const id = m ? parseInt(m[1], 10) : NaN
  return Number.isFinite(id) && id > 0 ? id : null
}

export const STORAGE_OPEN_ORDERS_PENDING_PAY = 'okfood_open_orders_pending_pay'

/**
 * @param {unknown} err
 * @param {{ kind: 'single' | 'mall' }} opts
 * @returns {boolean} 是否已弹出引导
 */
export function promptUnpaidOrderConflict(err, { kind }) {
  if (!isUnpaidOrderConflict(err)) return false
  const msg =
    err instanceof Error ? err.message : '您有待支付订单，请先完成支付后再下单'
  const orderId = parsePendingOrderIdFromConflict(err)
  const isSingle = kind === 'single'
  uni.showModal({
    title: '待支付订单',
    content: msg,
    confirmText: orderId && isSingle ? '去支付' : '查看订单',
    cancelText: '知道了',
    success: (res) => {
      if (!res.confirm) return
      if (isSingle && orderId) {
        uni.navigateTo({
          url: `/packageOrder/pages/singleOrderDetail/singleOrderDetail?id=${encodeURIComponent(String(orderId))}`,
        })
        return
      }
      try {
        uni.setStorageSync(STORAGE_OPEN_ORDERS_PENDING_PAY, isSingle ? 'single' : 'mall')
      } catch {
        /* ignore */
      }
      uni.switchTab({ url: '/pages/orders/index' })
    },
  })
  return true
}

/**
 * 开卡下单冲突时询问是否对已有工单继续支付。
 * @param {unknown} err
 * @returns {Promise<number | null>} 已有工单 id；用户取消或非冲突则 null
 */
export function confirmContinueExistingMallOrderPay(err) {
  if (!isUnpaidOrderConflict(err)) return Promise.resolve(null)
  const orderId = parsePendingOrderIdFromConflict(err)
  if (!orderId) return Promise.resolve(null)
  const msg =
    err instanceof Error ? err.message : '您有待支付的开卡订单，请先完成支付'
  return new Promise((resolve) => {
    uni.showModal({
      title: '待支付订单',
      content: msg,
      confirmText: '继续支付',
      cancelText: '取消',
      success: (res) => resolve(res.confirm ? orderId : null),
    })
  })
}
