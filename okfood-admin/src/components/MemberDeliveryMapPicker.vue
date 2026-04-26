<script setup>
/**
 * 会员配送选点：高德搜索 / 点击地图 / 拖标记，并回写地图定位文案（GCJ-02）。
 */
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { loadAmapOnce } from '../utils/amapLoader.js'

const XINXIANG_CENTER = [113.9268, 35.303]

function memberPickPinIconDataUrl() {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="38" height="46" viewBox="0 0 38 46">' +
    '<path fill="#0e5a44" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round" ' +
    'd="M19 3C11.8 3 6 8.5 6 15.2c0 7.2 11.2 23.5 13 25.8 1.8-2.3 13-18.6 13-25.8C32 8.5 26.2 3 19 3z"/>' +
    '<text x="19" y="19" text-anchor="middle" fill="#ffffff" font-size="11" font-weight="700" ' +
    "font-family=\"system-ui,-apple-system,'PingFang SC','Microsoft YaHei',sans-serif\">配</text></svg>"
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

function markerOptions(AMap, lng, lat) {
  const W = 38
  const H = 46
  return {
    position: [lng, lat],
    draggable: true,
    cursor: 'move',
    title: '配送位置（可拖动）',
    icon: new AMap.Icon({
      size: new AMap.Size(W, H),
      image: memberPickPinIconDataUrl(),
      imageSize: new AMap.Size(W, H),
    }),
    anchor: 'bottom-center',
  }
}

const props = defineProps({
  lngStr: { type: String, default: '' },
  latStr: { type: String, default: '' },
  mapLocationText: { type: String, default: '' },
})

const emit = defineEmits(['update:lngStr', 'update:latStr', 'update:mapLocationText', 'warn'])

const amapKey = String(import.meta.env.VITE_AMAP_KEY || '').trim()
const amapSecurity = String(import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim()

const mapEl = ref(null)
const searchKeyword = ref('')
const searchInputId = 'card-order-delivery-amap-search'

let map = null
let marker = null
let placeSearch = null
let autoComplete = null
let geocoder = null
/** @type {ResizeObserver | null} */
let resizeObs = null

function parseCoord(s) {
  const n = Number(String(s ?? '').trim())
  return Number.isFinite(n) ? n : NaN
}

function formatCoord(n) {
  return String(Math.round(Number(n) * 1e6) / 1e6)
}

function poiToMapText(poi) {
  if (!poi) return ''
  const name = String(poi.name || '').trim()
  const addr = String(poi.address || '').trim()
  const district = String(poi.district || '').trim()
  if (name && addr) return `${name} ${addr}`.trim()
  if (district && name) return `${district}${name}`.trim()
  return name || addr || district || ''
}

function applyPick(lng, lat, mapText) {
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) return
  emit('update:lngStr', formatCoord(lng))
  emit('update:latStr', formatCoord(lat))
  if (mapText != null && String(mapText).trim()) {
    emit('update:mapLocationText', String(mapText).trim().slice(0, 500))
  }
}

function reverseGeocodeToText(lng, lat) {
  if (!geocoder || !Number.isFinite(lng) || !Number.isFinite(lat)) return
  geocoder.getAddress([lng, lat], (status, result) => {
    if (status === 'complete' && result?.regeocode?.formattedAddress) {
      const t = String(result.regeocode.formattedAddress).trim()
      if (t) emit('update:mapLocationText', t.slice(0, 500))
    }
  })
}

function bindMarkerDragEnd(m) {
  m.on('dragend', () => {
    const p = m.getPosition()
    const lng = p.getLng()
    const lat = p.getLat()
    emit('update:lngStr', formatCoord(lng))
    emit('update:latStr', formatCoord(lat))
    reverseGeocodeToText(lng, lat)
  })
}

function syncMarkerFromProps() {
  if (!map) return
  const AMap = window.AMap
  if (!AMap) return
  const lng = parseCoord(props.lngStr)
  const lat = parseCoord(props.latStr)
  if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
    if (marker) {
      try {
        map.remove(marker)
      } catch {
        /* ignore */
      }
      marker = null
    }
    return
  }
  if (!marker) {
    marker = new AMap.Marker(markerOptions(AMap, lng, lat))
    bindMarkerDragEnd(marker)
    map.add(marker)
  } else {
    marker.setPosition([lng, lat])
  }
}

