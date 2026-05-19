/**
 * 库内/API：naive ISO = 北京时间；`Z` 按 UTC（兼容旧响应）。
 * @param {unknown} iso
 * @returns {Date}
 */
export function parseApiDateTimeBeijing(iso) {
  const raw = String(iso ?? '').trim()
  if (!raw) return new Date(NaN)
  const t = raw.replace(' ', 'T')
  if (/Z$/i.test(t)) return new Date(t)
  if (/[+-]\d{2}:\d{2}$/.test(t)) return new Date(t)
  if (/^\d{4}-\d{2}-\d{2}T\d{1,2}:\d{2}/.test(t)) return new Date(t + '+08:00')
  return new Date(t)
}
