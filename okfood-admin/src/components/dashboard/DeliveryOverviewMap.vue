<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { loadAmapOnce } from '../../utils/amapLoader.js'
import { pathRingFromPolygonJson } from '../../utils/polygonPath.js'

/** 新乡市 GCJ-02：市中心 */
const XINXIANG_CENTER = [113.9268, 35.303]
/**
 * 市域包络 [lng,lat]：仅用此矩形适配视野，不用会员/异常坐标扩展，避免视野被拉到「全中国」。
 */
const XINXIANG_CITY_SW = [113.48, 34.78]
const XINXIANG_CITY_NE = [114.52, 35.56]
/** 在包络外再扩一点留白（度） */
const XINXIANG_BOUNDS_MARGIN_DEG = 0.03
const BOUNDS_PADDING_PX = [48, 56, 72, 56]

const props = defineProps({
  amapKey: { type: String, default: '' },
  amapSecurity: { type: String, default: '' },
  regionsSorted: { type: Array, required: true },
  regionColorById: { type: Object, required: true },
  memberPoints: { type: Array, required: true },
})

const mapEl = ref(null)
let map = null
/** @type {ResizeObserver | null} */
let resizeObs = null

/**
 * 固定新乡市范围适配视野（不读取会员坐标/多边形外点，避免脏数据把地图拉到全国）。
 */
function fitMapToXinxiangCity() {
  if (!map) return
  const m = XINXIANG_BOUNDS_MARGIN_DEG
  const sw = [XINXIANG_CITY_SW[0] - m, XINXIANG_CITY_SW[1] - m]
  const ne = [XINXIANG_CITY_NE[0] + m, XINXIANG_CITY_NE[1] + m]
  try {
    const bounds = new AMap.Bounds(sw, ne)
    map.setBounds(bounds, false, BOUNDS_PADDING_PX)
  } catch {
    map.setCenter([...XINXIANG_CENTER])
    map.setZoom(10.5)
  }
}

function renderOverlays(AMap) {
  if (!map) return
  map.clearMap()
  const overlays = []
  for (const r of props.regionsSorted) {
    const path = pathRingFromPolygonJson(r.polygon_json)
    if (path.length < 3) continue
    const fill = props.regionColorById[r.id] || '#94a3b8'
    const inactive = r.is_active === false || r.is_active === 0
    const poly = new AMap.Polygon({
      path,
      strokeColor: fill,
      fillColor: fill,
      fillOpacity: inactive ? 0.06 : 0.2,
      strokeOpacity: inactive ? 0.35 : 0.95,
      strokeWeight: inactive ? 1 : 2,
      zIndex: 10,
    })
    map.add(poly)
    overlays.push(poly)
  }
  for (const m of props.memberPoints) {
    const lng = m.lng != null ? Number(m.lng) : null
    const lat = m.lat != null ? Number(m.lat) : null
    if (lng == null || lat == null || Number.isNaN(lng) || Number.isNaN(lat)) continue
    const color = m.markerColor || '#64748b'
    const cm = new AMap.CircleMarker({
      center: [lng, lat],
      radius: 5,
      strokeColor: color,
      fillColor: color,
      strokeWeight: 1,
      strokeOpacity: 0.95,
      fillOpacity: 0.9,
      zIndex: 120,
    })
    map.add(cm)
    overlays.push(cm)
  }
  fitMapToXinxiangCity()
}

async function initMap() {
  const key = String(props.amapKey || '').trim()
  if (!key) return
  await nextTick()
  if (!mapEl.value) return
  try {
    const AMap = await loadAmapOnce(key, props.amapSecurity, [])
    if (map) {
      map.destroy()
      map = null
    }
    map = new AMap.Map(mapEl.value, {
      zoom: 10.5,
      center: [...XINXIANG_CENTER],
      viewMode: '2D',
      mapStyle: 'amap://styles/normal',
    })
    renderOverlays(AMap)
    if (typeof ResizeObserver !== 'undefined' && mapEl.value) {
      resizeObs?.disconnect()
      resizeObs = new ResizeObserver(() => map?.resize?.())
      resizeObs.observe(mapEl.value)
    }
  } catch (e) {
    console.error(e)
    map = null
  }
}

watch(
  () => props.memberPoints,
  () => {
    if (map && window.AMap) renderOverlays(window.AMap)
  },
  { deep: true },
)

watch(
  () => [props.regionsSorted, props.regionColorById],
  () => {
    if (map && window.AMap) renderOverlays(window.AMap)
  },
  { deep: true },
)

watch(
  () => props.amapKey,
  () => {
    void initMap()
  },
)

onMounted(() => {
  void initMap()
})

onUnmounted(() => {
  resizeObs?.disconnect()
  resizeObs = null
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<template>
  <div v-if="String(amapKey || '').trim()" ref="mapEl" class="delivery-overview-map" />
  <p v-else class="delivery-overview-map-hint">未配置 <code>VITE_AMAP_KEY</code>，无法展示地图；片区与会员统计仍可查看页面内图例。</p>
</template>

<style scoped>
.delivery-overview-map {
  width: 100%;
  height: min(76vh, 880px);
  min-height: 520px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
.delivery-overview-map-hint {
  margin: 0;
  padding: 1rem 1.25rem;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border-radius: 16px;
  border: 1px dashed #cbd5e1;
}
.delivery-overview-map-hint code {
  font-size: 12px;
}
</style>