async function initMap() {
  if (!amapKey || !mapEl.value) return
  resizeObs?.disconnect()
  resizeObs = null

  const AMap = await loadAmapOnce(amapKey, amapSecurity, [])
  await new Promise((resolve) => {
    AMap.plugin(['AMap.PlaceSearch', 'AMap.AutoComplete', 'AMap.Geocoder'], () => resolve())
  })

  geocoder = new AMap.Geocoder({ city: '全国' })

  if (map) {
    try {
      map.destroy()
    } catch {
      /* ignore */
    }
    map = null
    marker = null
  }
  autoComplete = null

  const lng = parseCoord(props.lngStr)
  const lat = parseCoord(props.latStr)
  const hasPoint = Number.isFinite(lng) && Number.isFinite(lat)
  const center = hasPoint ? [lng, lat] : [...XINXIANG_CENTER]

  map = new AMap.Map(mapEl.value, {
    zoom: hasPoint ? 16 : 12,
    center,
    viewMode: '2D',
    mapStyle: 'amap://styles/normal',
  })

  map.on('click', (e) => {
    const { lng, lat } = e.lnglat
    applyPick(lng, lat, null)
    reverseGeocodeToText(lng, lat)
    if (!marker) {
      marker = new AMap.Marker(markerOptions(AMap, lng, lat))
      bindMarkerDragEnd(marker)
      map.add(marker)
    } else {
      marker.setPosition([lng, lat])
    }
  })

  if (hasPoint) {
    marker = new AMap.Marker(markerOptions(AMap, lng, lat))
    bindMarkerDragEnd(marker)
    map.add(marker)
  }

  placeSearch = new AMap.PlaceSearch({
    city: '新乡',
    citylimit: false,
    pageSize: 10,
    pageIndex: 1,
  })

  await nextTick()
  if (document.getElementById(searchInputId)) {
    autoComplete = new AMap.AutoComplete({
      input: searchInputId,
      city: '新乡',
      citylimit: false,
    })
    autoComplete.on('select', (e) => {
      const poi = e?.poi
      if (!poi) return
      const txt = poiToMapText(poi)
      let plng
      let plat
      if (poi.location) {
        const loc = poi.location
        plng = typeof loc.getLng === 'function' ? loc.getLng() : loc.lng
        plat = typeof loc.getLat === 'function' ? loc.getLat() : loc.lat
      }
      if (Number.isFinite(plng) && Number.isFinite(plat)) {
        finishSearchPick(plng, plat, txt)
        return
      }
      const pid = poi.id
      if (pid && placeSearch && typeof placeSearch.getDetails === 'function') {
        placeSearch.getDetails(pid, (status, result) => {
          const pois = result?.poiList?.pois
          if (status === 'complete' && Array.isArray(pois) && pois.length) {
            const p1 = pois[0]
            const loc = p1?.location
            if (loc) {
              const x = typeof loc.getLng === 'function' ? loc.getLng() : loc.lng
              const y = typeof loc.getLat === 'function' ? loc.getLat() : loc.lat
              finishSearchPick(x, y, poiToMapText(p1) || txt)
              return
            }
          }
          emit('warn', '该联想结果无坐标，请改关键词后点「搜索」或直接在地图上点击')
        })
        return
      }
      emit('warn', '该联想结果无坐标，请改关键词后点「搜索」或直接在地图上点击')
    })
  }

  if (typeof ResizeObserver !== 'undefined' && mapEl.value) {
    resizeObs = new ResizeObserver(() => map?.resize?.())
    resizeObs.observe(mapEl.value)
  }
}

