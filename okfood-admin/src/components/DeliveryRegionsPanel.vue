<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { MapPin, Trash2, Plus, Save, X } from 'lucide-vue-next'

/** 新乡市城区中心（GCJ-02，与高德一致）；定位失败时使用 */
const XINXIANG_CENTER = [113.9268, 35.303]

const props = defineProps({
  /** (path, init?) => Promise data */
  apiRequest: { type: Function, required: true },
})

const emit = defineEmits(['toast'])

const amapKey = String(import.meta.env.VITE_AMAP_KEY || '').trim()
const amapSecurity = String(import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim()

const regions = ref([])
const couriers = ref([])
const loading = ref(false)
const saving = ref(false)

const mapEl = ref(null)
let map = null
let mouseTool = null
let mapPolygon = null

const editingId = ref(null)
const formName = ref('')
const formCode = ref('')
const formPriority = ref(0)
const formActive = ref(true)
const selectedCourierIds = ref([])
const primaryCourierId = ref('')
const formDrawerOpen = ref(false)
/** 新建流程：已在地图画好多边形、等待抽屉里填名称保存 */
const newRegionAwaitingMeta = ref(false)

function showToast(msg, kind = 'success') {
  emit('toast', msg, kind)
}

async function refreshList() {
  loading.value = true
  try {
    regions.value = await props.apiRequest('/api/admin/delivery-regions')
    const c = await props.apiRequest('/api/admin/couriers')
    couriers.value = Array.isArray(c) ? c : []
  } catch (e) {
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function pathFromPolygonJson(json) {
  if (Array.isArray(json)) return json.map((p) => [Number(p[0]), Number(p[1])])
  if (json && typeof json === 'object' && json.type === 'Polygon' && Array.isArray(json.coordinates?.[0])) {
    return json.coordinates[0].map((p) => [Number(p[0]), Number(p[1])])
  }
  return []
}

function loadAmapScript() {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('无浏览器环境'))
      return
    }
    if (window.AMap) {
      resolve()
      return
    }
    if (amapSecurity) {
      window._AMapSecurityConfig = { securityJsCode: amapSecurity }
    } else {
      delete window._AMapSecurityConfig
    }

    const runLoader = () => {
      window.AMapLoader.load({
        key: amapKey,
        version: '2.0',
        plugins: ['AMap.MouseTool', 'AMap.Geolocation'],
      })
        .then((AMap) => {
          window.AMap = AMap
          resolve()
        })
        .catch((e) => reject(e instanceof Error ? e : new Error(String(e))))
    }

    if (window.AMapLoader) {
      runLoader()
      return
    }
    const s = document.createElement('script')
    s.src = 'https://webapi.amap.com/loader.js'
    s.onload = () => runLoader()
    s.onerror = () => reject(new Error('高德地图 Loader 加载失败'))
    document.head.appendChild(s)
  })
}

async function initMap() {
  if (!amapKey) return
  if (!mapEl.value) {
    await nextTick()
    if (!mapEl.value) return
  }
  try {
    await loadAmapScript()
    if (map) {
      map.destroy()
      map = null
    }
    map = new window.AMap.Map(mapEl.value, {
      zoom: 13,
      center: [...XINXIANG_CENTER],
      viewMode: '2D',
      mapStyle: 'amap://styles/normal',
    })
    centerMapToUserOrXinxiang()
  } catch (e) {
    map = null
    const msg = e instanceof Error ? e.message : '地图加载失败'
    showToast(msg, 'error')
    console.error(e)
  }
}

function centerMapToUserOrXinxiang() {
  if (!map || !window.AMap) return
  const AMap = window.AMap
  const fallback = () => {
    map.setCenter([...XINXIANG_CENTER])
    map.setZoom(13)
  }
  AMap.plugin('AMap.Geolocation', () => {
    const geolocation = new AMap.Geolocation({
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 60000,
      convert: true,
      showButton: false,
      showMarker: false,
      showCircle: false,
      panToLocation: false,
      zoomToAccuracy: true,
    })
    geolocation.getCurrentPosition((status, result) => {
      if (status === 'complete' && result?.position) {
        map.setCenter(result.position)
        map.setZoom(Math.max(map.getZoom(), 14))
      } else {
        fallback()
      }
    })
  })
}

function clearMapPolygon() {
  if (mapPolygon && map) {
    map.remove(mapPolygon)
    mapPolygon = null
  }
}

function showPolygonOnMap(path) {
  if (!map || !path.length) return
  clearMapPolygon()
  mapPolygon = new window.AMap.Polygon({
    path: path.map(([lng, lat]) => [lng, lat]),
    strokeColor: '#0e5a44',
    fillColor: '#0e5a44',
    fillOpacity: 0.2,
    strokeWeight: 2,
  })
  map.add(mapPolygon)
  map.setFitView([mapPolygon], false, [40, 40, 40, 40])
}

