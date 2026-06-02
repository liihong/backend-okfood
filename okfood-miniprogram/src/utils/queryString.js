/**
 * 构建 URL query 字符串（微信小程序运行时无 URLSearchParams）
 * @param {Record<string, string | number | boolean | undefined | null>} params
 * @returns {string} 不含前导 ? 的 query，空则返回 ''
 */
export function buildQueryString(params) {
  const parts = []
  for (const k of Object.keys(params)) {
    const v = params[k]
    if (v == null || v === '') continue
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  }
  return parts.join('&')
}
