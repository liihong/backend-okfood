/**
 * 与后端 `app.core.delivery_calendar.is_subscription_delivery_day` 最低口径一致：
 * 周日固定不配送。法定节假日由服务端完整判定，保存接口会对非营业日静默跳过。
 */
export function isSubscriptionDeliveryDayIso(iso) {
  const raw = String(iso ?? '').trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!m) return false
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  return dt.getUTCDay() !== 0
}
