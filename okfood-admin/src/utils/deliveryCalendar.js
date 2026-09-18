/**
 * 订阅配送业务日完整口径在后端 `app.core.delivery_calendar`（含补班周日）。
 * 前端无法复刻国务院日历，勿用本函数做业务拦截；保留仅供历史引用或离线粗判。
 * @deprecated 请依赖接口返回的 is_subscription_delivery_day
 */
export function isSubscriptionDeliveryDayIso(iso) {
  const raw = String(iso ?? '').trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!m) return false
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  // 仅排除「确定是普通周日」的粗判；补班周日须走服务端
  return dt.getUTCDay() !== 0
}
