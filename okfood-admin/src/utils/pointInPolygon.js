/**
 * 射线法：点是否在有向闭合多边形内（与后端 region_geo.point_in_polygon 一致）。
 * @param {number} lng
 * @param {number} lat
 * @param {Array<[number, number]>} ring
 */
export function pointInPolygon(lng, lat, ring) {
  const n = ring.length
  if (n < 3) return false
  let inside = false
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i][0]
    const yi = ring[i][1]
    const xj = ring[j][0]
    const yj = ring[j][1]
    if (yi > lat !== yj > lat && lng < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-18) + xi) {
      inside = !inside
    }
  }
  return inside
}