function startDrawPolygon() {
  if (!amapKey) {
    showToast('请配置 VITE_AMAP_KEY 后重启 npm run dev', 'error')
    return
  }
  if (!map) {
    showToast(
      '地图未就绪。若已配置 Key：请在高德控制台为该 Key 配置域名白名单（含当前地址栏里的主机，如 localhost 与 127.0.0.1 需分别添加），并确认 VITE_AMAP_SECURITY_CODE 与 Key 匹配；仍失败请看控制台报错',
      'error',
    )
    return
  }
  if (editingId.value == null) {
    newRegionAwaitingMeta.value = false
  }
  clearMapPolygon()
  if (mouseTool) {
    mouseTool.close()
    mouseTool = null
  }
  mouseTool = new window.AMap.MouseTool(map)
  mouseTool.polygon({
    strokeColor: '#0e5a44',
    fillColor: '#facc15',
    fillOpacity: 0.25,
    strokeWeight: 2,
  })
  mouseTool.on('draw', (e) => {
    const obj = e.obj
    mapPolygon = obj
    if (mouseTool) {
      mouseTool.close()
      mouseTool = null
    }
    const path = getCurrentPathForSave()
    if (editingId.value == null) {
      if (!path) {
        showToast('区域至少需要三个顶点，请重新绘制', 'error')
        clearMapPolygon()
        return
      }
      newRegionAwaitingMeta.value = true
      formDrawerOpen.value = true
      showToast('请填写区域名称并保存', 'success')
    }
  })
}

function getCurrentPathForSave() {
  if (!mapPolygon) return null
  const path = mapPolygon.getPath()
  if (!path || !path.length) return null
  const coords = path.map((p) => [p.getLng(), p.getLat()])
  if (coords.length >= 2) {
    const a = coords[0]
    const b = coords[coords.length - 1]
    if (a[0] === b[0] && a[1] === b[1]) coords.pop()
  }
  return coords.length >= 3 ? coords : null
}

function resetForm() {
  editingId.value = null
  formName.value = ''
  formCode.value = ''
  formPriority.value = 0
  formActive.value = true
  selectedCourierIds.value = []
  primaryCourierId.value = ''
  newRegionAwaitingMeta.value = false
  clearMapPolygon()
  if (mouseTool) {
    mouseTool.close()
    mouseTool = null
  }
}

function closeFormDrawer() {
  formDrawerOpen.value = false
}

function resumeNewRegionDrawer() {
  if (!newRegionAwaitingMeta.value) return
  formDrawerOpen.value = true
}

function openNewRegion() {
  closeFormDrawer()
  resetForm()
  centerMapToUserOrXinxiang()
  showToast('请在地图上绘制配送范围（沿边界点击，双击结束闭合）', 'success')
  nextTick(() => startDrawPolygon())
}

function selectRegion(r) {
  newRegionAwaitingMeta.value = false
  if (mouseTool) {
    mouseTool.close()
    mouseTool = null
  }
  formDrawerOpen.value = true
  editingId.value = r.id
  formName.value = r.name
  formCode.value = r.code || ''
  formPriority.value = r.priority
  formActive.value = r.is_active !== false
  selectedCourierIds.value = (r.couriers || []).map((c) => c.courier_id)
  const p = (r.couriers || []).find((c) => c.is_primary)
  primaryCourierId.value = p ? p.courier_id : selectedCourierIds.value[0] || ''
  const path = pathFromPolygonJson(r.polygon_json)
  showPolygonOnMap(path)
}

function toggleCourier(id) {
  const i = selectedCourierIds.value.indexOf(id)
  if (i === -1) {
    selectedCourierIds.value = [...selectedCourierIds.value, id]
    if (!primaryCourierId.value) primaryCourierId.value = id
  } else {
    selectedCourierIds.value = selectedCourierIds.value.filter((x) => x !== id)
    if (primaryCourierId.value === id) {
      primaryCourierId.value = selectedCourierIds.value[0] || ''
    }
  }
}

function buildCouriersPayload() {
  return selectedCourierIds.value.map((cid, idx) => ({
    courier_id: cid,
    is_primary: primaryCourierId.value === cid,
    sort_order: idx,
  }))
}

