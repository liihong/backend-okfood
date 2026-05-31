/** 会员起送日等与 menuApi 一致的最小日期（独立模块，避免 memberProfile ↔ menuApi 打包顺序问题）。 */

/** 无 Intl 时区时的上海日历日（UTC+8 墙钟） */
function ymdTodayShanghaiFallback(now = new Date()) {
  const t = now instanceof Date ? now.getTime() : Number(now)
  const anchor = Number.isFinite(t) ? t : Date.now()
  const shMs = anchor + 8 * 60 * 60 * 1000
  const sh = new Date(shMs)
  return `${sh.getUTCFullYear()}-${String(sh.getUTCMonth() + 1).padStart(2, '0')}-${String(sh.getUTCDate()).padStart(2, '0')}`
}

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
  return ymdTodayShanghaiFallback(now)
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

/** 会员起送业务日可选的最小 YYYY-MM-DD（上海）：当天不可选，最早为「明天」，与后端对齐。 */
export function minMemberDeliveryStartYmd(now = new Date()) {
  const today = ymdTodayShanghai(now)
  return addDaysIso(today, 1) || today
}

/**
 * 供微信原生 date-picker 的 `start` 绑定：比业务最小日早 1 天。
 * 部分机型对 `start` 按「严格大于」处理；业务最小日为「明天」时绑「今天」才能滚到明天。
 * 保存时仍以 {@link minMemberDeliveryStartYmd} 校验。
 */
export function pickerMinDeliveryStartYmd(now = new Date()) {
  const min = minMemberDeliveryStartYmd(now)
  return addDaysIso(min, -1) || min
}
