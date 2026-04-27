<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { RefreshCw, ChevronRight, MapPin, UserMinus, Utensils } from 'lucide-vue-next'
import { useDeliveryRegionMapOverview } from '../../composables/useDeliveryRegionMapOverview.js'
import DeliveryOverviewMap from './DeliveryOverviewMap.vue'
import { UNASSIGNED_AREA_LABEL } from '../../utils/regionAssignment.js'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const router = useRouter()

const dashboardStats = ref([])
const dashboardStatsLoading = ref(false)

async function fetchDashboardSummary() {
  if (!adminAccessToken.value) return
  dashboardStatsLoading.value = true
  try {
    const d = await apiJson('/api/admin/dashboard-summary', {}, { auth: true })
    const tl = Number(d?.today_leave_members) || 0
    const tp = Number(d?.today_meals_to_prepare) || 0
    const nl = Number(d?.tomorrow_leave_members) || 0
    const np = Number(d?.tomorrow_meals_to_prepare) || 0
    dashboardStats.value = [
      {
        label: '今日请假会员',
        value: tl,
        unit: '个',
        icon: UserMinus,
        bg: '#ffe4e6',
        color: '#e11d48',
        mapFilter: 'today_leave',
      },
      {
        label: '今日需准备餐品',
        value: tp,
        unit: '个',
        icon: Utensils,
        bg: '#d1fae5',
        color: '#059669',
        mapFilter: 'today_prep',
      },
      {
        label: '明日请假会员',
        value: nl,
        unit: '个',
        icon: UserMinus,
        bg: '#ffedd5',
        color: '#ea580c',
        mapFilter: 'tomorrow_leave',
      },
      {
        label: '明日需准备餐品',
        value: np,
        unit: '个',
        icon: Utensils,
        bg: '#e0f2fe',
        color: '#0284c7',
        mapFilter: 'tomorrow_prep',
      },
    ]
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    dashboardStats.value = []
    showToast(e instanceof Error ? e.message : '加载营业概览失败', 'error')
  } finally {
    dashboardStatsLoading.value = false
  }
}

const amapKey = String(import.meta.env.VITE_AMAP_KEY || '').trim()
const amapSecurity = String(import.meta.env.VITE_AMAP_SECURITY_CODE || '').trim()

const {
  loading,
  error,
  load,
  regionsSorted,
  regionColorById,
  memberPoints,
  mapMemberPoints,
  mapFilterKey,
  toggleMapFilter,
  storeAnchor,
  stats,
  membersCountByArea,
} = useDeliveryRegionMapOverview()

function onBizStatClick(mapFilter) {
  if (!mapFilter) return
  toggleMapFilter(mapFilter)
}

function onBizStatKeydown(e, mapFilter) {
  if (e.key !== 'Enter' && e.key !== ' ') return
  e.preventDefault()
  onBizStatClick(mapFilter)
}

const showDeliveryMetrics = computed(() => {
  if (error.value) return false
  if (loading.value && !regionsSorted.value.length) return false
  return true
})

const regionRows = computed(() =>
  regionsSorted.value.map((r) => ({
    ...r,
    color: regionColorById.value[r.id] || '#94a3b8',
    memberCount: membersCountByArea.value[r.name] || 0,
  })),
)

const unassignedMemberCount = computed(() => membersCountByArea.value[UNASSIGNED_AREA_LABEL] || 0)

onMounted(() => {
  void load()
  void fetchDashboardSummary()
})
</script>