async function saveRegion() {
  const path = getCurrentPathForSave()
  if (!path) {
    showToast('请先在地图上绘制或加载至少三点的多边形', 'error')
    return
  }
  if (!formName.value.trim()) {
    showToast('请填写区域名称', 'error')
    return
  }
  const primaries = buildCouriersPayload().filter((c) => c.is_primary)
  if (primaries.length > 1) {
    showToast('主责配送员只能选一名', 'error')
    return
  }
  saving.value = true
  try {
    const body = {
      name: formName.value.trim(),
      code: formCode.value.trim() || null,
      polygon_json: path,
      priority: Number(formPriority.value) || 0,
      is_active: formActive.value,
      couriers: buildCouriersPayload(),
    }
    if (editingId.value == null) {
      await props.apiRequest('/api/admin/delivery-regions', { method: 'POST', body: JSON.stringify(body) })
      showToast('已创建配送区域')
    } else {
      await props.apiRequest(`/api/admin/delivery-regions/${editingId.value}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      })
      showToast('已更新配送区域')
    }
    await refreshList()
    resetForm()
    closeFormDrawer()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function deleteRegion(r) {
  if (!confirm(`确定删除区域「${r.name}」？`)) return
  try {
    await props.apiRequest(`/api/admin/delivery-regions/${r.id}`, { method: 'DELETE' })
    showToast('已删除')
    if (editingId.value === r.id) {
      resetForm()
      closeFormDrawer()
    }
    await refreshList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

watch(formDrawerOpen, () => {
  nextTick(() => {
    setTimeout(() => map?.resize?.(), 320)
  })
})

onMounted(async () => {
  await refreshList()
  await nextTick()
  await initMap()
})

onUnmounted(() => {
  if (mouseTool) mouseTool.close()
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<template>
  <div class="regions-panel">
    <p v-if="!amapKey" class="regions-hint regions-hint--warn">
      未配置 <code>VITE_AMAP_KEY</code>（及建议的 <code>VITE_AMAP_SECURITY_CODE</code>），无法在地图上绘制；仍可通过接口或 JSON
      维护区域。
    </p>
    <div class="regions-layout">
      <aside class="regions-side">
        <div class="regions-side-head">
          <h3>配送区域</h3>
          <button type="button" class="btn-icon" title="添加区域" @click="openNewRegion">
            <Plus :size="18" />
          </button>
        </div>
        <p v-if="loading" class="regions-muted">加载中…</p>
        <ul v-else class="regions-list">
          <li
            v-for="r in regions"
            :key="r.id"
            :class="{ active: editingId === r.id }"
            @click="selectRegion(r)"
          >
            <span class="regions-li-name">{{ r.name }}</span>
            <span class="regions-li-meta">P{{ r.priority }}{{ r.is_active ? '' : ' · 停用' }}</span>
            <button
              type="button"
              class="btn-icon btn-icon--danger"
              title="删除"
              @click.stop="deleteRegion(r)"
            >
              <Trash2 :size="14" />
            </button>
          </li>
        </ul>
      </aside>
      <div class="regions-main">
        <div
          v-if="newRegionAwaitingMeta && !formDrawerOpen"
          class="regions-map-resume"
        >
          <span>已在地图上框选区域</span>
          <button type="button" class="btn-resume" @click="resumeNewRegionDrawer">
            填写信息并保存
          </button>
        </div>
        <div ref="mapEl" class="regions-map"></div>
      </div>
    </div>

    <Teleport to="body">
      <div
        class="regions-drawer-backdrop"
        :class="{ 'regions-drawer-backdrop--open': formDrawerOpen }"
        aria-hidden="true"
        @click="closeFormDrawer"
      />
      <aside class="regions-drawer" :class="{ 'regions-drawer--open': formDrawerOpen }">
        <div class="regions-drawer-head">
          <h4>{{ editingId == null ? '保存新区域' : '编辑配送区域' }}</h4>
          <button type="button" class="btn-icon" title="关闭" @click="closeFormDrawer">
            <X :size="18" />
          </button>
        </div>
        <div class="regions-drawer-body">
          <div class="regions-form">
            <div class="form-row-2">
              <label class="field">
                <span>名称</span>
                <input v-model="formName" type="text" placeholder="如：东片区" />
              </label>
              <label class="field">
                <span>编码（可选）</span>
                <input v-model="formCode" type="text" placeholder="短码" />
              </label>
            </div>
            <div class="form-row-2">
              <label class="field">
                <span>优先级（越小越优先）</span>
                <input v-model.number="formPriority" type="number" />
              </label>
              <label class="field field-check">
                <input v-model="formActive" type="checkbox" />
                <span>启用</span>
              </label>
            </div>
            <div class="field">
              <span>配送员（多选，单选主责）</span>
              <div class="courier-pick">
                <label v-for="c in couriers" :key="c.courier_id" class="courier-pick-row">
                  <input
                    type="checkbox"
                    :checked="selectedCourierIds.includes(c.courier_id)"
                    @change="toggleCourier(c.courier_id)"
                  />
                  <span>{{ c.courier_id }}{{ c.name ? ` · ${c.name}` : '' }}</span>
                  <input
                    v-if="selectedCourierIds.includes(c.courier_id)"
                    v-model="primaryCourierId"
                    type="radio"
                    :value="c.courier_id"
                    name="primaryCourier"
                  />
                </label>
                <p v-if="!couriers.length" class="regions-muted">暂无配送员数据，请先在后台创建配送员账号</p>
              </div>
            </div>
            <div class="form-actions">
              <button type="button" class="btn-secondary" @click="startDrawPolygon">
                <MapPin :size="16" /> {{ editingId == null ? '重新绘制' : '重绘多边形' }}
              </button>
              <button type="button" class="btn-primary" :disabled="saving" @click="saveRegion">
                <Save :size="16" /> {{ editingId == null ? '创建' : '保存' }}
              </button>
            </div>
          </div>
        </div>
      </aside>
    </Teleport>
  </div>
</template>

<style scoped>
.regions-panel {
  width: 100%;
}
.regions-hint {
  font-size: 13px;
  padding: 10px 14px;
  border-radius: 12px;
  margin-bottom: 1rem;
}
.regions-hint--warn {
  background: #fffbeb;
  color: #92400e;
  border: 1px solid #fde68a;
}
.regions-hint code {
  font-size: 12px;
}
.regions-layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 1.25rem;
  min-height: calc(100vh - 11rem);
  align-items: stretch;
}
@media (max-width: 900px) {
  .regions-layout {
    grid-template-columns: 1fr;
  }
}
.regions-side {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1.25rem;
  padding: 1rem;
  max-height: min(70vh, calc(100vh - 8rem));
  overflow: auto;
}
.regions-side-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}
.regions-side-head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 900;
}
.regions-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.regions-list li {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  border: 1px solid transparent;
}
.regions-list li:hover {
  background: #f8fafc;
}
.regions-list li.active {
  background: #ecfdf5;
  border-color: #a7f3d0;
}
.regions-li-name {
  font-weight: 800;
}
.regions-li-meta {
  font-size: 11px;
  color: #94a3b8;
}
.regions-main {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 11rem);
  min-width: 0;
  position: relative;
}
.regions-map-resume {
  position: absolute;
  z-index: 5;
  left: 50%;
  top: 12px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #e2e8f0;
  border-radius: 999px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  max-width: calc(100% - 24px);
  pointer-events: auto;
}
.btn-resume {
  border: none;
  border-radius: 999px;
  padding: 8px 16px;
  background: #0e5a44;
  color: #fff;
  font-weight: 800;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
}
.btn-resume:hover {
  filter: brightness(1.06);
}
.regions-map {
  flex: 1;
  width: 100%;
  min-height: 480px;
  height: calc(100vh - 12rem);
  border-radius: 1.25rem;
  border: 1px solid #e2e8f0;
  background: #f1f5f9;
}
.regions-drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1090;
  background: rgba(15, 23, 42, 0.25);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
}
.regions-drawer-backdrop--open {
  opacity: 1;
  pointer-events: auto;
}
.regions-drawer {
  position: fixed;
  top: 0;
  right: 0;
  z-index: 1100;
  width: min(420px, 100vw);
  height: 100vh;
  max-height: 100dvh;
  background: #fff;
  box-shadow: -12px 0 40px rgba(15, 23, 42, 0.12);
  transform: translateX(100%);
  transition: transform 0.28s cubic-bezier(0.23, 1, 0.32, 1);
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e2e8f0;
}
.regions-drawer--open {
  transform: translateX(0);
}
.regions-drawer-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}
.regions-drawer-head h4 {
  margin: 0;
  font-size: 1rem;
  font-weight: 900;
  color: #0f172a;
}
.regions-drawer-body {
  flex: 1;
  overflow: auto;
  padding: 1.25rem;
  -webkit-overflow-scrolling: touch;
}
.regions-form {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
}
.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}
@media (max-width: 600px) {
  .form-row-2 {
    grid-template-columns: 1fr;
  }
}
.field span {
  display: block;
  font-size: 12px;
  font-weight: 900;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}
.field input[type='text'],
.field input[type='number'] {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border-radius: 12px;
  border: 2px solid #e2e8f0;
  font-weight: 700;
}
.field-check {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 1.5rem;
}
.field-check span {
  margin: 0;
 text-transform: none;
  font-size: 14px;
  color: #334155;
}
.courier-pick {
  max-height: 160px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 8px;
}
.courier-pick-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 4px 0;
}
.form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 1rem;
}
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 12px;
  border: none;
  background: #0e5a44;
  color: #fff;
  font-weight: 900;
  cursor: pointer;
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-secondary {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 18px;
  border-radius: 12px;
  border: 2px solid #0e5a44;
  background: #fff;
  color: #0e5a44;
  font-weight: 800;
  cursor: pointer;
}
.btn-icon {
  border: none;
  background: #f1f5f9;
  border-radius: 10px;
  padding: 6px;
  cursor: pointer;
  color: #0e5a44;
}
.btn-icon--danger {
  color: #be123c;
  background: #fff1f2;
}
.regions-muted {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}
</style>
