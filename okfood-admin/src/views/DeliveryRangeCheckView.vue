<script setup>
defineOptions({ name: 'DeliveryRangeCheckView' })
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { Copy } from 'lucide-vue-next'
import { apiJson } from '../admin/core.js'
import { loadAmapOnce } from '../utils/amapLoader.js'
import { pathRingFromPolygonJson } from '../utils/polygonPath.js'
import { useToast } from '../composables/useToast.js'
import { REGION_FILL_PALETTE } from '../constants/deliveryRegionMapPalette.js'

const amapKey = String(import.meta.env.VITE_AMAP_KEY || '').trim()
const amapSecurity = String(import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim()

/** 新乡市 GCJ-02 兜底中心 */
const CITY_CENTER = [113.9268, 35.303]
/** 高德输入联想偏好城市（与会员配送地图选点一致） */
const AMAP_SUGGEST_CITY = '新乡'
/** 高德 AutoComplete 绑定的 input id（须页内唯一） */
const ADDRESS_AUTOCOMPLETE_INPUT_ID = 'delivery-range-check-address-ac'

const { showToast } = useToast()

/** @type {import('vue').Ref<object | null>} */
const storeCfg = ref(null)
const regionsSorted = ref([])
const addressInput = ref('')
const checking = ref(false)
const mapLoading = ref(false)
/** @type {import('vue').Ref<object | null>} */
const lastResult = ref(null)
/** 最近一次有效核验坐标（片区重绘后恢复图钉） */
const lastLngLat = ref(null)

const mapEl = ref(null)
/** @type {unknown} */
let map = null
/** @type {unknown[]} */
let regionPolys = []
/** @type {unknown} */
let storeMarker = null
/** @type {unknown} */
let checkMarker = null
let addressPlaceSearch = null
let addressAutoComplete = null

const coordsResolvedSafe = computed(
  () => lastResult.value && lastResult.value.coords_resolved === true,
)

const inRangeComputed = computed(
  () => Boolean(lastResult.value && lastResult.value.in_region === true),
)

const pinSummary = computed(() => {
  const r = lastResult.value
  if (!r || !r.coords_resolved || r.lng == null || r.lat == null) return '在地图上点击以选点核验'
  const dist =
    r.distance_to_store_km != null ? `直线约 ${Number(r.distance_to_store_km).toFixed(1)}km` : '门店未配置坐标'
  if (r.in_region && r.region_name) {
    return `距门店：${dist}（${String(r.region_name)}）`
  }
  return `${r.in_region ? '在服务范围内 — ' : '不在片区内 — '}${dist}`
})

const resultIdleText = '输入地址后点「立即核验」，或直接在地图上选点。'

const resultTag = computed(() => {
  const r = lastResult.value
  if (!r) return { type: 'info', text: '待核验' }
  if (!coordsResolvedSafe.value) {
    return {
      type: 'warning',
      text: r.geocode_failed ? '无法定位' : '未得到坐标',
    }
  }
  return inRangeComputed.value
    ? { type: 'success', text: '可配送' }
    : { type: 'danger', text: '不可配送' }
})

/** 未取得坐标或无结果时用中性底色 */
const resultTone = computed(() => {
  const r = lastResult.value
  if (!r) return 'neutral'
  if (!r.coords_resolved) return 'neutral'
  return r.in_region ? 'in-range' : 'out-range'
})

const detailLabel = computed(() => {
  const r = lastResult.value
  if (!r || !r.coords_resolved) return ''
  return String(r.query_label || '').trim() || '所选位置'
})

const scriptText = computed(() => {
  const r = lastResult.value
  if (!r) {
    return '宝子，您的地址在我们的每日免费配范围内哦，每中午 12 点前可以给您妥投，您可以放心订购周卡/月卡套餐～'
  }
  if (r.message && (!r.coords_resolved || r.geocode_failed)) {
    return String(r.message)
  }
  if (r.in_region) {
    const dist =
      r.distance_to_store_km != null ? `这里距我们门店直线大约 ${Number(r.distance_to_store_km).toFixed(1)} 公里，` : ''
    const area = r.region_name ? `系统显示属于「${String(r.region_name)}」片区，` : ''
    return `您好，${dist}${area}是在我们配置的鲜配范围内的，可以按周卡/月卡正常办理哈～`
  }
  const dist =
    r.distance_to_store_km != null ? `该位置距门店直线约 ${Number(r.distance_to_store_km).toFixed(1)} 公里，` : ''
  return `您好，${dist}目前不在我们后台划定的配送片区里，暂时没法走日常配送到家。建议看看到店自提，或请负责人调整片区后再帮您办理～`
})

function storePinContent() {
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="27" height="32" viewBox="0 0 38 46">' +
    '<path fill="#059669" stroke="#ffffff" stroke-width="2.2" stroke-linejoin="round" ' +
    'd="M19 3C11.8 3 6 8.5 6 15.2c0 7.2 11.2 23.5 13 25.8 1.8-2.3 13-18.6 13-25.8C32 8.5 26.2 3 19 3z"/>' +
    '<text x="19" y="19" text-anchor="middle" fill="#ffffff" font-size="12" font-weight="700" ' +
    "font-family=\"system-ui,sans-serif\">店</text></svg>"
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`
}

function clearRegionPolys() {
  if (!map) return
  for (const p of regionPolys) {
    try {
      map.remove(p)
    } catch {
      /* ignore */
    }
  }
  regionPolys = []
  if (storeMarker) {
    try {
      map.remove(storeMarker)
    } catch {
      /* ignore */
    }
    storeMarker = null
  }
  if (checkMarker) {
    try {
      map.remove(checkMarker)
    } catch {
      /* ignore */
    }
    checkMarker = null
  }
}

function restoreConsultPinIfAny(AMap) {
  const p = lastLngLat.value
  if (
    map &&
    p &&
    typeof p.lng === 'number' &&
    typeof p.lat === 'number' &&
    Number.isFinite(p.lng) &&
    Number.isFinite(p.lat)
  ) {
    syncCheckMarker(AMap, p.lng, p.lat)
  }
}

function drawOverlays(AMap) {
  if (!map) return
  clearRegionPolys()
  const fitList = []
  /** 与营业概览相同色板顺序；避免 hsl 低亮度在地图上显脏、发黑 */
  let paletteIdx = 0
  for (const r of regionsSorted.value) {
    const path = pathRingFromPolygonJson(r.polygon_json)
    if (path.length < 3) continue
    const inactive = r.is_active === false || r.is_active === 0
    const fill = REGION_FILL_PALETTE[paletteIdx % REGION_FILL_PALETTE.length]
    paletteIdx += 1
    const poly = new AMap.Polygon({
      path,
      strokeColor: fill,
      fillColor: fill,
      fillOpacity: inactive ? 0.06 : 0.2,
      strokeOpacity: inactive ? 0.35 : 0.88,
      strokeWeight: inactive ? 1 : 1.5,
      zIndex: 10,
    })
    map.add(poly)
    regionPolys.push(poly)
    fitList.push(poly)
  }
  const sc = storeCfg.value
  const slng = sc?.store_lng != null ? Number(sc.store_lng) : NaN
  const slat = sc?.store_lat != null ? Number(sc.store_lat) : NaN
  if (Number.isFinite(slng) && Number.isFinite(slat)) {
    const sicon = new AMap.Icon({
      size: new AMap.Size(27, 32),
      image: storePinContent(),
      imageSize: new AMap.Size(27, 32),
    })
    const title = (typeof sc?.store_name === 'string' && sc.store_name.trim()) || '门店'
    storeMarker = new AMap.Marker({
      position: [slng, slat],
      icon: sicon,
      title,
      zIndex: 200,
      anchor: 'bottom-center',
    })
    map.add(storeMarker)
    fitList.push(storeMarker)
  }
  if (fitList.length) {
    try {
      map.setFitView(fitList, false, [48, 48, 48, 48], 18)
    } catch {
      map.setCenter([...CITY_CENTER])
      map.setZoom(12)
    }
  } else {
    map.setCenter([...CITY_CENTER])
    map.setZoom(12)
  }
  restoreConsultPinIfAny(AMap)
}

/** 高德 AutoComplete：输入小区/关键字即联想 POI，选中后写入输入框并按坐标核验 */
function disposeAddressAutocomplete() {
  if (addressAutoComplete && typeof addressAutoComplete.destroy === 'function') {
    try {
      addressAutoComplete.destroy()
    } catch {
      /* ignore */
    }
  }
  addressAutoComplete = null
  addressPlaceSearch = null
}

/** @returns {{ lng: number, lat: number }} */
function parseLngLatFromPoi(poi) {
  const loc = poi?.location
  if (!loc) return { lng: NaN, lat: NaN }
  const lng = typeof loc.getLng === 'function' ? Number(loc.getLng()) : Number(loc.lng)
  const lat = typeof loc.getLat === 'function' ? Number(loc.getLat()) : Number(loc.lat)
  return { lng, lat }
}

function displayLabelFromPoi(poi) {
  if (!poi) return ''
  const nm = String(poi.name ?? '').trim()
  if (nm) return nm
  return String(poi.address ?? poi.district ?? '').trim().slice(0, 120)
}

/**
 * @param {*} AMap window.AMap
 */
async function setupAddressAutocomplete(AMap) {
  disposeAddressAutocomplete()
  if (!amapKey || !AMap) return

  await new Promise((resolve) => {
    AMap.plugin(['AMap.AutoComplete', 'AMap.PlaceSearch'], resolve)
  })
  await nextTick()
  if (!document.getElementById(ADDRESS_AUTOCOMPLETE_INPUT_ID)) {
    await nextTick()
  }
  if (!document.getElementById(ADDRESS_AUTOCOMPLETE_INPUT_ID)) return

  addressPlaceSearch = new AMap.PlaceSearch({
    city: AMAP_SUGGEST_CITY,
    citylimit: false,
    pageSize: 15,
    pageIndex: 1,
  })

  addressAutoComplete = new AMap.AutoComplete({
    input: ADDRESS_AUTOCOMPLETE_INPUT_ID,
    city: AMAP_SUGGEST_CITY,
    citylimit: false,
  })

  addressAutoComplete.on('select', (evt) => {
    const poi = evt?.poi
    if (!poi) return

    /** 选中后直接触发核验的标签（回传后端写入 query_label） */
    let chosenLabel = displayLabelFromPoi(poi)
    if (!chosenLabel) {
      chosenLabel = String(addressInput.value || '').trim()
    } else {
      addressInput.value = chosenLabel
    }

    const finishConsult = (lng, lat, label) => {
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        void runConsult(
          { lng, lat },
          { queryLabel: String(label || chosenLabel || '').trim() },
        )
        return
      }
      void runConsult(null)
      if (!(chosenLabel.length > 0)) {
        showToast('未能解析该地点坐标，请换关键字或地图上点选', 'error')
      }
    }

    const { lng, lat } = parseLngLatFromPoi(poi)
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      finishConsult(lng, lat, chosenLabel)
      return
    }

    const pid = poi.id
    if (pid && addressPlaceSearch?.getDetails) {
      addressPlaceSearch.getDetails(pid, (status, result) => {
        const list = result?.poiList?.pois
        if (status === 'complete' && Array.isArray(list) && list.length > 0) {
          const p1 = list[0]
          const loc = p1?.location
          if (loc) {
            const lx =
              typeof loc.getLng === 'function'
                ? Number(loc.getLng())
                : Number(loc.lng)
            const ly =
              typeof loc.getLat === 'function'
                ? Number(loc.getLat())
                : Number(loc.lat)
            finishConsult(lx, ly, displayLabelFromPoi(p1) || chosenLabel)
            return
          }
        }
        finishConsult(NaN, NaN, chosenLabel)
      })
      return
    }

    finishConsult(NaN, NaN, chosenLabel)
  })
}

async function initMap(AMap) {
  if (!mapEl.value || !AMap) return
  mapLoading.value = true
  try {
    if (map) {
      try {
        map.destroy()
      } catch {
        /* ignore */
      }
      map = null
    }
    map = new AMap.Map(mapEl.value, {
      zoom: 12,
      center: [...CITY_CENTER],
      viewMode: '2D',
      mapStyle: 'amap://styles/normal',
    })
    drawOverlays(AMap)
    map.on('click', (e) => {
      const ll = e.lnglat
      const lng = ll.getLng()
      const lat = ll.getLat()
      addressInput.value = '地图选点'
      void runConsult({ lng, lat })
    })
  } catch (e) {
    console.error(e)
    showToast(e instanceof Error ? e.message : '地图加载失败', 'error')
  } finally {
    mapLoading.value = false
  }
}

function syncCheckMarker(AMap, lng, lat) {
  if (!map) return
  if (!checkMarker) {
    checkMarker = new AMap.Marker({
      position: [lng, lat],
      title: pinSummary.value,
      zIndex: 180,
      anchor: 'bottom-center',
    })
    map.add(checkMarker)
  } else {
    try {
      checkMarker.setPosition([lng, lat])
      checkMarker.setTitle(pinSummary.value)
    } catch {
      /* ignore */
    }
  }
}

watch(
  () => [regionsSorted.value, storeCfg.value],
  async () => {
    if (!map || !window.AMap) return
    await nextTick()
    drawOverlays(window.AMap)
  },
  { deep: true },
)

async function bootstrap() {
  const [regionsData, cfg] = await Promise.all([
    apiJson('/api/admin/delivery-regions?include_polygon=true', {}, { auth: true }),
    apiJson('/api/admin/store-config', {}, { auth: true }),
  ])
  regionsSorted.value = Array.isArray(regionsData)
    ? regionsData.slice().sort((a, b) => {
        const pa = Number(a.priority) || 0
        const pb = Number(b.priority) || 0
        return pa !== pb ? pa - pb : Number(a.id) - Number(b.id)
      })
    : []
  storeCfg.value = cfg && typeof cfg === 'object' ? cfg : {}
}

async function runConsult(coordsOrNull, options = {}) {
  const labelHint = typeof options.queryLabel === 'string' ? options.queryLabel.trim() : ''
  const storeId =
    storeCfg.value && storeCfg.value.store_id != null ? Number(storeCfg.value.store_id) : 1
  /** @type {Record<string, unknown>} */
  let body
  if (coordsOrNull != null) {
    body = {
      location: {
        lng: Number(coordsOrNull.lng),
        lat: Number(coordsOrNull.lat),
      },
    }
    const hint = labelHint || String(addressInput.value || '').trim()
    if (hint && hint !== '地图选点') {
      body.address_keyword = hint
    }
  } else {
    body = { address_keyword: String(addressInput.value || '').trim() }
  }
  checking.value = true
  try {
    const url = `/api/admin/delivery-region/consult?store_id=${encodeURIComponent(String(storeId))}`
    /** @type {Record<string, unknown>} */
    const data = await apiJson(url, { method: 'POST', body: JSON.stringify(body) }, { auth: true })
    lastResult.value = data
    if (
      data.coords_resolved &&
      data.lng != null &&
      data.lat != null &&
      typeof data.lng === 'number' &&
      typeof data.lat === 'number'
    ) {
      lastLngLat.value = { lng: data.lng, lat: data.lat }
      await nextTick()
      if (window.AMap && map) {
        syncCheckMarker(window.AMap, data.lng, data.lat)
        try {
          map.setZoomAndCenter(15, [data.lng, data.lat], true)
        } catch {
          /* ignore */
        }
      }
    } else {
      lastLngLat.value = null
    }
  } catch (e) {
    showToast(e instanceof Error ? e.message : '核验失败', 'error')
  } finally {
    checking.value = false
  }
}

function onVerifyClick() {
  const q = String(addressInput.value || '').trim()
  if (!q || q === '地图选点') {
    showToast('请输入小区、道路或建筑名称后再核验', 'error')
    return
  }
  void runConsult(null)
}

function onCopyScript() {
  const t = scriptText.value || ''
  if (!t.trim()) return
  void navigator.clipboard.writeText(t).then(
    () => showToast('已复制话术', 'success'),
    async () => {
      try {
        const ta = document.createElement('textarea')
        ta.value = t
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        showToast('已复制话术', 'success')
      } catch {
        showToast('复制失败，请长按手工复制', 'error')
      }
    },
  )
}

onMounted(async () => {
  try {
    await bootstrap()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '加载片区失败', 'error')
  }
  await nextTick()
  if (!amapKey) return
  try {
    const AMap = await loadAmapOnce(amapKey, amapSecurity, [])
    try {
      await setupAddressAutocomplete(AMap)
    } catch (e1) {
      console.error(e1)
      showToast(
        e1 instanceof Error
          ? e1.message
          : '地址联想初始化失败；可继续手动输入或地图选点核验',
        'error',
      )
    }
    await initMap(AMap)
  } catch (e) {
    console.error(e)
    showToast(e instanceof Error ? e.message : '地图加载失败', 'error')
  }
})

onUnmounted(() => {
  disposeAddressAutocomplete()
  if (map) {
    try {
      map.destroy()
    } catch {
      /* ignore */
    }
    map = null
  }
  regionPolys = []
  storeMarker = null
  checkMarker = null
})
</script>

<template>
  <section class="mkt-page drc-page tab-content animate-up page-content-shell">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">配送管理</p>
        <h1 class="mkt-title">配送资质检验</h1>
        <p class="mkt-intro">
          输入小区或地标，或在地图上点选。结论只看「配送区域管理」里启用的片区，与承运方无关。
        </p>
      </div>
    </header>

    <div class="drc-workspace">
      <aside class="mkt-card drc-panel">
        <header class="mkt-card__head">
          <span class="mkt-card__title">地址核验</span>
          <span class="mkt-card__hint">关键字或地图选点</span>
        </header>

        <div class="drc-search">
          <label class="drc-label" :for="ADDRESS_AUTOCOMPLETE_INPUT_ID">意向配送地址</label>
          <p v-if="amapKey" class="drc-hint">输入后从联想里选择小区或地标，会自动核验。</p>
          <div class="drc-search-row">
            <el-input
              :id="ADDRESS_AUTOCOMPLETE_INPUT_ID"
              v-model="addressInput"
              placeholder="示例：市人民医院、大桥…"
              clearable
              autocomplete="off"
              spellcheck="false"
              @keydown.enter.prevent="onVerifyClick"
            />
            <el-button type="primary" round :loading="checking" @click="onVerifyClick">立即核验</el-button>
          </div>
          <el-alert
            v-if="!amapKey"
            class="drc-alert"
            type="warning"
            :closable="false"
            show-icon
            title="未配置高德 Key"
            description="只能按关键字核验。在 .env.local 填写 VITE_AMAP_KEY 后可显示地图和地址联想。"
          />
        </div>

        <div class="drc-result" :class="resultTone">
          <div class="drc-result__head">
            <el-tag round effect="light" :type="resultTag.type">{{ resultTag.text }}</el-tag>
            <span v-if="inRangeComputed && lastResult?.region_name" class="drc-result__region">
              {{ lastResult.region_name }}
            </span>
          </div>
          <div class="drc-result__body">
            <template v-if="!lastResult">
              {{ resultIdleText }}
            </template>
            <template v-else-if="!coordsResolvedSafe">
              {{ lastResult.message || '暂无法判定，建议在地图上精确选点后重试。' }}
            </template>
            <template v-else-if="lastResult.in_region">
              <p>
                该意向位置「<strong>{{ detailLabel }}</strong>」<template
                  v-if="lastResult.distance_to_store_km != null"
                >距门店直线约 <strong>{{ Number(lastResult.distance_to_store_km).toFixed(1) }} km</strong>，</template>落在启用片区「<strong>{{ lastResult.region_name || '已配置片区' }}</strong>」内，可按常规会员配送办理。
              </p>
            </template>
            <template v-else>
              <p>
                该意向位置「<strong>{{ detailLabel }}</strong>」<template
                  v-if="lastResult.distance_to_store_km != null"
                >距门店直线约 <strong>{{ Number(lastResult.distance_to_store_km).toFixed(1) }} km</strong>，</template><strong>未命中</strong>任一启用配送片区，当前视为不可配送（与承运方无关）。
              </p>
            </template>
          </div>
        </div>

        <div class="drc-script">
          <div class="drc-script__head">
            <span class="drc-script__label">推荐沟通话术</span>
            <el-button round class="drc-copy" @click="onCopyScript">
              <Copy :size="14" stroke-width="2.2" aria-hidden="true" />
              复制话术
            </el-button>
          </div>
          <p class="drc-script__text">{{ scriptText }}</p>
        </div>

        <div class="drc-notes">
          <span class="drc-notes__title">作业要求</span>
          <ul class="drc-notes__list">
            <li>
              <span class="drc-notes__mark" aria-hidden="true">✓</span>
              <span><strong>精确定位：</strong>优先引导客户在地图上选点核对，谨防重名小区导致编码偏差。</span>
            </li>
            <li>
              <span class="drc-notes__mark" aria-hidden="true">✓</span>
              <span><strong>判定口径：</strong>仅依据「配送区域管理」启用多边形；与第三方承运无关。</span>
            </li>
            <li>
              <span class="drc-notes__mark" aria-hidden="true">✓</span>
              <span><strong>开卡留痕：</strong>保存变更前核对会员手机号、备注是否与开卡工单一致。</span>
            </li>
          </ul>
        </div>
      </aside>

      <section class="mkt-card drc-map-card">
        <header class="mkt-card__head">
          <span class="mkt-card__title">判定沙盘</span>
          <span class="mkt-card__hint">{{ pinSummary }}</span>
        </header>
        <div class="drc-map-surface">
          <div v-show="mapLoading" class="drc-map-cover">地图加载中…</div>
          <div ref="mapEl" class="drc-map-mount" aria-label="高德地图选点核验" />
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
/* 全高双栏：页头与玻璃卡沿用 mkt-page，地图区吃满剩余视口 */
.drc-page.mkt-page {
  max-width: none;
  width: 100%;
  flex: 1;
  min-height: 0;
  gap: 0.85rem;
}

.drc-page.page-content-shell {
  padding-bottom: 0;
}

.drc-workspace {
  display: grid;
  grid-template-columns: minmax(320px, 400px) minmax(0, 1fr);
  gap: 0.9rem;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.drc-panel {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 0;
  overflow: auto;
}

.drc-panel > .mkt-card__head,
.drc-map-card > .mkt-card__head {
  margin-bottom: 0;
}

.drc-search {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.drc-label {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.drc-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}

.drc-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.drc-search-row :deep(.el-input) {
  flex: 1;
  min-width: 0;
}

.drc-search-row :deep(.el-input__wrapper) {
  min-height: 40px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}

.drc-search-row :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.drc-search-row :deep(.el-button) {
  height: 40px;
  padding: 0 18px;
  font-weight: 800;
  flex-shrink: 0;
}

.drc-alert {
  margin-top: 0.35rem;
  border-radius: 14px;
}

.drc-result {
  border-radius: 16px;
  padding: 14px;
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.8);
  border-color: rgba(15, 23, 42, 0.06);
  color: #334155;
}

.drc-result.in-range {
  background: #ecfdf5;
  border-color: #bbf7d0;
  color: #166534;
}

.drc-result.out-range {
  background: #fef2f2;
  border-color: #fecaca;
  color: #991b1b;
}

.drc-result__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.drc-result__region {
  font-size: 12px;
  font-weight: 700;
  color: inherit;
}

.drc-result__body {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.55;
}

.drc-result__body p {
  margin: 0;
}

.drc-script {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border-radius: 16px;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.drc-script__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.drc-script__label {
  font-size: 13px;
  font-weight: 800;
  color: #1d1f21;
}

.drc-copy {
  font-weight: 700;
}

.drc-copy :deep(svg) {
  margin-right: 4px;
}

.drc-script__text {
  margin: 0;
  padding-left: 10px;
  border-left: 3px solid color-mix(in srgb, var(--el-color-primary) 55%, #fff);
  font-size: 14px;
  font-weight: 650;
  line-height: 1.6;
  color: #1d1f21;
}

.drc-notes {
  margin-top: auto;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.drc-notes__title {
  font-size: 12px;
  font-weight: 800;
  color: #8b949e;
}

.drc-notes__list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.drc-notes__list li {
  display: flex;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  color: #5c6670;
}

.drc-notes__list strong {
  color: #334155;
  font-weight: 800;
}

.drc-notes__mark {
  flex-shrink: 0;
  color: var(--el-color-primary);
  font-weight: 800;
}

.drc-map-card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
  min-height: 0;
}

.drc-map-card .mkt-card__hint {
  max-width: 62%;
  text-align: right;
  line-height: 1.4;
}

.drc-map-surface {
  position: relative;
  flex: 1;
  width: 100%;
  min-height: 280px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: #f1f5f9;
  overflow: hidden;
}

.drc-map-mount {
  width: 100%;
  height: 100%;
  min-height: 280px;
}

.drc-map-cover {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(8px);
  font-weight: 700;
  font-size: 13px;
  color: #5c6670;
}

@media (max-width: 900px) {
  .drc-workspace {
    grid-template-columns: 1fr;
  }

  .drc-panel {
    overflow: visible;
  }

  .drc-map-card .mkt-card__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .drc-map-card .mkt-card__hint {
    max-width: none;
    text-align: left;
  }

  .drc-map-surface,
  .drc-map-mount {
    min-height: 360px;
  }

  .drc-search-row {
    flex-wrap: wrap;
  }

  .drc-search-row :deep(.el-button) {
    width: 100%;
  }
}
</style>