function finishSearchPick(lng, lat, mapText) {
  if (!Number.isFinite(lng) || !Number.isFinite(lat) || !map) return
  applyPick(lng, lat, mapText || null)
  const AMap = window.AMap
  if (!marker) {
    marker = new AMap.Marker(markerOptions(AMap, lng, lat))
    bindMarkerDragEnd(marker)
    map.add(marker)
  } else {
    marker.setPosition([lng, lat])
  }
  map.setCenter([lng, lat])
  map.setZoom(16)
}

function runKeywordSearch() {
  const kw = String(searchKeyword.value || '').trim()
  if (!kw || !placeSearch) {
    return
  }
  placeSearch.search(kw, (status, result) => {
    if (status !== 'complete' || !result?.poiList?.pois?.length) {
      emit('warn', '未搜索到地点，请换关键词或直接在地图上点击')
      return
    }
    const p0 = result.poiList.pois[0]
    const loc = p0?.location
    if (!loc) {
      emit('warn', '未解析到坐标，请直接在地图上点击选点')
      return
    }
    const lng = typeof loc.getLng === 'function' ? loc.getLng() : loc.lng
    const lat = typeof loc.getLat === 'function' ? loc.getLat() : loc.lat
    finishSearchPick(lng, lat, poiToMapText(p0))
  })
}

watch(
  () => [props.lngStr, props.latStr],
  () => {
    syncMarkerFromProps()
  },
)

onMounted(() => {
  void nextTick().then(() => initMap())
})

onUnmounted(() => {
  resizeObs?.disconnect()
  resizeObs = null
  if (autoComplete) {
    try {
      autoComplete.off?.('select')
    } catch {
      /* ignore */
    }
    autoComplete = null
  }
  placeSearch = null
  geocoder = null
  marker = null
  if (map) {
    try {
      map.destroy()
    } catch {
      /* ignore */
    }
    map = null
  }
})
</script>

<template>
  <div class="mdmp">
    <p v-if="!amapKey" class="mdmp-warn">
      未配置 <code>VITE_AMAP_KEY</code>，无法使用地图选点；请在环境变量中配置 Key 与安全码后再录入配送位置（坐标由选点自动提交保存）。
    </p>
    <template v-else>
      <div class="mdmp-search">
        <input
          :id="searchInputId"
          v-model="searchKeyword"
          type="text"
          class="mdmp-search-input"
          placeholder="搜索地点（联想或输入后点搜索），如：宝龙城市广场 新乡"
          autocomplete="off"
          @keydown.enter.prevent="runKeywordSearch"
        />
        <button type="button" class="mdmp-search-btn" @click="runKeywordSearch">搜索</button>
      </div>
      <p class="mdmp-hint">
        选用联想结果或「搜索」第一条 POI；也可<strong>点击地图</strong>、<strong>拖动标记</strong>微调。坐标系为 GCJ-02（高德）。
      </p>
      <div ref="mapEl" class="mdmp-map" />
    </template>
  </div>
</template>

<style scoped>
.mdmp {
  margin-bottom: 0.75rem;
}
.mdmp-warn {
  margin: 0 0 0.75rem;
  padding: 0.75rem 1rem;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  line-height: 1.5;
}
.mdmp-warn code {
  font-size: 12px;
}
.mdmp-search {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.mdmp-search-input {
  flex: 1;
  min-width: 200px;
  box-sizing: border-box;
  padding: 0.55rem 0.65rem;
  font-size: 14px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  font-family: inherit;
}
.mdmp-search-btn {
  padding: 0.55rem 1rem;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: #0e5a44;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  flex-shrink: 0;
}
.mdmp-search-btn:hover {
  background: #0c4d3a;
}
.mdmp-hint {
  margin: 0 0 0.5rem;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}
.mdmp-map {
  width: 100%;
  height: min(280px, 42vh);
  min-height: 200px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}
</style>
