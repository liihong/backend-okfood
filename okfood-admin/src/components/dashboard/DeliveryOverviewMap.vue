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

/** @type {any} */
let memberInfoWindow = null

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function plotStatusLabel(st) {
  switch (st) {
    case 'matched':
      return '坐标与档案片区一致'
    case 'mismatch':
      return '档案片区与坐标推算不一致'
    case 'outside_assigned':
      return '坐标不在启用片区内（档案有片区）'
    case 'no_coords':
      return '无坐标（地图上不显示图钉）'
    default:
      return ''
  }
}

/** 门店锚点图钉（与会员黄/绿区分） */
function storePinIconDataUrl() {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">' +
    '<path fill="#dc2626" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round" ' +
    'd="M19 3C11.8 3 6 8.5 6 15.2c0 7.2 11.2 23.5 13 25.8 1.8-2.3 13-18.6 13-25.8C32 8.5 26.2 3 19 3z"/>' +
    '<text x="19" y="19" text-anchor="middle" fill="#ffffff" font-size="12" font-weight="700" ' +
    "font-family=\"system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif\">店</text></svg>"
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

/** GCJ-02 会员图钉：白描边 + 中心高光，颜色与图例一致 */
function memberPinIconDataUrl(hexColor) {
  const fill = String(hexColor || '#eab308').trim()
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="46" viewBox="0 0 36 46"><path fill="${fill}" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round" d="M18 3C10.3 3 4 9.1 4 16.4c0 8.5 14 25.6 14 25.6s14-17.1 14-25.6C32 9.1 25.7 3 18 3z"/><circle cx="18" cy="16" r="5" fill="#ffffff" fill-opacity="0.92"/></svg>`
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

function memberInfoWindowHtml(m) {
  const name = escapeHtml(m.name || '（未命名）')
  const phoneRaw = String(m.phone || '').trim()
  const phone = escapeHtml(phoneRaw || '—')
  const area = escapeHtml(String(m.area || '').trim() || '—')
  const expected = String(m.expectedArea || '').trim()
  const actual = String(m.area || '').trim()
  const showExpected = expected && actual && expected !== actual
  const deliveredToday = m.deliveredToday === true || m.deliveredToday === 1
  const todayDeliveryLabel = deliveredToday ? '今日已送达' : '今日未送达'
  const status = plotStatusLabel(m.plotStatus)
  const statusHtml = status
    ? `<p class="dov-iw-row dov-iw-status">${escapeHtml(status)}</p>`
    : ''
  const expRow = showExpected
    ? `<p class="dov-iw-row"><span class="dov-iw-k">坐标推算</span><span class="dov-iw-v">${escapeHtml(expected)}</span></p>`
    : ''
  return `<div class="dov-iw">
    <p class="dov-iw-title">${name}</p>
    <p class="dov-iw-row"><span class="dov-iw-k">手机</span><span class="dov-iw-v">${phone}</span></p>
    <p class="dov-iw-row"><span class="dov-iw-k">档案片区</span><span class="dov-iw-v">${area}</span></p>
    <p class="dov-iw-row"><span class="dov-iw-k">送达</span><span class="dov-iw-v">${escapeHtml(todayDeliveryLabel)}</span></p>
    ${expRow}
    ${statusHtml}
  </div>`
}

const props = defineProps({
  amapKey: { type: String, default: '' },
  amapSecurity: { type: String, default: '' },
  regionsSorted: { type: Array, required: true },
  regionColorById: { type: Object, required: true },
  memberPoints: { type: Array, required: true },
  /** 后台门店配置：有坐标时地图以门店为中心并展示红色「店」标 */
  storeAnchor: { type: Object, default: null },
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

/** 已配置门店坐标时以门店为中心；否则保持新乡市域视野（与历史行为一致） */
function fitMapViewToStoreOrCity() {
  if (!map) return
  const sa = props.storeAnchor
  const lng = sa?.store_lng != null ? Number(sa.store_lng) : NaN
  const lat = sa?.store_lat != null ? Number(sa.store_lat) : NaN
  if (Number.isFinite(lng) && Number.isFinite(lat)) {
    map.setCenter([lng, lat])
    map.setZoom(12)
    return
  }
  fitMapToXinxiangCity()
}

function renderOverlays(AMap) {
  if (!map) return
  if (memberInfoWindow) {
    try {
      memberInfoWindow.close()
    } catch {
      /* ignore */
    }
    memberInfoWindow = null
  }
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
  const sa = props.storeAnchor
  const slng = sa?.store_lng != null ? Number(sa.store_lng) : NaN
  const slat = sa?.store_lat != null ? Number(sa.store_lat) : NaN
  if (Number.isFinite(slng) && Number.isFinite(slat)) {
    const STORE_W = 38
    const STORE_H = 46
    const sicon = new AMap.Icon({
      size: new AMap.Size(STORE_W, STORE_H),
      image: storePinIconDataUrl(),
      imageSize: new AMap.Size(STORE_W, STORE_H),
    })
    const sname = (typeof sa.store_name === 'string' && sa.store_name.trim()) || '门店'
    const sm = new AMap.Marker({
      position: [slng, slat],
      icon: sicon,
      title: sname,
      zIndex: 200,
      anchor: 'bottom-center',
    })
    map.add(sm)
    overlays.push(sm)
  }
  const PIN_W = 36
  const PIN_H = 46
  for (const m of props.memberPoints) {
    const lng = m.lng != null ? Number(m.lng) : null
    const lat = m.lat != null ? Number(m.lat) : null
    if (lng == null || lat == null || Number.isNaN(lng) || Number.isNaN(lat)) continue
    const color = m.markerColor || '#eab308'
    const icon = new AMap.Icon({
      size: new AMap.Size(PIN_W, PIN_H),
      image: memberPinIconDataUrl(color),
      imageSize: new AMap.Size(PIN_W, PIN_H),
    })
    const marker = new AMap.Marker({
      position: [lng, lat],
      icon,
      anchor: 'bottom-center',
      zIndex: 130,
      cursor: 'pointer',
    })
    const pos = [lng, lat]
    marker.on('click', () => {
      if (memberInfoWindow) {
        try {
          memberInfoWindow.close()
        } catch {
          /* ignore */
        }
        memberInfoWindow = null
      }
      setTimeout(() => {
        memberInfoWindow = new AMap.InfoWindow({
          isCustom: true,
          content: memberInfoWindowHtml(m),
          offset: new AMap.Pixel(0, -PIN_H - 4),
          closeWhenClickMap: true,
        })
        memberInfoWindow.open(map, pos)
      }, 0)
    })
    map.add(marker)
    overlays.push(marker)
  }
  fitMapViewToStoreOrCity()
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
    const sa0 = props.storeAnchor
    const cLng = sa0?.store_lng != null ? Number(sa0.store_lng) : NaN
    const cLat = sa0?.store_lat != null ? Number(sa0.store_lat) : NaN
    const hasStore = Number.isFinite(cLng) && Number.isFinite(cLat)
    map = new AMap.Map(mapEl.value, {
      zoom: hasStore ? 12 : 10.5,
      center: hasStore ? [cLng, cLat] : [...XINXIANG_CENTER],
      viewMode: '2D',
      mapStyle: 'amap://styles/normal',
    })
    map.on('click', () => {
      if (memberInfoWindow) {
        try {
          memberInfoWindow.close()
        } catch {
          /* ignore */
        }
        memberInfoWindow = null
      }
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
  () => [props.memberPoints, props.storeAnchor],
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
  if (memberInfoWindow) {
    try {
      memberInfoWindow.close()
    } catch {
      /* ignore */
    }
    memberInfoWindow = null
  }
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

<!-- InfoWindow 插入地图容器，非 Vue 编译；用全局类名避免 scoped 不生效 -->
<style>
.dov-iw {
  min-width: 200px;
  max-width: 280px;
  padding: 12px 14px;
  font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  line-height: 1.45;
  color: #0f172a;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(15, 23, 42, 0.18), 0 0 0 1px rgba(226, 232, 240, 0.9);
}
.dov-iw-title {
  margin: 0 0 8px;
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.02em;
}
.dov-iw-row {
  margin: 0 0 6px;
  display: flex;
  gap: 8px;
  align-items: flex-start;
  font-size: 12px;
}
.dov-iw-row:last-child {
  margin-bottom: 0;
}
.dov-iw-k {
  flex-shrink: 0;
  width: 4.5em;
  color: #64748b;
  font-weight: 600;
}
.dov-iw-v {
  flex: 1;
  min-width: 0;
  font-weight: 650;
  color: #334155;
  word-break: break-all;
}
.dov-iw-status {
  margin-top: 4px !important;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
  display: block !important;
  font-size: 11px;
  font-weight: 700;
  color: #b45309;
}
</style>
