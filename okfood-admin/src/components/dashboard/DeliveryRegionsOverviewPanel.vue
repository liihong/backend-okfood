<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  RefreshCw,
  CalendarMinus,
  Utensils,
  Users,
  Info,
  TrendingUp,
  CalendarClock,
} from 'lucide-vue-next'
import { useDeliveryRegionMapOverview } from '../../composables/useDeliveryRegionMapOverview.js'
import DeliveryOverviewMap from './DeliveryOverviewMap.vue'
import { UNASSIGNED_AREA_LABEL } from '../../utils/regionAssignment.js'
import { apiJson, adminAccessToken, adminKind, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const dashboardStats = ref([])
const dashboardStatsLoading = ref(false)
/** @type {import('vue').Ref<string>} */
const summaryAnchorDate = ref('')
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const summaryMeta = ref(null)
/** 与智能配送大表同源拆分（/api/admin/delivery-sheet），锚定日与营业概览一致
 * @type {import('vue').Ref<{ total: number, delivery: number, pickup: number } | null>}
 */
const sheetPrepBreakdown = ref(null)
/** 锚定日「次日」大表拆分（明日需备餐的配送/自提）
 * @type {import('vue').Ref<{ total: number, delivery: number, pickup: number } | null>}
 */
const tomorrowPrepBreakdown = ref(null)

const summaryIsLiveToday = computed(() => {
  const m = summaryMeta.value
  if (!m) return true
  return String(m.business_anchor_date || '') === String(m.shanghai_today || '')
})

/** 营业锚定日 → YYYY/MM/DD，与日期选择器、概览接口一致 */
const businessAnchorDateDisplay = computed(() => {
  const raw = summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value
  if (raw == null || String(raw).trim() === '') return ''
  const s = String(raw).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (m) return `${m[1]}/${m[2]}/${m[3]}`
  return s
})

/** 锚定日的次日（概览中的「明日」），YYYY/MM/DD；按日历日 +1，用 UTC 避免本机时区偏移 */
const businessAnchorTomorrowDisplay = computed(() => {
  const raw = summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value
  if (raw == null || String(raw).trim() === '') return ''
  const s = String(raw).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + 1)
  const y = dt.getUTCFullYear()
  const mo = String(dt.getUTCMonth() + 1).padStart(2, '0')
  const d = String(dt.getUTCDate()).padStart(2, '0')
  return `${y}/${mo}/${d}`
})

/** 请假卡标题：有锚定日时为「2026/05/18请假总览」，加载前仍为「今日请假总览」 */
const leaveOverviewTitle = computed(() => {
  const d = businessAnchorDateDisplay.value
  return d ? `${d} - 请假总览` : '今日请假总览'
})

/** 备餐 / 到期卡标题：同一锚定日前缀 */
const mealPrepTitle = computed(() => {
  const d = businessAnchorDateDisplay.value
  return d ? `${d} - 需备餐品` : '今日需备餐品'
})
const expiryActivityTitle = computed(() => {
  const d = businessAnchorDateDisplay.value
  return d ? `${d} - 到期与活跃` : '到期与活跃'
})

/** 续费与备餐卡：展示「明日」日期（锚定日+1 天），与概览中明日备餐等指标同日 */
const renewalPrepTitle = computed(() => {
  const t = businessAnchorTomorrowDisplay.value
  return t ? `${t} - 续费与备餐` : '续费与备餐'
})