<template>
  <section class="dro-panel">
    <header class="dro-head">
      <div class="dro-title">
        <MapPin :size="20" class="dro-title-icon" aria-hidden="true" />
        <div>
          <h3 class="dro-h">配送区域总览</h3>
          <p class="dro-sub">
            下方四张卡片可点击筛选地图标点（再点一次取消）；默认不显示「暂停配送」会员坐标；玫红点为今日请假、橙点为仅明日请假，绿/黄仍为今日是否已送达
          </p>
        </div>
      </div>
      <div class="dro-actions">
        <button type="button" class="dro-btn-ghost" :disabled="loading" @click="load()">
          <RefreshCw :size="16" :class="{ 'dro-spin': loading }" />
          刷新
        </button>
        <button type="button" class="dro-btn-link" @click="router.push({ name: 'store-config' })">
          门店配置 <ChevronRight :size="14" />
        </button>
        <button type="button" class="dro-btn-link" @click="router.push({ name: 'regions' })">
          管理片区 <ChevronRight :size="14" />
        </button>
      </div>
    </header>

    <p v-if="dashboardStatsLoading" class="dro-loading">正在加载营业概览…</p>
    <p v-else-if="!dashboardStats.length" class="dro-loading">暂无营业概览数据，配送地图仍可查看。</p>

    <div
      v-if="
        (!dashboardStatsLoading && dashboardStats.length) || showDeliveryMetrics
      "
      class="dro-stats dro-stats--band"
    >
      <template v-if="!dashboardStatsLoading && dashboardStats.length">
        <div
          v-for="(s, i) in dashboardStats"
          :key="'biz-' + i"
          class="dro-stat dro-stat--biz dro-stat--clickable"
          :class="{ 'dro-stat--filter-on': mapFilterKey === s.mapFilter }"
          role="button"
          tabindex="0"
          :aria-pressed="mapFilterKey === s.mapFilter ? 'true' : 'false'"
          :aria-label="(s.label || '') + '，点击筛选地图'"
          @click="onBizStatClick(s.mapFilter)"
          @keydown="onBizStatKeydown($event, s.mapFilter)"
        >
          <span class="dro-stat-ico" :style="{ backgroundColor: s.bg, color: s.color }">
            <component :is="s.icon" :size="16" aria-hidden="true" />
          </span>
          <div class="dro-stat-body">
            <span class="dro-stat-val">
              {{ s.value }}<small>{{ s.unit }}</small>
            </span>
            <span class="dro-stat-label">{{ s.label }}</span>
          </div>
        </div>
      </template>

      <template v-if="showDeliveryMetrics">
        <div class="dro-stat">
          <span class="dro-stat-val">{{ stats.total }}</span>
          <span class="dro-stat-label">地图会员（有余额）</span>
        </div>
        <div class="dro-stat dro-stat--ok">
          <span class="dro-stat-val">{{ stats.deliveredToday }}</span>
          <span class="dro-stat-label">今日已送达</span>
        </div>
        <div class="dro-stat dro-stat--warn">
          <span class="dro-stat-val">{{ stats.pendingToday }}</span>
          <span class="dro-stat-label">今日未送达</span>
        </div>
      </template>
    </div>

    <p v-if="loading && !regionsSorted.length" class="dro-loading">加载配送数据…</p>
    <p v-else-if="error" class="dro-error">{{ error }}</p>

    <template v-else-if="showDeliveryMetrics">
      <div class="dro-map-shell">
               <DeliveryOverviewMap
          :amap-key="amapKey"
          :amap-security="amapSecurity"
          :regions-sorted="regionsSorted"
          :region-color-by-id="regionColorById"
          :member-points="mapMemberPoints"
          :store-anchor="storeAnchor"
        />
        <div class="dro-float-legends" aria-label="地图图例">
          <div class="dro-legend-card dro-legend-card--float">
            <h4 class="dro-legend-h">会员图钉颜色（今日送达）</h4>
            <ul class="dro-legend-list dro-legend-list--compact">
              <li><span class="dro-dot" style="background: #dc2626" />门店位置（后台「门店配置」坐标）</li>
              <li><span class="dro-dot" style="background: #e11d48" />今日请假（配送日缺席）</li>
              <li><span class="dro-dot" style="background: #ea580c" />仅明日请假（今日不请）</li>
              <li><span class="dro-dot" style="background: #22c55e" />当日已送达（订阅扣次或单次点餐已履约）</li>
              <li><span class="dro-dot" style="background: #eab308" />尚未送达（非请假）</li>
            </ul>
          </div>
          <div class="dro-legend-card dro-legend-card--float">
            <h4 class="dro-legend-h">片区覆盖（档案会员数）</h4>
            <ul class="dro-region-chips dro-region-chips--float">
              <li v-for="row in regionRows" :key="row.id" class="dro-chip">
                <span class="dro-swatch" :style="{ background: row.color }" />
                <span class="dro-chip-name">
                  {{ row.name }}
                  <span
                    v-if="row.is_active === false || row.is_active === 0"
                    class="dro-chip-off"
                  >（停用）</span>
                </span>
                <span class="dro-chip-n">{{ row.memberCount }} 人</span>
              </li>
              <li v-if="unassignedMemberCount" class="dro-chip dro-chip--extra">
                <span class="dro-swatch dro-swatch--dash" />
                <span class="dro-chip-name">{{ UNASSIGNED_AREA_LABEL }}</span>
                <span class="dro-chip-n">{{ unassignedMemberCount }} 人</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.dro-panel {
  margin-top: 0.5rem;
  padding: 1.25rem 1.35rem;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 1.25rem;
}
.dro-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.dro-title {
  display: flex;
  gap: 0.65rem;
  align-items: flex-start;
}
.dro-title-icon {
  color: #0e5a44;
  flex-shrink: 0;
  margin-top: 2px;
}
.dro-h {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  color: #0f172a;
}
.dro-sub {
  margin: 0.25rem 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
  max-width: 36rem;
}
.dro-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.dro-btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  background: #f1f5f9;
  border:1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  font-family: inherit;
}
.dro-btn-ghost:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.dro-btn-link {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 700;
  color: #0e5a44;
  background: transparent;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-family: inherit;
}
.dro-btn-link:hover {
  background: #ecfdf5;
}
.dro-spin {
  animation: dro-spin 0.85s linear infinite;
}
@keyframes dro-spin {
  to {
    transform: rotate(360deg);
  }
}
.dro-loading,
.dro-error {
  margin: 0 0 1rem;
  font-size: 14px;
  color: #64748b;
}
.dro-error {
  color: #b91c1c;
}
.dro-stats {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.65rem;
  margin-bottom: 1rem;
}
.dro-stats--band {
  grid-template-columns: repeat(auto-fill, minmax(124px, 1fr));
}
.dro-stat {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.dro-stat--biz {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.dro-stat-ico {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dro-stat-body {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dro-stat--biz .dro-stat-val {
  font-size: 1.1rem;
  line-height: 1.15;
}
.dro-stat--biz .dro-stat-val small {
  font-size: 10px;
  margin-left: 2px;
  color: #94a3b8;
  font-weight: 700;
}
.dro-stat--biz .dro-stat-label {
  font-size: 10px;
  line-height: 1.25;
  white-space: normal;
}
.dro-stat--clickable {
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.dro-stat--clickable:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
}
.dro-stat--clickable:focus {
  outline: none;
  box-shadow: 0 0 0 2px #fff, 0 0 0 4px #0e5a44;
}
.dro-stat--filter-on {
  border-color: #0e5a44;
  box-shadow: 0 0 0 1px #0e5a44;
  background: #f0fdf4;
}
.dro-stat-val {
  display: block;
  font-size: 1.35rem;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.2;
}
.dro-stat-val small {
  font-size: 11px;
  margin-left: 2px;
  color: #94a3b8;
  font-weight: 700;
}
.dro-stat-label {
  font-size: 11px;
  color: #64748b;
  font-weight: 600;
}
.dro-stat--ok .dro-stat-val {
  color: #15803d;
}
.dro-stat--warn .dro-stat-val {
  color: #b45309;
}
.dro-stat--danger .dro-stat-val {
  color: #b91c1c;
}
.dro-stat--muted .dro-stat-val {
  color: #64748b;
}
.dro-map-shell {
  position: relative;
  width: 100%;
}
.dro-float-legends {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 400;
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: min(308px, calc(100% - 24px));
  max-height: min(calc(76vh - 100px), 720px);
  overflow-y: auto;
  pointer-events: auto;
  -webkit-overflow-scrolling: touch;
}
@media (max-width: 520px) {
  .dro-float-legends {
    width: calc(100% - 20px);
    right: 10px;
    bottom: 10px;
    max-height: 42vh;
  }
}
.dro-legend-card--float {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(226, 232, 240, 0.95);
  box-shadow: 0 12px 36px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(10px);
}
.dro-legend-h {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 800;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.dro-legend-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  font-size: 12px;
  color: #475569;
  line-height: 1.55;
}
.dro-legend-list--compact {
  font-size: 11px;
  line-height: 1.45;
}
.dro-legend-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}
.dro-legend-list--compact li {
  margin-bottom: 4px;
}
.dro-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
  margin-top: 3px;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.12);
}
.dro-region-chips {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow: auto;
}
.dro-region-chips--float {
  max-height: 200px;
}
.dro-chip {
  display: grid;
  grid-template-columns: 14px 1fr auto;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #334155;
}
.dro-swatch {
  width: 12px;
  height: 12px;
  border-radius: 4px;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.08);
}
.dro-swatch--dash {
  background: repeating-linear-gradient(-45deg, #e2e8f0, #e2e8f0 3px, #fff 3px, #fff 6px);
}
.dro-chip-name {
  font-weight: 650;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dro-chip-off {
  font-size: 10px;
  color: #94a3b8;
  font-weight: 600;
  margin-left: 4px;
}
.dro-chip-n {
  font-weight: 700;
  color: #64748b;
  font-variant-numeric: tabular-nums;
}
.dro-chip--extra {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px dashed #e2e8f0;
}
</style>
