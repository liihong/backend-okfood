/** 后端 409：会员已有未支付订单，不宜重复下单。 */

const MEMBER_CARD_ORDER_DETAIL_PAGE =
  '/packageOrder/pages/memberCardOrderDetail/memberCardOrderDetail'

function goMemberCardOrderDetail(orderId) {
  const id = Math.floor(Number(orderId))
  if (!Number.isFinite(id) || id < 1) return
  uni.navigateTo({
    url: `${MEMBER_CARD_ORDER_DETAIL_PAGE}?id=${encodeURIComponent(String(id))}`,
  })
}

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
    confirmText: orderId ? '去支付' : '查看订单',
    cancelText: '知道了',
    success: (res) => {
      if (!res.confirm) return
      if (isSingle && orderId) {
        uni.navigateTo({
          url: `/packageOrder/pages/singleOrderDetail/singleOrderDetail?id=${encodeURIComponent(String(orderId))}`,
        })
        return
      }
      if (!isSingle && orderId) {
        goMemberCardOrderDetail(orderId)
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
 * 开卡下单冲突：引导至对应工单详情页继续支付。
 * @param {unknown} err
 * @param {{ memberCouponId?: number | null }} [opts]
 * @returns {boolean} 是否已弹出引导
 */
export function promptUnpaidMallOrderConflict(err, opts = {}) {
  if (!isUnpaidOrderConflict(err)) return false
  const orderId = parsePendingOrderIdFromConflict(err)
  if (!orderId) return false
  const msg =
    err instanceof Error ? err.message : '您有待支付的开卡订单，请先完成支付'
  uni.showModal({
    title: '待支付订单',
    content: msg,
    confirmText: '去支付',
    cancelText: '知道了',
    success: (res) => {
      if (!res.confirm) return
      goMemberCardOrderDetail(orderId)
    },
  })
  return true
}
