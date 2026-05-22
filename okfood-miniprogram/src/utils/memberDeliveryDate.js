/** 会员起送日等与 menuApi 一致的最小日期（独立模块，避免 memberProfile ↔ menuApi 打包顺序问题）。 */

export function ymdTodayShanghai(now = new Date()) {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(now)
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* ignore */
  }
  const d = new Date(now)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** @param {string} isoDate YYYY-MM-DD */
export function addDaysIso(isoDate, days) {
  if (!isoDate || typeof isoDate !== 'string') return ''
  const n = Math.floor(Number(days)) || 0
  const anchor = new Date(`${isoDate.trim()}T12:00:00`)
  if (Number.isNaN(anchor.getTime())) return ''
  anchor.setDate(anchor.getDate() + n)
  return `${anchor.getFullYear()}-${String(anchor.getMonth() + 1).padStart(2, '0')}-${String(anchor.getDate()).padStart(2, '0')}`
}

function isShanghaiPastDailyCutoff(now = new Date(), hour = 10) {
  const h0 = Math.floor(Number(hour)) || 10
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Shanghai',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).formatToParts(now)
    const h = parseInt(parts.find((p) => p.type === 'hour')?.value || '0', 10) || 0
    if (h > h0) return true
    if (h < h0) return false
    return true
  } catch {
    const d = new Date(now)
    return d.getHours() > h0 || d.getHours() === h0
  }
}

/** 会员起送业务日可选的最小 YYYY-MM-DD（上海） */
export function minMemberDeliveryStartYmd(now = new Date()) {
  const today = ymdTodayShanghai(now)
  const delta = isShanghaiPastDailyCutoff(now) ? 1 : 0
  return addDaysIso(today, delta)
}
