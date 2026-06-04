/** 系统消息跳转：解析供餐日等业务日期（勿用单次零售的 business_date uk 槽位）。 */

export const KIND_SINGLE_MEAL_ORDER_PAID = 'single_meal_order_paid'

const YMD_RE = /^\d{4}-\d{2}-\d{2}$/
const SUPPLY_DAY_MSG_RE = /供餐日[：:\s]*(\d{4}-\d{2}-\d{2})/

export function todayShanghaiYmd() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const y = parts.find((p) => p.type === 'year')?.value || '1970'
  const mo = parts.find((p) => p.type === 'month')?.value || '01'
  const da = parts.find((p) => p.type === 'day')?.value || '01'
  return `${y}-${mo}-${da}`
}

/** 从单次零售消息正文解析供餐日。 */
export function parseSupplyDayFromNotificationMessage(message) {
  const m = String(message || '').match(SUPPLY_DAY_MSG_RE)
  return m && YMD_RE.test(m[1]) ? m[1] : ''
}

/**
 * 跳转订单管理 / 顺丰监控时使用的配送业务日。
 * 单次零售：优先 API delivery_date 或正文供餐日，不用 business_date。
 */
export function resolveNotificationDeliveryDate(item) {
  if (!item) return ''
  const apiDay = String(item.delivery_date || '').trim()
  if (YMD_RE.test(apiDay)) return apiDay
  if (item.kind === KIND_SINGLE_MEAL_ORDER_PAID) {
    const fromMsg = parseSupplyDayFromNotificationMessage(item.message)
    if (fromMsg) return fromMsg
    return todayShanghaiYmd()
  }
  const bd = String(item.business_date || '').trim()
  return YMD_RE.test(bd) ? bd : ''
}
