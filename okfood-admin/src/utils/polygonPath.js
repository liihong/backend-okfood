/**
 * 将 delivery_regions.polygon_json 转为外环 [[lng, lat], ...]（GCJ-02）。
 * @param {unknown} json
 * @returns {Array<[number, number]>}
 */
export function pathRingFromPolygonJson(json) {
  if (Array.isArray(json)) {
    return json.map((p) => [Number(p[0]), Number(p[1])])
  }
  if (json && typeof json === 'object' && json.type === 'Polygon' && Array.isArray(json.coordinates?.[0])) {
    return json.coordinates[0].map((p) => [Number(p[0]), Number(p[1])])
  }
  return []
}