/** ISO 日历日 YYYY-MM-DD 的次日（UTC，与业务日一致） */
function addOneDayIso(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso).trim().slice(0, 10))
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + 1)
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(
    dt.getUTCDate(),
  ).padStart(2, '0')}`
}

/** 解析 delivery-sheet 汇总为总份数 / 配送 / 自提 */
function parseDeliverySheetBreakdown(sh) {
  if (!sh || typeof sh !== 'object') return null
  const hp = Number(sh.home_pending_meal_total) || 0
  const hd = Number(sh.home_delivered_meal_total) || 0
  const pu = Number(sh.pickup_meal_total) || 0
  return { total: hp + hd + pu, delivery: hp + hd, pickup: pu }
}

/** 拉取配送大表汇总行，与 DeliveryView 顶部「后厨需出 / 待送达 / 自提」同一口径 */
async function fetchSheetPrepBreakdowns(anchorIso) {
  sheetPrepBreakdown.value = null
  tomorrowPrepBreakdown.value = null
  if (!adminAccessToken.value || !anchorIso) return
  const day = String(anchorIso).trim().slice(0, 10)
  const nextDay = addOneDayIso(day)
  if (!nextDay) return
  try {
    const qs1 = new URLSearchParams()
    qs1.set('delivery_date', day)
    const qs2 = new URLSearchParams()
    qs2.set('delivery_date', nextDay)
    const [shToday, shTomorrow] = await Promise.all([
      apiJson(`/api/admin/delivery-sheet?${qs1.toString()}`, {}, { auth: true }),
      apiJson(`/api/admin/delivery-sheet?${qs2.toString()}`, {}, { auth: true }),
    ])
    sheetPrepBreakdown.value = parseDeliverySheetBreakdown(shToday)
    tomorrowPrepBreakdown.value = parseDeliverySheetBreakdown(shTomorrow)
  } catch {
    sheetPrepBreakdown.value = null
    tomorrowPrepBreakdown.value = null
  }
}

async function fetchDashboardSummary() {
  if (!adminAccessToken.value) return
  dashboardStatsLoading.value = true
  sheetPrepBreakdown.value = null
  tomorrowPrepBreakdown.value = null
  try {
    const q = summaryAnchorDate.value.trim()
    const qs = q ? `?business_date=${encodeURIComponent(q)}` : ''
    const d = await apiJson(`/api/admin/dashboard-summary${qs}`, {}, { auth: true })
    summaryMeta.value = d
    if (d && typeof d.business_anchor_date === 'string') {
      summaryAnchorDate.value = d.business_anchor_date
    }
    await fetchSheetPrepBreakdowns(
      d && typeof d.business_anchor_date === 'string' ? d.business_anchor_date : '',
    )
    const tl = Number(d?.today_leave_members) || 0
    const tp = Number(d?.today_meals_to_prepare) || 0
    const nl = Number(d?.tomorrow_leave_members) || 0
    const np = Number(d?.tomorrow_meals_to_prepare) || 0
    const te = Number(d?.today_expire_one_unit_members) || 0
    dashboardStats.value = [
      { label: '今日请假会员', value: tl, unit: '人', mapFilter: 'today_leave' },
      { label: '明日请假会员', value: nl, unit: '人', mapFilter: 'tomorrow_leave' },
      { label: '今日需准备餐品', value: tp, unit: '份', mapFilter: 'today_prep' },
      { label: '明日需准备餐品', value: np, unit: '份', mapFilter: 'tomorrow_prep' },
      { label: '今日到期会员', value: te, unit: '人', mapFilter: null },
    ]
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    dashboardStats.value = []
    summaryMeta.value = null
    sheetPrepBreakdown.value = null
    tomorrowPrepBreakdown.value = null
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
  mapMemberPoints,
  storeAnchor,
  stats,
  membersCountByArea,
} = useDeliveryRegionMapOverview()

/** 与 layout 一致：完整店主菜单可见性 */
const showFullAdminMenus = computed(() => {
  const k = adminKind.value
  return k !== 'delivery' && k !== 'system'
})
const showOwnerAdminMenus = computed(() => {
  const k = adminKind.value
  return k !== 'delivery' && k !== 'support' && k !== 'system'
})

function onSummaryDateChange() {
  void fetchDashboardSummary()
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

const regionCoverageRows = computed(() => {
  const rows = regionRows.value
  const extra = unassignedMemberCount.value || 0
  const total = rows.reduce((s, r) => s + r.memberCount, 0) + extra
  const pct = (n) => (total > 0 ? Math.round((n / total) * 100) : 0)
  const out = rows.map((r) => ({
    ...r,
    coveragePercent: pct(r.memberCount),
  }))
  if (extra > 0) {
    out.push({
      id: '__unassigned__',
      name: UNASSIGNED_AREA_LABEL,
      color: '#94a3b8',
      memberCount: extra,
      coveragePercent: pct(extra),
      is_active: true,
    })
  }
  return out
})

/** [0]今日请假 [1]明日请假 [2]今日备餐 [3]明日备餐 */
const summarySlice = computed(() => ({
  todayLeave: Number(dashboardStats.value[0]?.value) || 0,
  tomorrowLeave: Number(dashboardStats.value[1]?.value) || 0,
  todayMeals: Number(dashboardStats.value[2]?.value) || 0,
  tomorrowMeals: Number(dashboardStats.value[3]?.value) || 0,
}))

const expireCount = computed(() => Number(dashboardStats.value[4]?.value) || 0)

/** 备餐卡片「总数」：优先大表停靠点合计（与智能配送页一致），否则回落营业概览 */
const cardPrepTotal = computed(() => {
  if (sheetPrepBreakdown.value != null) return sheetPrepBreakdown.value.total
  return Number(dashboardStats.value[2]?.value) || 0
})

/** 配送=到家待送达+已送达；自提=门店自提分组。优先大表接口，与图1 红框一致 */
const todayMealsDelivery = computed(() => {
  if (sheetPrepBreakdown.value != null) return sheetPrepBreakdown.value.delivery
  const v = summaryMeta.value?.today_meals_delivery
  if (v == null) return null
  return Number(v) || 0
})
const todayMealsPickup = computed(() => {
  if (sheetPrepBreakdown.value != null) return sheetPrepBreakdown.value.pickup
  const v = summaryMeta.value?.today_meals_pickup
  if (v == null) return null
  return Number(v) || 0
})

/** 明日备餐：总份优先大表次日合计，否则营业概览 tomorrow_meals_to_prepare */
const cardTomorrowPrepTotal = computed(() => {
  if (tomorrowPrepBreakdown.value != null) return tomorrowPrepBreakdown.value.total
  return Number(dashboardStats.value[3]?.value) || 0
})

const tomorrowPrepDelivery = computed(() => {
  if (tomorrowPrepBreakdown.value != null) return tomorrowPrepBreakdown.value.delivery
  return null
})
const tomorrowPrepPickup = computed(() => {
  if (tomorrowPrepBreakdown.value != null) return tomorrowPrepBreakdown.value.pickup
  return null
})

const storePinLegendCount = computed(() =>
  storeAnchor.value?.store_lng != null && storeAnchor.value?.store_lat != null ? 1 : 0,
)

/** 勾选时仅显示「门店自提」会员坐标（档案 store_pickup） */
const showSelfPickupPoints = ref(false)
const mapPointsForDisplay = computed(() => {
  const pts = mapMemberPoints.value
  if (!showSelfPickupPoints.value) return pts
  return pts.filter((p) => p.store_pickup === true || p.store_pickup === 1)
})

const refreshBusy = computed(() => dashboardStatsLoading.value || loading.value)

async function onRefreshAll() {
  await Promise.all([fetchDashboardSummary(), load()])
}

onMounted(() => {
  void load()
  void fetchDashboardSummary()
})
</script>

<template>
  <section class="dro-page dro-page--modern">
    <div class="dro-dash-title-row">
      <h2 class="dro-dash-title">配送区域总览</h2>
      <div class="dro-dash-title-actions">
        <button
          type="button"
          class="dro-btn-refresh"
          :disabled="refreshBusy"
          @click="onRefreshAll"
        >
          <RefreshCw :size="15" class="dro-btn-refresh-ico" :class="{ 'dro-btn-refresh-ico--spin': refreshBusy }" />
          数据刷新
        </button>
        <label class="dro-date-inline">
          <span class="dro-sr-only">营业概览锚定日</span>
          <input
            v-model="summaryAnchorDate"
            type="date"
            class="dro-date-inline-input"
            :disabled="dashboardStatsLoading"
            aria-describedby="dro-summary-anchor-hint"
            @change="onSummaryDateChange"
          />
        </label>
      </div>
    </div>
    <span id="dro-summary-anchor-hint" class="dro-sr-only"
      >切换日期将重拉营业概览；地图送达状态仍为服务端当日口径。</span
    >

    <p v-if="summaryMeta?.from_snapshot" class="dro-snapshot-hint">
      已显示归档数据（与智能配送大表口径对齐的首读留存）。
      <template v-if="summaryMeta.snapshot_recorded_at">
        归档时间 {{ summaryMeta.snapshot_recorded_at }}。
      </template>
    </p>

    <p v-if="dashboardStatsLoading" class="dro-loading">正在加载营业概览…</p>
    <p v-else-if="!dashboardStats.length && !loading" class="dro-loading">
      暂无营业概览数据，配送地图仍可查看。
    </p>

    <!-- 四张合并指标卡 -->
    <div
      v-if="(!dashboardStatsLoading && dashboardStats.length) || showDeliveryMetrics"
      class="dro-dash-stat-grid"
    >
      <article
        class="dro-stat-card dro-stat-card--leave"
        :class="{ 'dro-stat-card--historical': !summaryIsLiveToday }"
      >
        <div class="dro-stat-card-top dro-stat-card-top--dense-icon">
          <span class="dro-stat-card-k">{{ leaveOverviewTitle }}</span>
          <CalendarMinus :size="18" class="dro-stat-card-ico" aria-hidden="true" />
        </div>
        <div class="dro-stat-card-metric-wrap dro-stat-card-metric-wrap--lift">
          <div class="dro-stat-card-metric dro-stat-card-metric--leave">
            <span class="dro-stat-card-num dro-stat-card-num--xl">{{ summarySlice.todayLeave }}</span>
            <span class="dro-stat-card-unit dro-stat-card-unit--leave">人</span>
          </div>
        </div>
        <div class="dro-stat-card-foot dro-stat-card-foot--dock">
          <p class="dro-stat-card-foot-caption">
            明日预计请假:
            <span class="dro-stat-card-foot-strong dro-stat-card-foot-strong--tomorrow-leave"
              >{{ summarySlice.tomorrowLeave }}人</span
            >
          </p>
        </div>
      </article>

      <article
        class="dro-stat-card dro-stat-card--meal"
        :class="{ 'dro-stat-card--historical': !summaryIsLiveToday }"
      >
        <div class="dro-stat-card-top dro-stat-card-top--dense-icon">
          <span class="dro-stat-card-k">{{ mealPrepTitle }}</span>
          <Utensils :size="18" class="dro-stat-card-ico dro-stat-card-ico--meal-prep" aria-hidden="true" />
        </div>
        <div class="dro-stat-card-metric-wrap dro-stat-card-metric-wrap--prep-rows">
          <div class="dro-stat-card-prep-row dro-stat-card-prep-row--total dro-stat-card-metric--emerald">
            <span class="dro-stat-card-num dro-stat-card-num--xl">{{ cardPrepTotal }}</span>
            <span class="dro-stat-card-unit dro-stat-card-unit--prep-hero">份</span>
          </div>
          <div class="dro-stat-card-prep-row dro-stat-card-prep-row--split">
            <span class="dro-stat-card-prep-split-chunk"
              >配送<span class="dro-stat-card-prep-split-num">{{
                todayMealsDelivery === null ? '—' : todayMealsDelivery
              }}</span
              >份</span
            >
            <span class="dro-stat-card-prep-split-gap" aria-hidden="true" />
            <span class="dro-stat-card-prep-split-chunk"
              >自提<span class="dro-stat-card-prep-split-num">{{
                todayMealsPickup === null ? '—' : todayMealsPickup
              }}</span
              >份</span
            >
          </div>
        </div>
      </article>

      <article
        class="dro-stat-card dro-stat-card--asset"
        :class="{ 'dro-stat-card--historical': !summaryIsLiveToday }"
      >
        <div class="dro-stat-card-top dro-stat-card-top--asset">
          <div class="dro-stat-card-title-inline">
            <span class="dro-stat-card-k">{{ expiryActivityTitle }}</span>
            <el-tooltip content="仅统计当前账户有余额会员" placement="top" :show-after="250">
              <button type="button" class="dro-stat-card-tip dro-stat-card-tip--soft" aria-label="口径说明">
                <Info :size="14" stroke-width="2.5" aria-hidden="true" />
              </button>
            </el-tooltip>
          </div>
          <Users :size="18" class="dro-stat-card-ico dro-stat-card-ico--blue" aria-hidden="true" />
        </div>
        <div class="dro-stat-card-asset-mid">
          <div class="dro-stat-card-split dro-stat-card-split--around">
            <div class="dro-stat-card-split-cell">
              <p class="dro-stat-card-split-k">今日到期</p>
              <p class="dro-stat-card-split-v dro-stat-card-split-v--lg dro-stat-card-split-v--expire-today">{{ expireCount }}</p>
            </div>
            <span class="dro-stat-card-split-vsep dro-stat-card-split-vsep--refined" aria-hidden="true" />
            <div class="dro-stat-card-split-cell">
              <p class="dro-stat-card-split-k">地图会员</p>
              <p class="dro-stat-card-split-v dro-stat-card-split-v--lg dro-stat-card-split-v--map-total">{{ stats.total }}</p>
            </div>
          </div>
        </div>
      </article>

      <article
        class="dro-stat-card dro-stat-card--renewal-prep"
        :class="{ 'dro-stat-card--historical': !summaryIsLiveToday }"
      >
        <div class="dro-stat-card-top dro-stat-card-top--asset">
          <span class="dro-stat-card-k">{{ renewalPrepTitle }}</span>
          <CalendarClock :size="18" class="dro-stat-card-ico dro-stat-card-ico--amber" aria-hidden="true" />
        </div>
        <div class="dro-stat-card-asset-mid">
          <div class="dro-stat-card-split dro-stat-card-split--around">
            <div class="dro-stat-card-split-cell">
              <p class="dro-stat-card-split-k">今日即将到期会员</p>
              <p class="dro-stat-card-split-vrow">
                <span class="dro-stat-card-split-v dro-stat-card-split-v--lg dro-stat-card-split-v--soon-expire">{{
                  expireCount
                }}</span>
                <span class="dro-stat-card-split-u dro-stat-card-split-u--soon-expire">人</span>
              </p>
            </div>
            <span class="dro-stat-card-split-vsep dro-stat-card-split-vsep--refined" aria-hidden="true" />
            <div class="dro-stat-card-split-cell dro-stat-card-split-cell--tomorrow-prep">
              <p class="dro-stat-card-split-k">明天需准备餐品</p>
              <div
                class="dro-stat-card-metric-wrap dro-stat-card-metric-wrap--prep-rows dro-stat-card-metric-wrap--prep-rows--nested"
              >
                <div class="dro-stat-card-prep-row dro-stat-card-prep-row--total dro-stat-card-metric--nextday-embed">
                  <span class="dro-stat-card-num dro-stat-card-num--nest-xl">{{ cardTomorrowPrepTotal }}</span>
                  <span class="dro-stat-card-unit dro-stat-card-unit--nest-nextday">份</span>
                </div>
                <div class="dro-stat-card-prep-row dro-stat-card-prep-row--split">
                  <span class="dro-stat-card-prep-split-chunk"
                    >配送<span class="dro-stat-card-prep-split-num dro-stat-card-prep-split-num--nest">{{
                      tomorrowPrepDelivery === null ? '—' : tomorrowPrepDelivery
                    }}</span
                    >份</span
                  >
                  <span class="dro-stat-card-prep-split-gap" aria-hidden="true" />
                  <span class="dro-stat-card-prep-split-chunk"
                    >自提<span class="dro-stat-card-prep-split-num dro-stat-card-prep-split-num--nest">{{
                      tomorrowPrepPickup === null ? '—' : tomorrowPrepPickup
                    }}</span
                    >份</span
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <p v-if="loading && !regionsSorted.length" class="dro-loading">加载配送数据…</p>
    <p v-else-if="error" class="dro-error">{{ error }}</p>

    <div v-else-if="showDeliveryMetrics" class="dro-dash-main">
      <div class="dro-map-shell">
        <div class="dro-map-toolbar">
          <div class="dro-map-toolbar-left">
            <span class="dro-map-toolbar-live-dot" aria-hidden="true" />
            <span class="dro-map-toolbar-title">实时地理分布 (LIVE)</span>
          </div>
          <label class="dro-map-pickup-toggle">
            <input v-model="showSelfPickupPoints" type="checkbox" class="dro-map-pickup-cb" />
            <span class="dro-map-pickup-label">自提显示</span>
          </label>
        </div>
        <div class="dro-map-body">
          <DeliveryOverviewMap
            :amap-key="amapKey"
            :amap-security="amapSecurity"
            :regions-sorted="regionsSorted"
            :region-color-by-id="regionColorById"
            :member-points="mapPointsForDisplay"
            :store-anchor="storeAnchor"
          />
          <div class="dro-float-legends dro-float-legends--glass" aria-label="地图图例">
            <div class="dro-legend-card dro-glass-legend">
              <h4 class="dro-legend-h">标注图例</h4>
              <ul class="dro-legend-metrics">
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--store" />
                    <span>门店位置</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ storePinLegendCount }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--leave" />
                    <span>今日请假</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ summarySlice.todayLeave }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--done" />
                    <span>当日已送达</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ stats.deliveredToday }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--pending" />
                    <span>尚未送达</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ stats.pendingToday }}</span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <aside class="dro-rank-card" aria-label="片区覆盖排行">
        <div class="dro-rank-head">
          <h3 class="dro-rank-title">片区覆盖排行</h3>
          <TrendingUp :size="18" class="dro-rank-trend-ico" aria-hidden="true" />
        </div>
        <div class="dro-rank-list custom-scrollbar">
          <div v-for="row in regionCoverageRows" :key="row.id" class="dro-rank-item">
            <div class="dro-rank-item-head">
              <div class="dro-rank-item-meta">
                <p class="dro-rank-name">{{ row.name }}</p>
                <p class="dro-rank-count">
                  {{ row.memberCount }}
                  <span class="dro-rank-count-unit">Member</span>
                </p>
              </div>
              <span class="dro-rank-pct-wrap"
                ><span class="dro-rank-pct">{{ row.coveragePercent }}%</span></span
              >
            </div>
            <div class="dro-rank-bar">
              <div
                class="dro-rank-bar-fill"
                :style="{ width: row.coveragePercent + '%', background: row.color }"
              />
            </div>
          </div>
        </div>
        <!-- <div v-if="showFullAdminMenus" class="dro-rank-actions">
          <router-link v-if="showOwnerAdminMenus" class="dro-rank-btn dro-rank-btn--primary" to="/store-config">
            门店配置
          </router-link>
          <router-link class="dro-rank-btn dro-rank-btn--secondary" to="/regions">片区管理</router-link>
        </div> -->
      </aside>
    </div>
  </section>
</template>

<style scoped>
.dro-page--modern {
  /* 与 main-body 下其他页一致：占满内容区宽度，不额外居中收窄 */
  margin: 0;
  padding: 0 0 2rem;
  background: transparent;
  font-family:
    'Plus Jakarta Sans',
    'Noto Sans SC',
    ui-sans-serif,
    system-ui,
    -apple-system,
    sans-serif;
}

.dro-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.dro-dash-title-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.dro-dash-title {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 900;
  color: #1e293b;
  letter-spacing: -0.02em;
  font-style: italic;
}

.dro-dash-title-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.dro-btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 1rem;
  font-size: 13px;
  font-weight: 800;
  color: #334155;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.dro-btn-refresh:hover:not(:disabled) {
  border-color: #10b981;
}

.dro-btn-refresh:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.dro-btn-refresh-ico--spin {
  animation: dro-spin 0.8s linear infinite;
}

@keyframes dro-spin {
  to {
    transform: rotate(360deg);
  }
}

.dro-date-inline-input {
  padding: 0.45rem 0.85rem;
  border: 1px solid #e2e8f0;
  border-radius: 0.75rem;
  font-size: 13px;
  font-weight: 800;
  color: #334155;
  background: #fff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  font-family: inherit;
}

.dro-date-inline-input:focus {
  outline: none;
  border-color: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}

.dro-snapshot-hint {
  font-size: 13px;
  color: #0369a1;
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 12px;
  padding: 10px 12px;
  margin: 0 0 1rem;
  line-height: 1.45;
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

.dro-dash-stat-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  margin-bottom: 1.5rem;
  align-items: stretch;
}

@media (min-width: 768px) {
  .dro-dash-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1280px) {
  .dro-dash-stat-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.dro-stat-card {
  background: #fff;
  border-radius: 24px;
  padding: 1.5rem;
  border: 1px solid #f1f5f9;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02);
  transition:
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  min-height: 160px;
  box-sizing: border-box;
}

.dro-stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.05);
}

.dro-stat-card--renewal-prep .dro-stat-card-split-k {
  line-height: 1.35;
}

.dro-stat-card-ico--amber {
  color: #fde68a;
}

.dro-stat-card-split-vrow {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 0.25rem;
  margin: 0;
  flex-wrap: wrap;
}

.dro-stat-card-split-u {
  font-size: 13px;
  font-weight: 800;
  color: #94a3b8;
}

.dro-stat-card--historical {
  opacity: 0.88;
}

.dro-stat-card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.65rem;
  flex-shrink: 0;
}

.dro-stat-card-top--dense-icon {
  align-items: flex-start;
}

.dro-stat-card-top--asset {
  margin-bottom: 0.5rem;
}

.dro-stat-card-ico--emerald {
  color: #d1fae5;
}

/** 备餐卡：餐具图标与请假卡等处同为深绿 #047857 */
.dro-stat-card-ico--meal-prep {
  flex-shrink: 0;
}

.dro-stat-card-ico--blue {
  color: #dbeafe;
}

.dro-stat-card-tip--soft {
  color: #93c5fd;
}

.dro-stat-card-tip--soft:hover {
  color: #3b82f6;
}

.dro-stat-card-metric-wrap--lift {
  margin-top: -0.5rem;
}

.dro-stat-card-metric-wrap--prep-rows {
  margin-top: -0.35rem;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  min-height: 4.25rem;
}

.dro-stat-card-prep-row {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.dro-stat-card-prep-row--split {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  line-height: 1.4;
}

/** 备餐卡主行「份」与第二行数字略加大、对比度提高 */
.dro-stat-card--meal .dro-stat-card-unit--prep-hero {
  font-size: 16px;
  font-weight: 800;
  color: #047857;
}

.dro-stat-card--meal .dro-stat-card-num--xl {
  font-size: 3.35rem;
}

.dro-stat-card--meal .dro-stat-card-prep-split-num {
  color: #047857;
  font-weight: 900;
  font-size: 1.05em;
  font-variant-numeric: tabular-nums;
  margin: 0 0.05rem;
}

.dro-stat-card-prep-split-gap {
  display: inline-block;
  width: 0.5rem;
}

/** 续费卡右栏：明日备餐嵌套（与「今日需备餐品」相同配送/自提拆分，栏宽较窄略缩小主数字） */
.dro-stat-card-metric-wrap--prep-rows--nested {
  min-height: 0;
  margin-top: 0.1rem;
  padding: 0.15rem 0 0;
  gap: 0.35rem;
}

.dro-stat-card--renewal-prep .dro-stat-card-split-cell--tomorrow-prep .dro-stat-card-split-k {
  margin-bottom: 0.3rem;
}

.dro-stat-card-metric--nextday-embed .dro-stat-card-num--nest-xl {
  font-size: 2.35rem;
  font-weight: 900;
  color: #a16207;
  letter-spacing: -0.03em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.dro-stat-card-unit--nest-nextday {
  font-size: 14px;
  font-weight: 800;
  color: #ca8a04;
}

.dro-stat-card--renewal-prep .dro-stat-card-prep-split-num--nest {
  color: #047857;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

/**
 * 与备餐卡黄框「配送…自提…」行一致：14px / 700 / #475569；数字强调 #047857（同 dro-stat-card-prep-split-num）
 */
.dro-stat-card--leave .dro-stat-card-k,
.dro-stat-card--meal .dro-stat-card-k,
.dro-stat-card--asset .dro-stat-card-k,
.dro-stat-card--renewal-prep .dro-stat-card-k {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  letter-spacing: normal;
  text-transform: none;
}

.dro-stat-card--leave .dro-stat-card-foot-caption {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
}

.dro-stat-card--leave .dro-stat-card-foot-strong--tomorrow-leave {
  color: #047857;
  font-weight: 900;
}

.dro-stat-card--leave .dro-stat-card-ico,
.dro-stat-card--meal .dro-stat-card-ico {
  color: #047857;
}

.dro-stat-card--asset .dro-stat-card-split-k {
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  letter-spacing: normal;
  text-transform: none;
}

.dro-stat-card--asset .dro-stat-card-ico--blue {
  color: #047857;
}

.dro-stat-card--asset .dro-stat-card-tip--soft {
  color: #475569;
}

.dro-stat-card--asset .dro-stat-card-tip--soft:hover {
  color: #334155;
}

.dro-stat-card--renewal-prep .dro-stat-card-ico--amber {
  color: #047857;
}


.dro-stat-card-foot-caption {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #cbd5e1;
  text-align: center;
}

.dro-stat-card-foot-strong {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.dro-stat-card-foot-strong--tomorrow-meals {
  color: #0f766e;
}

.dro-stat-card-title-inline {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.dro-stat-card-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;
  border: none;
  background: transparent;
  color: #94a3b8;
  border-radius: 0.35rem;
  cursor: help;
  line-height: 1;
  transition: color 0.15s ease;
}

.dro-stat-card-tip:hover {
  color: #3b82f6;
}

.dro-stat-card-k {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.dro-stat-card-ico {
  color: #e2e8f0;
  flex-shrink: 0;
}

.dro-stat-card-metric-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 4rem;
  padding: 0.35rem 0;
}

.dro-stat-card-metric {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  justify-content: center;
}

.dro-stat-card-metric--emerald .dro-stat-card-num {
  color: #059669;
}

.dro-stat-card-metric--emerald .dro-stat-card-unit {
  color: #34d399;
}

/* 请假卡主数值：靛紫，与备餐绿区分 */
.dro-stat-card-metric--leave .dro-stat-card-num {
  color: #4f46e5;
}

.dro-stat-card-unit--leave {
  color: #6366f1;
}

.dro-stat-card-num {
  font-size: 2.5rem;
  font-weight: 900;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.dro-stat-card-num.dro-stat-card-num--xl {
  font-size: 3.125rem;
  letter-spacing: -0.04em;
  line-height: 1;
}

.dro-stat-card-unit {
  font-size: 13px;
  font-weight: 800;
  color: #94a3b8;
}

.dro-stat-card-foot--dock {
  margin-top: auto;
  padding-top: 0.35rem;
  flex-shrink: 0;
  text-align: center;
  border-top: none;
}

.dro-stat-card-foot-line {
  font-size: 10px;
  font-weight: 600;
  color: #cbd5e1;
  letter-spacing: 0.02em;
}

.dro-stat-card-foot-num {
  font-weight: 800;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.dro-stat-card-asset-mid {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0 0.5rem;
}

.dro-stat-card-split {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: 100%;
  max-width: 15rem;
}

.dro-stat-card-split--around {
  justify-content: space-around;
  max-width: none;
}

.dro-stat-card-split-cell {
  flex: 1;
  min-width: 0;
  text-align: center;
}

.dro-stat-card-split-k {
  margin: 0 0 0.25rem;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
}

.dro-stat-card-split-v {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 900;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.dro-stat-card-split-vsep {
  align-self: stretch;
  width: 1px;
  min-height: 2.75rem;
  margin: 0 0.85rem;
  background: rgba(148, 163, 184, 0.38);
  flex-shrink: 0;
}

.dro-stat-card-split-vsep--refined {
  align-self: center;
  min-height: 2.5rem;
  margin: 0 0.5rem;
  background: #f1f5f9;
}

.dro-stat-card-split-v--lg {
  font-size: 2rem;
  letter-spacing: -0.03em;
}

/* 双栏卡大数字：橙/蓝/玫/琥珀，彼此错开 */
.dro-stat-card-split-v--expire-today {
  color: #ea580c;
}

.dro-stat-card-split-v--map-total {
  color: #2563eb;
}

.dro-stat-card-split-v--soon-expire {
  color: #be185d;
}

.dro-stat-card-split-u--soon-expire {
  color: #db2777;
}

.dro-stat-card-split-v--nextday-prep {
  color: #a16207;
}

.dro-stat-card-split-u--nextday-prep {
  color: #ca8a04;
}

/* 主区：地图宽 + 右侧排行 */
.dro-dash-main {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1.5rem;
  align-items: start;
}

@media (min-width: 1280px) {
  .dro-dash-main {
    grid-template-columns: minmax(0, 9fr) minmax(260px, 3fr);
  }
}

.dro-map-shell {
  background: #fff;
  border-radius: 2.5rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  min-height: min(calc(100vh - 300px), 880px);
}

.dro-map-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
  padding: 1.5rem;
  border-bottom: 1px solid #f8fafc;
  flex-shrink: 0;
}

.dro-map-toolbar-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dro-map-toolbar-live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  flex-shrink: 0;
}

.dro-map-toolbar-title {
  font-size: 14px;
  font-weight: 900;
  color: #334155;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.dro-map-pickup-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
}

.dro-map-pickup-label {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.dro-map-pickup-cb {
  width: 14px;
  height: 14px;
  accent-color: #10b981;
}

.dro-map-body {
  position: relative;
  flex: 1;
  min-height: 500px;
  background-color: #f8fafc;
  background-image: radial-gradient(#cbd5e1 1px, transparent 1px);
  background-size: 24px 24px;
}

.dro-map-body :deep(.delivery-overview-map) {
  border: none;
  border-radius: 0;
  height: min(calc(100vh - 360px), 900px);
  min-height: 500px;
}

.dro-map-body :deep(.delivery-overview-map-hint) {
  border-radius: 0;
  min-height: 240px;
}

.dro-float-legends {
  position: absolute;
  right: 1rem;
  bottom: 1rem;
  left: auto;
  z-index: 400;
  width: min(17rem, calc(100% - 2rem));
  max-height: min(40vh, 320px);
  overflow-y: auto;
  pointer-events: auto;
}

.dro-float-legends--glass {
  left: 2rem;
  right: auto;
  bottom: 2rem;
}

.dro-legend-card {
  padding: 0.8rem 0.95rem;
  border-radius: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.42);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  backdrop-filter: blur(16px) saturate(1.15);
  -webkit-backdrop-filter: blur(16px) saturate(1.15);
}

/* 与 HTML 一致：图例卡为更强的毛玻璃（需置于 .dro-legend-card 之后以覆盖基础样式） */
.dro-legend-card.dro-glass-legend {
  padding: 1.5rem;
  border-radius: 1.5rem;
  border: 1px solid rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.06);
}

.dro-legend-h {
  margin: 0 0 0.65rem;
  padding-bottom: 0.45rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  font-size: 12px;
  font-weight: 900;
  color: #64748b;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dro-legend-metrics {
  list-style: none;
  margin: 0;
  padding: 0;
}

.dro-legend-metrics li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 0.45rem;
}

.dro-legend-metrics li:last-of-type {
  margin-bottom: 0;
}

.dro-legend-metrics-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.dro-legend-metrics-n {
  font-weight: 900;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

/* 精雕版图例：标题字距与数字等宽字体（置于通用 .dro-legend-h 之后以保证覆盖） */
.dro-legend-card.dro-glass-legend .dro-legend-h {
  border-bottom-color: rgba(15, 23, 42, 0.05);
  letter-spacing: 0.2em;
}

.dro-legend-card.dro-glass-legend .dro-legend-metrics li {
  margin-bottom: 0.6rem;
}

.dro-legend-card.dro-glass-legend .dro-legend-metrics-n {
  font-family:
    ui-monospace,
    SFMono-Regular,
    Menlo,
    Monaco,
    Consolas,
    monospace;
}

.dro-legend-foot {
  margin: 0.65rem 0 0;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  font-size: 9px;
  line-height: 1.5;
  color: #64748b;
  font-style: italic;
}

.dro-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  flex-shrink: 0;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.12);
}

.dro-dot--store {
  background: #059669;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
}
.dro-dot--leave {
  background: #94a3b8;
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.16);
}
.dro-dot--done {
  background: #34d399;
  box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.18);
}
.dro-dot--pending {
  background: #f97316;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.18);
}

/* 右侧排行卡 */
.dro-rank-card {
  background: #fff;
  border-radius: 2.5rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  padding: 2rem;
  display: flex;
  flex-direction: column;
  min-height: min(calc(100vh - 300px), 880px);
}

.dro-rank-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2rem;
}

.dro-rank-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}

.dro-rank-trend-ico {
  color: #10b981;
  flex-shrink: 0;
}

.dro-rank-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.dro-rank-item-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.55rem;
}

.dro-rank-item-meta {
  min-width: 0;
}

.dro-rank-name {
  margin: 0 0 0.2rem;
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  text-transform: none;
  letter-spacing: normal;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dro-rank-count {
  margin: 0;
  font-size: 14px;
  font-weight: 800;
  color: #334155;
  font-variant-numeric: tabular-nums;
}

.dro-rank-count-unit {
  font-size: 11px;
  font-weight: 400;
  color: #cbd5e1;
}

.dro-rank-pct-wrap {
  flex: 0 0 3.35rem;
  width: 3.35rem;
  text-align: right;
}

.dro-rank-pct {
  font-size: 13px;
  font-weight: 900;
  color: #059669;
  font-variant-numeric: tabular-nums;
  font-family:
    ui-monospace,
    SFMono-Regular,
    Menlo,
    Monaco,
    Consolas,
    monospace;
}

.dro-rank-bar {
  height: 6px;
  background: #f8fafc;
  border-radius: 999px;
  overflow: hidden;
}

.dro-rank-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
}

.dro-rank-actions {
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #f1f5f9;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.dro-rank-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.875rem 0.5rem;
  border-radius: 1rem;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  text-decoration: none;
  text-align: center;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}

.dro-rank-btn--primary {
  background: #ecfdf5;
  color: #047857;
}

.dro-rank-btn--primary:hover {
  background: #d1fae5;
}

.dro-rank-btn--secondary {
  background: #f8fafc;
  color: #475569;
}

.dro-rank-btn--secondary:hover {
  background: #f1f5f9;
}

/* 滚动条（设计稿 custom-scrollbar） */
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: #f1f5f9;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
</style>
