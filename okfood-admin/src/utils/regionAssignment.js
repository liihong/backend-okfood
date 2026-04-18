import { pathRingFromPolygonJson } from './polygonPath.js'
import { pointInPolygon } from './pointInPolygon.js'

/** 与后端 UNASSIGNED_DELIVERY_AREA 一致 */
export const UNASSIGNED_AREA_LABEL = '未分配'

/**
 * 按启用片区 priority、id 顺序做点选（同 assign_area_name_for_coords）。
 * @param {number} lng
 * @param {number} lat
 * @param {Array<Record<string, unknown>>} activeRegionsSorted
 */
export function assignAreaForCoords(lng, lat, activeRegionsSorted) {
  for (const r of activeRegionsSorted) {
    try {
      const ring = pathRingFromPolygonJson(r.polygon_json)
      if (ring.length >= 3 && pointInPolygon(lng, lat, ring)) {
        return typeof r.name === 'string' ? r.name : String(r.name ?? '')
      }
    } catch {
      /* 无效 polygon 跳过 */
    }
  }
  return UNASSIGNED_AREA_LABEL
}
