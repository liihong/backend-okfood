/**
 * 后端库内 DATETIME 为「北京时间」naive；API 多为无时区 ISO。
 * `Z` 结尾按 UTC 瞬时解析（仅兼容旧接口/外部）；否则按 +08:00 墙钟解析，避免管理员电脑的本地时区干扰。
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
