/**
 * 球面大圆距离（米），输入 GCJ-02 经纬度。
 * @param {number} lng1
 * @param {number} lat1
 * @param {number} lng2
 * @param {number} lat2
 * @returns {number | null}
 */
export function haversineDistanceM(lng1, lat1, lng2, lat2) {
  const lo1 = Number(lng1)
  const la1 = Number(lat1)
  const lo2 = Number(lng2)
  const la2 = Number(lat2)
  if (![lo1, la1, lo2, la2].every(Number.isFinite)) return null
  const r = 6371000
  const p1 = (la1 * Math.PI) / 180
  const p2 = (la2 * Math.PI) / 180
  const dLat = ((la2 - la1) * Math.PI) / 180
  const dLng = ((lo2 - lo1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dLng / 2) ** 2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1 - a)))
  const m = r * c
  return Number.isFinite(m) ? m : null
}

/**
 * 格式化为小程序展示文案，如「直线约 1.2 km」「直线约 350 m」。
 * @param {number | null | undefined} meters
 * @returns {string}
 */
export function formatStraightDistanceM(meters) {
  const m = Number(meters)
  if (!Number.isFinite(m) || m < 0) return ''
  if (m < 1000) return `直线约 ${Math.round(m)} m`
  return `直线约 ${(m / 1000).toFixed(1)} km`
}
