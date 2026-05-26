<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { RefreshCw, Sun, Users, TrendingUp } from 'lucide-vue-next'
import { useDeliveryRegionMapOverview } from '../../composables/useDeliveryRegionMapOverview.js'
import DeliveryOverviewMap from './DeliveryOverviewMap.vue'
import { UNASSIGNED_AREA_LABEL } from '../../utils/regionAssignment.js'
import { apiJson, adminAccessToken, adminKind, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useAnimatedInteger } from '../../composables/useAnimatedInteger.js'

const route = useRoute()

/** 与路由 meta 一致：本页自带顶栏（hidePageTitle），主标题与详情描述与智能配送大表同级样式 */
const pageTitleText = computed(() =>
  route.meta.title != null && String(route.meta.title).trim() !== ''
    ? String(route.meta.title).trim()
    : '今日营业概览',
)
const pageSubtitleText = computed(() => {
  const s = route.meta.pageSubtitle
  return s != null && String(s).trim() !== '' ? String(s).trim() : ''
})

const dashboardStats = ref([])
const dashboardStatsLoading = ref(false)
/** @type {import('vue').Ref<string>} */
const summaryAnchorDate = ref('')
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const summaryMeta = ref(null)

const todayPrepMetrics = computed(() => {
  const m = summaryMeta.value?.today_prep_metrics
  return m && typeof m === 'object' ? m : null
})
const tomorrowPrepMetrics = computed(() => {
  const m = summaryMeta.value?.tomorrow_prep_metrics
  return m && typeof m === 'object' ? m : null
})

/** @param {Record<string, unknown> | null} m */
function prepMetricsBreakdown(m) {
  if (!m) return null
  const hp = Number(m.home_pending_meal_total) || 0
  const hd = Number(m.home_delivered_meal_total) || 0
  const pu = Number(m.pickup_meal_total) || 0
  return { total: hp + hd + pu, delivery: hp + hd, pickup: pu }
}

/** @param {Record<string, unknown> | null} m */
function prepMetricsFulfillment(m) {
  if (!m) return null
  const hd = Number(m.home_delivered_meal_total) || 0
  const hp = Number(m.home_pending_meal_total) || 0
  const pd = Number(m.pickup_delivered_meal_total) || 0
  const pp = Number(m.pickup_pending_meal_total) || 0
  const delivered = hd + pd
  const pending = hp + pp
  return { delivered, pending, total: delivered + pending }
}

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

/** 明日首餐新客：起送业务日 = 锚定日次日（dashboard-summary.tomorrow_first_meal_new_members） */
const tomorrowFirstMealNewCount = computed(
  () => Number(summaryMeta.value?.tomorrow_first_meal_new_members) || 0,
)

/** 同比上周今日：大表到家+自提去重人数 − 7 天前同日（dashboard-summary） */
const todayPrepHeadsYoyDelta = computed(() => {
  const v = summaryMeta.value?.today_prep_heads_yoy_week_delta
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : null
})
const tomorrowPrepHeadsYoyDelta = computed(() => {
  const v = summaryMeta.value?.tomorrow_prep_heads_yoy_week_delta
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.trunc(n) : null
})

/**
 * 去掉备餐周同比 caption 前导「较上周」（左侧条已写同比上周，避免重复）
 * @param {unknown} raw
 * @returns {string}
 */
function stripMealsWowCaptionLeadingPhrase(raw) {
  const t = raw == null ? '' : String(raw).trim()
  if (!t) return ''
  return t.replace(/^较上周[\s\u3000]*/, '').trim()
}

/** 备餐份数同比上周说明（dashboard-summary）；展示在同比条右侧（左侧日期仍由前端拼装） */
const todayMealsWeekOverWeekCaption = computed(() => {
  const raw = summaryMeta.value?.today_meals_week_over_week_caption
  return stripMealsWowCaptionLeadingPhrase(raw)
})
/** 明日备餐份数同比上周说明；展示在同比条右侧 */
const tomorrowMealsWeekOverWeekCaption = computed(() => {
  const raw = summaryMeta.value?.tomorrow_meals_week_over_week_caption
  return stripMealsWowCaptionLeadingPhrase(raw)
})

/** 同比文案：正为增加 x 人，负为减少 x 人，零为持平 */
function formatYoyWeekHeadsText(delta) {
  if (delta == null) return '—'
  if (delta === 0) return '与上周同期持平'
  if (delta > 0) return `增加${delta}人`
  return `减少${Math.abs(delta)}人`
}

/** 同比展示：+x人 / -x人 / 0人（用于边框区块数字） */
function formatYoyWeekHeadsSigned(delta) {
  if (delta == null) return '—'
  if (delta === 0) return '0人'
  if (delta > 0) return `+${delta}人`
  return `${delta}人`
}

/** 与 Date#getUTCDay() 一致：0=周日 … 6=周六（UTC，与锚定业务日一致） */
const WEEKDAY_CN_SHORT = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** ISO 日期 YYYY-MM-DD → 中文「周x」 */
function isoToWeekdayCn(isoLike) {
  const raw = isoLike == null ? '' : String(isoLike).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  return WEEKDAY_CN_SHORT[dt.getUTCDay()] ?? ''
}

/** ISO 日期 YYYY-MM-DD → 「M月D日」 */
function isoToMdDisplay(isoLike) {
  const raw = isoLike == null ? '' : String(isoLike).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!m) return ''
  return `${Number(m[2])}月${Number(m[3])}日`
}

const businessAnchorMdDisplay = computed(() =>
  isoToMdDisplay(summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value),
)

const businessAnchorWeekdayDisplay = computed(() =>
  isoToWeekdayCn(summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value),
)

/** 锚定日次日 → 「M月D日」 */
const businessAnchorTomorrowMdDisplay = computed(() => {
  const raw = summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value
  const s = raw == null ? '' : String(raw).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + 1)
  return `${dt.getUTCMonth() + 1}月${dt.getUTCDate()}日`
})

const businessAnchorTomorrowWeekdayDisplay = computed(() => {
  const raw = summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value
  const s = raw == null ? '' : String(raw).trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + 1)
  return WEEKDAY_CN_SHORT[dt.getUTCDay()] ?? ''
})

/** 业务锚定日 ISO（YYYY-MM-DD），非法则为空串 */
const businessAnchorIsoNormalized = computed(() => {
  const raw = summaryMeta.value?.business_anchor_date ?? summaryAnchorDate.value
  if (raw == null || String(raw).trim() === '') return ''
  const s = String(raw).trim().slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : ''
})

/** 同比基准：上周同一日历日（今日卡 = 锚定日 −7 天） */
const yoyLastWeekTodayIso = computed(() =>
  businessAnchorIsoNormalized.value ? addCalendarDaysIso(businessAnchorIsoNormalized.value, -7) : '',
)
const yoyLastWeekTodayMd = computed(() => isoToMdDisplay(yoyLastWeekTodayIso.value))
const yoyLastWeekTodayWeekday = computed(() => isoToWeekdayCn(yoyLastWeekTodayIso.value))

/** 同比基准：上周与「明日」对应的日历日（锚定日+1 再 −7 天） */
const yoyLastWeekTomorrowIso = computed(() => {
  const a = businessAnchorIsoNormalized.value
  if (!a) return ''
  const next = addOneDayIso(a)
  return next ? addCalendarDaysIso(next, -7) : ''
})
const yoyLastWeekTomorrowMd = computed(() => isoToMdDisplay(yoyLastWeekTomorrowIso.value))
const yoyLastWeekTomorrowWeekday = computed(() => isoToWeekdayCn(yoyLastWeekTomorrowIso.value))

/** ISO 日历日 YYYY-MM-DD 平移若干天（UTC，与业务日一致） */
function addCalendarDaysIso(isoLike, deltaDays) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(isoLike).trim().slice(0, 10))
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + Number(deltaDays))
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(
    dt.getUTCDate(),
  ).padStart(2, '0')}`
}

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

async function fetchDashboardSummary() {
  if (!adminAccessToken.value) return
  dashboardStatsLoading.value = true
  try {
    const q = summaryAnchorDate.value.trim()
    const qs = q ? `?business_date=${encodeURIComponent(q)}` : ''
    const d = await apiJson(`/api/admin/dashboard-summary${qs}`, {}, { auth: true })
    summaryMeta.value = d
    if (d && typeof d.business_anchor_date === 'string') {
      summaryAnchorDate.value = d.business_anchor_date
    }
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
      { label: '今日卡到期会员', value: te, unit: '人', mapFilter: null },
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
  mapEligiblePlanCounts,
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

/** 今日单次零售总计数量（dashboard-summary.today_single_retail_total_quantity） */
const todaySingleRetailTotalCount = computed(
  () => Number(summaryMeta.value?.today_single_retail_total_quantity) || 0,
)

/** 备餐卡片「总数」：优先 dashboard-summary 拆分，否则回落营业概览 */
const cardPrepTotal = computed(() => {
  const b = prepMetricsBreakdown(todayPrepMetrics.value)
  if (b != null) return b.total
  return Number(dashboardStats.value[2]?.value) || 0
})

/** 配送=到家待送达+已送达；自提=门店自提分组 */
const todayMealsDelivery = computed(() => {
  const b = prepMetricsBreakdown(todayPrepMetrics.value)
  if (b != null) return b.delivery
  return null
})
const todayMealsPickup = computed(() => {
  const b = prepMetricsBreakdown(todayPrepMetrics.value)
  if (b != null) return b.pickup
  return null
})

/** 明日备餐：总份优先 dashboard-summary 拆分，否则营业概览 tomorrow_meals_to_prepare */
const cardTomorrowPrepTotal = computed(() => {
  const b = prepMetricsBreakdown(tomorrowPrepMetrics.value)
  if (b != null) return b.total
  return Number(dashboardStats.value[3]?.value) || 0
})

const tomorrowPrepDelivery = computed(() => {
  const b = prepMetricsBreakdown(tomorrowPrepMetrics.value)
  if (b != null) return b.delivery
  return null
})
const tomorrowPrepPickup = computed(() => {
  const b = prepMetricsBreakdown(tomorrowPrepMetrics.value)
  if (b != null) return b.pickup
  return null
})

const todayHomeStopCount = computed(() => {
  const m = todayPrepMetrics.value
  if (!m || m.home_stop_count == null) return null
  return Math.max(0, Math.trunc(Number(m.home_stop_count) || 0))
})
const tomorrowHomeStopCount = computed(() => {
  const m = tomorrowPrepMetrics.value
  if (!m || m.home_stop_count == null) return null
  return Math.max(0, Math.trunc(Number(m.home_stop_count) || 0))
})

/** 概览接口是否包含地图会员库五字段（旧后端兼容） */
const mapLibFromApi = computed(
  () =>
    summaryMeta.value != null &&
    Object.prototype.hasOwnProperty.call(summaryMeta.value, 'total_members'),
)

const mapLibActiveWeekly = computed(() => {
  if (mapLibFromApi.value) return Number(summaryMeta.value.active_weekly_members) || 0
  return mapEligiblePlanCounts.value.week
})

const mapLibExpiredWeekly = computed(() => {
  return mapLibFromApi.value ? Number(summaryMeta.value.expired_weekly_members) || 0 : 0
})

const mapLibActiveMonthly = computed(() => {
  if (mapLibFromApi.value) return Number(summaryMeta.value.active_monthly_members) || 0
  return mapEligiblePlanCounts.value.month
})

const mapLibExpiredMonthly = computed(() => {
  return mapLibFromApi.value ? Number(summaryMeta.value.expired_monthly_members) || 0 : 0
})

const mapLibTotal = computed(() => {
  if (mapLibFromApi.value) return Number(summaryMeta.value.total_members) || 0
  return mapEligiblePlanCounts.value.week + mapEligiblePlanCounts.value.month
})

const mapLibWeekSum = computed(() => mapLibActiveWeekly.value + mapLibExpiredWeekly.value)
const mapLibMonthSum = computed(() => mapLibActiveMonthly.value + mapLibExpiredMonthly.value)

const mapLibActivityRatePct = computed(() => {
  const t = mapLibTotal.value
  if (t <= 0) return 0
  return Math.round(((mapLibActiveWeekly.value + mapLibActiveMonthly.value) / t) * 100)
})

/** 进度条四段：有效月、有效周、过期月、过期周（与参考 HTML 顺序一致） */
const mapLibBarSegments = computed(() => {
  const t = mapLibTotal.value
  const raw = [
    { key: 'am', n: mapLibActiveMonthly.value, cls: 'dro-map-bar__seg--month' },
    { key: 'aw', n: mapLibActiveWeekly.value, cls: 'dro-map-bar__seg--week' },
    { key: 'em', n: mapLibExpiredMonthly.value, cls: 'dro-map-bar__seg--exp-m' },
    { key: 'ew', n: mapLibExpiredWeekly.value, cls: 'dro-map-bar__seg--exp-w' },
  ]
  if (t <= 0) return raw.map((s) => ({ ...s, width: 0 }))
  return raw.map((s) => ({ ...s, width: (s.n / t) * 100 }))
})

/** 今日：已送达 / 待履约（绿/灰），数据来自 dashboard-summary.today_prep_metrics */
const todayDeliveryFulfillBar = computed(() => {
  const f = prepMetricsFulfillment(todayPrepMetrics.value)
  if (!f || f.total <= 0) return { done: 0, pending: 0 }
  return {
    done: (f.delivered / f.total) * 100,
    pending: (f.pending / f.total) * 100,
  }
})

const todayFulfillAria = computed(() => {
  const f = prepMetricsFulfillment(todayPrepMetrics.value)
  if (!f || f.total <= 0) return '配送履约：暂无备餐份数'
  return `配送履约：已送达 ${f.delivered} 份，待履约 ${f.pending} 份，合计 ${f.total} 份`
})

/** 明日：配送到家 vs 自提占比（蓝/琥珀），与参考稿中间留白结构对称 */
const tomorrowPrepSplitBar = computed(() => {
  const d = tomorrowPrepDelivery.value
  const p = tomorrowPrepPickup.value
  if (d == null || p == null) return { home: 0, pickup: 0 }
  const nd = Number(d) || 0
  const np = Number(p) || 0
  const sum = nd + np
  if (sum <= 0) return { home: 0, pickup: 0 }
  return {
    home: (nd / sum) * 100,
    pickup: (np / sum) * 100,
  }
})

const tomorrowSplitAria = computed(() => {
  const d = tomorrowPrepDelivery.value
  const p = tomorrowPrepPickup.value
  if (d == null || p == null) return '明日配餐结构：暂无数据'
  return `明日配餐结构：配送到家 ${d} 份，门店自提 ${p} 份`
})

const storePinLegendCount = computed(() =>
  storeAnchor.value?.store_lng != null && storeAnchor.value?.store_lat != null ? 1 : 0,
)

/** 概览数字滚动展示（加载 / 刷新 / 换日后过渡到新值） */
const prepTotalAnimated = useAnimatedInteger(() => cardPrepTotal.value, { duration: 840 })
const todayDeliveryAnimated = useAnimatedInteger(() => todayMealsDelivery.value, { duration: 700 })
const todayPickupAnimated = useAnimatedInteger(() => todayMealsPickup.value, { duration: 700 })
const todayHomeStopCountAnimated = useAnimatedInteger(() => todayHomeStopCount.value, {
  duration: 640,
})
const tomorrowTotalAnimated = useAnimatedInteger(() => cardTomorrowPrepTotal.value, { duration: 840 })
const tomorrowDeliveryAnimated = useAnimatedInteger(() => tomorrowPrepDelivery.value, { duration: 700 })
const tomorrowPickupAnimated = useAnimatedInteger(() => tomorrowPrepPickup.value, { duration: 700 })
const tomorrowHomeStopCountAnimated = useAnimatedInteger(() => tomorrowHomeStopCount.value, {
  duration: 640,
})
const todayLeaveAnimated = useAnimatedInteger(() => summarySlice.value.todayLeave, { duration: 620 })
const tomorrowLeaveAnimated = useAnimatedInteger(() => summarySlice.value.tomorrowLeave, { duration: 620 })
const expireCountAnimated = useAnimatedInteger(() => expireCount.value, { duration: 620 })
const todaySingleRetailTotalAnimated = useAnimatedInteger(() => todaySingleRetailTotalCount.value, {
  duration: 620,
})
const tomorrowFirstMealNewAnimated = useAnimatedInteger(() => tomorrowFirstMealNewCount.value, {
  duration: 620,
})
const mapLibTotalAnimated = useAnimatedInteger(() => mapLibTotal.value, { duration: 720 })
const mapLibActiveWeeklyAnimated = useAnimatedInteger(() => mapLibActiveWeekly.value, { duration: 580 })
const mapLibExpiredWeeklyAnimated = useAnimatedInteger(() => mapLibExpiredWeekly.value, { duration: 580 })
const mapLibActiveMonthlyAnimated = useAnimatedInteger(() => mapLibActiveMonthly.value, { duration: 580 })
const mapLibExpiredMonthlyAnimated = useAnimatedInteger(() => mapLibExpiredMonthly.value, { duration: 580 })
const mapLibWeekSumAnimated = useAnimatedInteger(() => mapLibWeekSum.value, { duration: 560 })
const mapLibMonthSumAnimated = useAnimatedInteger(() => mapLibMonthSum.value, { duration: 560 })
const storePinLegendAnimated = useAnimatedInteger(() => storePinLegendCount.value, { duration: 420 })
const deliveredTodayAnimated = useAnimatedInteger(() => stats.value.deliveredToday, { duration: 640 })
const pendingTodayAnimated = useAnimatedInteger(() => stats.value.pendingToday, { duration: 640 })

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
      <div class="page-heading">
        <h2 class="page-title">{{ pageTitleText }}</h2>
        <p v-if="pageSubtitleText" class="page-subtitle">{{ pageSubtitleText }}</p>
      </div>
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
          <el-date-picker
            v-model="summaryAnchorDate"
            type="date"
            value-format="YYYY-MM-DD"
            class="dro-date-inline-picker"
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

    <!-- 三张概览卡：今日备餐 / 明日预测 / 地图会员库（样式对齐设计稿） -->
    <div
      v-if="(!dashboardStatsLoading && dashboardStats.length) || showDeliveryMetrics"
      class="dro-dash-stat-grid"
    >
      <article class="dro-dash-kpi" :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }">
        <div class="dro-dash-kpi__head">
          <div class="dro-dash-kpi__tags">
            <span class="dro-dash-pill dro-dash-pill--emerald"
              >今日 · {{ businessAnchorMdDisplay || '—'
              }}<template v-if="businessAnchorWeekdayDisplay">
                {{ businessAnchorWeekdayDisplay }}</template
              ></span
            >
            <span class="dro-dash-kpi__kicker">配餐总盘</span>
          </div>
          <Sun :size="22" class="dro-dash-kpi__ico dro-dash-kpi__ico--emerald" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__mid">
          <div class="dro-dash-kpi__main">
            <div class="dro-dash-kpi__hero">
              <span class="dro-dash-kpi__hero-num">{{ prepTotalAnimated }}</span>
              <span class="dro-dash-kpi__hero-suffix">份需备</span>
            </div>
            <div class="dro-dash-kpi__side">
              <div
                class="dro-dash-kpi__side-stop-line"
                role="status"
                :aria-label="
                  todayHomeStopCount == null
                    ? '配送点数量未加载'
                    : `${todayHomeStopCount} 个到家配送点`
                "
              >
                <template v-if="todayHomeStopCount != null">
                  <span class="dro-dash-kpi__side-stop-n dro-dash-kpi__side-n--emerald">{{
                    todayHomeStopCountAnimated
                  }}</span>
                  <span class="dro-dash-kpi__side-stop-lbl">配送点</span>
                </template>
                <span v-else class="dro-dash-kpi__side-stop-placeholder">—</span>
              </div>
              <div class="dro-dash-kpi__side-row">
                <span class="dro-dash-kpi__side-n dro-dash-kpi__side-n--emerald">{{
                  todayMealsDelivery === null ? '—' : todayDeliveryAnimated
                }}</span>
                <span class="dro-dash-kpi__side-txt">配送</span>
              </div>
              <div class="dro-dash-kpi__side-row">
                <span class="dro-dash-kpi__side-n dro-dash-kpi__side-n--ink">{{
                  todayMealsPickup === null ? '—' : todayPickupAnimated
                }}</span>
                <span class="dro-dash-kpi__side-txt dro-dash-kpi__side-txt--soft">自提</span>
              </div>
            </div>
          </div>
          <div class="dro-prep-bar" role="img" :aria-label="todayFulfillAria">
            <div
              class="dro-prep-bar__seg dro-prep-bar__seg--today-done"
              :style="{ width: todayDeliveryFulfillBar.done + '%' }"
            />
            <div
              class="dro-prep-bar__seg dro-prep-bar__seg--today-pending"
              :style="{ width: todayDeliveryFulfillBar.pending + '%' }"
            />
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--chips-then-yoy">
          <div class="dro-dash-chip dro-dash-chip--amber">
            <span class="dro-dash-chip__k">今日请假</span>
            <span class="dro-dash-chip__v">{{ todayLeaveAnimated }} <small>人</small></span>
          </div>
          <div class="dro-dash-chip dro-dash-chip--rose">
            <span class="dro-dash-chip__k">今日卡到期</span>
            <span class="dro-dash-chip__v">{{ expireCountAnimated }} <small>人</small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--emerald"
            role="status"
            :aria-label="`今日单次零售 ${todaySingleRetailTotalCount} 份`"
          >
            <span class="dro-dash-chip__k">今日单次零售</span>
            <span class="dro-dash-chip__v">{{ todaySingleRetailTotalAnimated }} <small>份</small></span>
          </div>
          <div
            class="dro-dash-yoy-chip dro-dash-yoy-chip--today"
            role="status"
            :aria-label="
              (yoyLastWeekTodayMd
                ? '同比上周 · ' +
                  yoyLastWeekTodayMd +
                  (yoyLastWeekTodayWeekday || '') +
                  '，'
                : '') +
              (todayMealsWeekOverWeekCaption || formatYoyWeekHeadsText(todayPrepHeadsYoyDelta))
            "
          >
            <div class="dro-dash-yoy-chip__left">
              <span class="dro-dash-yoy-chip__line">
                <span class="dro-dash-yoy-chip__prefix">同比上周 · </span>
                <span class="dro-dash-yoy-chip__date">{{ yoyLastWeekTodayMd || '—' }}</span>
                <span class="dro-dash-yoy-chip__week">{{ yoyLastWeekTodayWeekday || '' }}</span>
              </span>
            </div>
            <span
              class="dro-dash-yoy-chip__val"
              :class="
                todayMealsWeekOverWeekCaption
                  ? 'dro-dash-yoy-chip__val--caption'
                  : {
                      'dro-dash-yoy-chip__val--up':
                        todayPrepHeadsYoyDelta != null && todayPrepHeadsYoyDelta > 0,
                      'dro-dash-yoy-chip__val--down':
                        todayPrepHeadsYoyDelta != null && todayPrepHeadsYoyDelta < 0,
                      'dro-dash-yoy-chip__val--flat': todayPrepHeadsYoyDelta === 0,
                      'dro-dash-yoy-chip__val--muted': todayPrepHeadsYoyDelta == null,
                    }
              "
              >{{
                todayMealsWeekOverWeekCaption || formatYoyWeekHeadsSigned(todayPrepHeadsYoyDelta)
              }}</span
            >
          </div>
        </div>
      </article>

      <article
        class="dro-dash-kpi dro-dash-kpi--tomorrow"
        :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }"
      >
        <div class="dro-dash-kpi__head">
          <div class="dro-dash-kpi__tags">
            <span class="dro-dash-pill dro-dash-pill--blue"
              >明日预测 · {{ businessAnchorTomorrowMdDisplay || '—'
              }}<template v-if="businessAnchorTomorrowWeekdayDisplay">
                {{ businessAnchorTomorrowWeekdayDisplay }}</template
              ></span
            >
            <span class="dro-dash-kpi__kicker">配餐预测</span>
          </div>
          <TrendingUp :size="22" class="dro-dash-kpi__ico dro-dash-kpi__ico--blue" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__mid">
          <div class="dro-dash-kpi__main">
            <div class="dro-dash-kpi__hero">
              <span class="dro-dash-kpi__hero-num">{{ tomorrowTotalAnimated }}</span>
              <span class="dro-dash-kpi__hero-suffix">份预计</span>
            </div>
            <div class="dro-dash-kpi__side">
              <div
                class="dro-dash-kpi__side-stop-line"
                role="status"
                :aria-label="
                  tomorrowHomeStopCount == null
                    ? '配送点数量未加载'
                    : `${tomorrowHomeStopCount} 个到家配送点`
                "
              >
                <template v-if="tomorrowHomeStopCount != null">
                  <span class="dro-dash-kpi__side-stop-n dro-dash-kpi__side-n--blue">{{
                    tomorrowHomeStopCountAnimated
                  }}</span>
                  <span class="dro-dash-kpi__side-stop-lbl">配送点</span>
                </template>
                <span v-else class="dro-dash-kpi__side-stop-placeholder">—</span>
              </div>
              <div class="dro-dash-kpi__side-row">
                <span class="dro-dash-kpi__side-n dro-dash-kpi__side-n--blue">{{
                  tomorrowPrepDelivery === null ? '—' : tomorrowDeliveryAnimated
                }}</span>
                <span class="dro-dash-kpi__side-txt">配送</span>
              </div>
              <div class="dro-dash-kpi__side-row">
                <span class="dro-dash-kpi__side-n dro-dash-kpi__side-n--ink">{{
                  tomorrowPrepPickup === null ? '—' : tomorrowPickupAnimated
                }}</span>
                <span class="dro-dash-kpi__side-txt dro-dash-kpi__side-txt--soft">自提</span>
              </div>
            </div>
          </div>
          <div class="dro-prep-bar dro-prep-bar--tomorrow" role="img" :aria-label="tomorrowSplitAria">
            <div
              class="dro-prep-bar__seg dro-prep-bar__seg--tom-home"
              :style="{ width: tomorrowPrepSplitBar.home + '%' }"
            />
            <div
              class="dro-prep-bar__seg dro-prep-bar__seg--tom-pu"
              :style="{ width: tomorrowPrepSplitBar.pickup + '%' }"
            />
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--chips-then-yoy">
          <div class="dro-dash-chip dro-dash-chip--amber">
            <span class="dro-dash-chip__k">明日请假</span>
            <span class="dro-dash-chip__v">{{ tomorrowLeaveAnimated }} <small>人</small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--rose"
            :class="{ 'dro-dash-chip--faded': tomorrowFirstMealNewCount === 0 }"
          >
            <span class="dro-dash-chip__k">明日首餐新客</span>
            <span class="dro-dash-chip__v">{{ tomorrowFirstMealNewAnimated }} <small>人</small></span>
          </div>
          <div
            class="dro-dash-yoy-chip dro-dash-yoy-chip--tomorrow"
            role="status"
            :aria-label="
              (yoyLastWeekTomorrowMd
                ? '同比上周 · ' +
                  yoyLastWeekTomorrowMd +
                  (yoyLastWeekTomorrowWeekday || '') +
                  '，'
                : '') +
              (tomorrowMealsWeekOverWeekCaption || formatYoyWeekHeadsText(tomorrowPrepHeadsYoyDelta))
            "
          >
            <div class="dro-dash-yoy-chip__left">
              <span class="dro-dash-yoy-chip__line">
                <span class="dro-dash-yoy-chip__prefix">同比上周 · </span>
                <span class="dro-dash-yoy-chip__date">{{ yoyLastWeekTomorrowMd || '—' }}</span>
                <span class="dro-dash-yoy-chip__week">{{ yoyLastWeekTomorrowWeekday || '' }}</span>
              </span>
            </div>
            <span
              class="dro-dash-yoy-chip__val"
              :class="
                tomorrowMealsWeekOverWeekCaption
                  ? 'dro-dash-yoy-chip__val--caption'
                  : {
                      'dro-dash-yoy-chip__val--up':
                        tomorrowPrepHeadsYoyDelta != null && tomorrowPrepHeadsYoyDelta > 0,
                      'dro-dash-yoy-chip__val--down':
                        tomorrowPrepHeadsYoyDelta != null && tomorrowPrepHeadsYoyDelta < 0,
                      'dro-dash-yoy-chip__val--flat': tomorrowPrepHeadsYoyDelta === 0,
                      'dro-dash-yoy-chip__val--muted': tomorrowPrepHeadsYoyDelta == null,
                    }
              "
              >{{
                tomorrowMealsWeekOverWeekCaption ||
                  formatYoyWeekHeadsSigned(tomorrowPrepHeadsYoyDelta)
              }}</span
            >
          </div>
        </div>
      </article>

      <article class="dro-dash-kpi dro-dash-kpi--maplib">
        <div class="dro-dash-kpi__head">
          <div class="dro-dash-kpi__tags">
            <span class="dro-dash-pill dro-dash-pill--purple">活跃监控</span>
            <span class="dro-dash-kpi__kicker">地图会员库</span>
          </div>
          <Users :size="22" class="dro-dash-kpi__ico dro-dash-kpi__ico--purple" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__maplib-mid">
          <div class="dro-dash-kpi__maplib-top">
            <div class="dro-dash-kpi__hero dro-dash-kpi__hero--compact">
              <span class="dro-dash-kpi__hero-num dro-dash-kpi__hero-num--dark">{{ mapLibTotalAnimated }}</span>
              <span class="dro-dash-kpi__hero-suffix">位总会员</span>
            </div>
            <span class="dro-dash-kpi__rate">活跃率 {{ mapLibActivityRatePct }}%</span>
          </div>
          <div class="dro-map-bar" aria-hidden="true">
            <div
              v-for="seg in mapLibBarSegments"
              :key="seg.key"
              class="dro-map-bar__seg"
              :class="seg.cls"
              :style="{ width: seg.width + '%' }"
            />
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--plans">
          <div class="dro-dash-plan-box">
            <div class="dro-dash-plan-box__head">
              <span class="dro-dash-plan-box__t">周卡明细</span>
              <span class="dro-dash-plan-box__sum">共 {{ mapLibWeekSumAnimated }} 人</span>
            </div>
            <div class="dro-dash-plan-box__rows">
              <div class="dro-dash-plan-row">
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot" />有效</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--emerald"
                  >{{ mapLibActiveWeeklyAnimated }} 位</span
                >
              </div>
              <div class="dro-dash-plan-row">
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot dro-dash-dot--slate" />过期</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--muted"
                  >{{ mapLibExpiredWeeklyAnimated }} 位</span
                >
              </div>
            </div>
          </div>
          <div class="dro-dash-plan-box">
            <div class="dro-dash-plan-box__head">
              <span class="dro-dash-plan-box__t">月卡明细</span>
              <span class="dro-dash-plan-box__sum">共 {{ mapLibMonthSumAnimated }} 人</span>
            </div>
            <div class="dro-dash-plan-box__rows">
              <div class="dro-dash-plan-row">
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot dro-dash-dot--blue" />有效</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--blue"
                  >{{ mapLibActiveMonthlyAnimated }} 位</span
                >
              </div>
              <div class="dro-dash-plan-row">
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot dro-dash-dot--amber" />过期</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--amber"
                  >{{ mapLibExpiredMonthlyAnimated }} 位</span
                >
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
            <el-checkbox v-model="showSelfPickupPoints">自提显示</el-checkbox>
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
                  <span class="dro-legend-metrics-n">{{ storePinLegendAnimated }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--leave" />
                    <span>今日请假</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ todayLeaveAnimated }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--done" />
                    <span>当日已送达</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ deliveredTodayAnimated }}</span>
                </li>
                <li>
                  <span class="dro-legend-metrics-left">
                    <span class="dro-dot dro-dot--pending" />
                    <span>尚未送达</span>
                  </span>
                  <span class="dro-legend-metrics-n">{{ pendingTodayAnimated }}</span>
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
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

.dro-date-inline-picker {
  width: auto;
  min-width: 170px;
}

.dro-date-inline-picker :deep(.el-input__wrapper) {
  padding: 0.45rem 0.85rem;
  border-radius: 0.75rem;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.dro-date-inline-picker :deep(.el-input__inner) {
  font-size: 13px;
  font-weight: 800;
  color: #334155;
  font-family: inherit;
}

.dro-date-inline-picker :deep(.el-input__wrapper.is-focus) {
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

@media (min-width: 1120px) {
  .dro-dash-stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

/* ——— 配送区域总览：顶部三张 KPI 卡（对齐 Tailwind 参考稿） ——— */
.dro-dash-kpi {
  background: #fff;
  border: 1px solid rgba(226, 232, 240, 0.85);
  border-radius: 32px;
  padding: 1.75rem 1.85rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  min-height: 300px;
  height: 100%;
  transition:
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    border-color 0.3s ease;
}

.dro-dash-kpi:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.06);
  border-color: rgba(16, 185, 129, 0.22);
}

.dro-dash-kpi--tomorrow:hover {
  border-color: rgba(59, 130, 246, 0.25);
}

.dro-dash-kpi--maplib:hover {
  border-color: rgba(139, 92, 246, 0.22);
}

.dro-dash-kpi--dim {
  opacity: 0.88;
}

.dro-dash-kpi__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
  gap: 0.75rem;
  flex-shrink: 0;
}

.dro-dash-kpi__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  min-width: 0;
}

.dro-dash-pill {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.02em;
  padding: 0.3rem 0.85rem;
  border-radius: 999px;
  border: 1px solid transparent;
  line-height: 1.2;
  white-space: nowrap;
}

.dro-dash-pill--emerald {
  background: #ecfdf5;
  color: #047857;
  border-color: #d1fae5;
}

.dro-dash-pill--blue {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #dbeafe;
}

.dro-dash-pill--purple {
  background: #faf5ff;
  color: #7c3aed;
  border-color: #ede9fe;
}

.dro-dash-kpi__kicker {
  font-size: 12px;
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.dro-dash-kpi__ico {
  flex-shrink: 0;
}

.dro-dash-kpi__ico--emerald {
  color: #10b981;
}

.dro-dash-kpi__ico--blue {
  color: #3b82f6;
}

.dro-dash-kpi__ico--purple {
  color: #8b5cf6;
}

.dro-dash-kpi__main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0;
  flex: 0 0 auto;
  min-height: 0;
}

.dro-dash-kpi__mid {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  margin-bottom: 0;
}

/** 进度条与同比 chip / 地图卡周月区之间的弹性留白，三卡等高时拉齐「中间红框」行 */
.dro-dash-kpi__mid-spacer {
  flex: 1 1 auto;
  min-height: 0;
  width: 100%;
}

.dro-dash-kpi__mid .dro-dash-kpi__main {
  margin-bottom: 0.55rem;
}

.dro-prep-bar {
  display: flex;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #f1f5f9;
  flex-shrink: 0;
}

.dro-prep-bar__seg {
  height: 100%;
  min-width: 0;
  transition: width 0.45s ease;
}

.dro-prep-bar__seg--today-done {
  background: #10b981;
}

.dro-prep-bar__seg--today-pending {
  background: #cbd5e1;
}

.dro-prep-bar__seg--tom-home {
  background: #3b82f6;
}

.dro-prep-bar__seg--tom-pu {
  background: rgba(251, 191, 36, 0.65);
}

.dro-dash-yoy-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  margin-top: 0.5rem;
  padding: 0.65rem 0.85rem;
  border-radius: 1rem;
  border: 1px solid transparent;
  flex-shrink: 0;
}

/* 今日：翠绿底边（与今日胶囊、进度条同系） */
.dro-dash-yoy-chip--today {
  background: rgba(236, 253, 245, 0.94);
  border-color: rgba(16, 185, 129, 0.38);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.72) inset;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__prefix {
  color: #059669;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__date {
  color: #047857;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__week {
  color: #065f46;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__val--up {
  color: #047857;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__val--flat {
  color: #059669;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__val--muted {
  color: #0d9488;
}

/* 明日：浅蓝底边（与明日预测卡、rose 系区分） */
.dro-dash-yoy-chip--tomorrow {
  background: rgba(239, 246, 255, 0.96);
  border-color: rgba(59, 130, 246, 0.32);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.7) inset;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__prefix {
  color: #64748b;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__date {
  color: #475569;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__week {
  color: #0f172a;
}
.dro-dash-yoy-chip__left {
  min-width: 0;
  flex: 1;
}

.dro-dash-yoy-chip__line {
  display: inline;
  font-size: 12px;
  line-height: 1.35;
}

/* 备餐份数周同比文案：与左侧「同比上周」行同为 12px */
.dro-dash-yoy-chip__val--caption {
  max-width: 52%;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.35;
  text-align: right;
  word-break: break-word;
  hyphens: auto;
}

.dro-dash-yoy-chip--today .dro-dash-yoy-chip__val--caption {
  color: #047857;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__val--caption {
  color: #1e40af;
}

.dro-dash-yoy-chip__prefix {
  font-weight: 800;
  color: #94a3b8;
}

.dro-dash-yoy-chip__date {
  font-weight: 800;
  color: #64748b;
}

.dro-dash-yoy-chip__week {
  font-size: 12px;
  font-weight: 900;
  color: #0f172a;
}

.dro-dash-yoy-chip__val {
  font-size: 1rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  line-height: 1.35;
}

.dro-dash-yoy-chip__val--up {
  color: #047857;
}

.dro-dash-yoy-chip__val--down {
  color: #be123c;
}

.dro-dash-yoy-chip__val--flat {
  color: #475569;
}

.dro-dash-yoy-chip__val--muted {
  color: #94a3b8;
  font-weight: 800;
  font-size: 12px;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__val--up {
  color: #1d4ed8;
}

.dro-dash-kpi__hero {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.15rem 0.35rem;
  min-width: 0;
}

.dro-dash-kpi__hero--compact {
  margin-bottom: 0;
}

.dro-dash-kpi__hero-num {
  font-size: clamp(3rem, 7.5vw, 3.85rem);
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.05em;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.dro-dash-kpi__hero-num--dark {
  font-size: clamp(2.85rem, 6.8vw, 3.45rem);
}

.dro-dash-kpi--tomorrow .dro-dash-kpi__hero-num {
  color: #0f172a;
}

.dro-dash-kpi__hero-suffix {
  font-size: 1.05rem;
  font-weight: 800;
  color: #94a3b8;
  margin-left: 0.15rem;
}

.dro-dash-kpi__side {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  flex-shrink: 0;
}

/** 右侧列顶部：大表到家配送点数量（排除门店自提分组） */
.dro-dash-kpi__side-stop-line {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 0.35rem;
  font-size: 13px;
  font-weight: 800;
  color: #64748b;
  min-height: 1.35rem;
}

.dro-dash-kpi__side-stop-n {
  font-size: 1.05rem;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.dro-dash-kpi__side-stop-lbl {
  font-weight: 800;
  color: #64748b;
}

.dro-dash-kpi__side-stop-placeholder {
  font-size: 1.05rem;
  font-weight: 800;
  color: #94a3b8;
}

.dro-dash-kpi__side-row {
  display: flex;
  align-items: baseline;
  justify-content: flex-end;
  gap: 0.35rem;
  font-size: 13px;
  font-weight: 800;
  color: #64748b;
}

.dro-dash-kpi__side-n {
  font-size: 1.05rem;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.dro-dash-kpi__side-n--emerald {
  color: #059669;
}

.dro-dash-kpi__side-n--blue {
  color: #2563eb;
}

.dro-dash-kpi__side-n--ink {
  color: #334155;
}

.dro-dash-kpi__side-txt {
  font-weight: 800;
  color: #64748b;
}

.dro-dash-kpi__side-txt--soft {
  color: #94a3b8;
  font-weight: 800;
}

.dro-dash-kpi__stat-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(241, 245, 249, 0.95);
  flex-shrink: 0;
}

.dro-dash-kpi__stat-row--plans {
  align-items: stretch;
}

/** 今日/明日：首行双 chip，次行单次零售 + 同比上周并排 */
.dro-dash-kpi__stat-row--chips-then-yoy {
  grid-template-columns: 1fr 1fr;
  align-items: stretch;
}

.dro-dash-kpi__stat-row--chips-then-yoy .dro-dash-yoy-chip {
  margin-top: 0;
  padding-top: 0.65rem;
  padding-bottom: 0.65rem;
  min-width: 0;
}

.dro-dash-chip {
  border-radius: 1rem;
  padding: 0.65rem 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid transparent;
}

.dro-dash-chip__k {
  font-size: 13px;
  font-weight: 800;
}

.dro-dash-chip__v {
  font-size: 1rem;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.dro-dash-chip__v small {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.9;
}

.dro-dash-chip--amber {
  background: rgba(255, 251, 235, 0.85);
  border-color: rgba(252, 211, 77, 0.35);
  color: #b45309;
}

.dro-dash-chip--amber .dro-dash-chip__v {
  color: #b45309;
}

.dro-dash-chip--rose {
  background: rgba(255, 241, 242, 0.85);
  border-color: rgba(251, 207, 232, 0.5);
  color: #be123c;
}

.dro-dash-chip--rose .dro-dash-chip__v {
  color: #be123c;
}

.dro-dash-chip--emerald {
  background: rgba(236, 253, 245, 0.85);
  border-color: rgba(16, 185, 129, 0.35);
  color: #047857;
}

.dro-dash-chip--emerald .dro-dash-chip__v {
  color: #047857;
}

.dro-dash-chip--slate {
  background: #f8fafc;
  border-color: #e2e8f0;
  color: #64748b;
}

.dro-dash-chip--slate .dro-dash-chip__v {
  color: #334155;
}

.dro-dash-chip--faded {
  opacity: 0.58;
}

.dro-dash-chip--faded .dro-dash-chip__k,
.dro-dash-chip--faded .dro-dash-chip__v {
  color: #94a3b8;
  font-weight: 700;
}

.dro-dash-kpi__maplib-mid {
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  margin-bottom: 0;
}

.dro-dash-kpi__maplib-top {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
  flex-shrink: 0;
}

.dro-dash-kpi__rate {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 800;
  color: #059669;
  background: #ecfdf5;
  padding: 0.25rem 0.55rem;
  border-radius: 0.375rem;
}

.dro-map-bar {
  display: flex;
  width: 100%;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: #f1f5f9;
  flex-shrink: 0;
}

.dro-map-bar__seg {
  height: 100%;
  min-width: 0;
  transition: width 0.45s ease;
}

.dro-map-bar__seg--month {
  background: #3b82f6;
}

.dro-map-bar__seg--week {
  background: #10b981;
}

.dro-map-bar__seg--exp-m {
  background: #fbbf24;
}

.dro-map-bar__seg--exp-w {
  background: #cbd5e1;
}

.dro-dash-plan-box {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 1rem;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-height: 0;
}

.dro-dash-plan-box__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
}

.dro-dash-plan-box__t {
  font-size: 13px;
  font-weight: 900;
  color: #334155;
}

.dro-dash-plan-box__sum {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
}

.dro-dash-plan-box__rows {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.dro-dash-plan-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
  font-weight: 800;
}

.dro-dash-plan-row__k {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #94a3b8;
}

.dro-dash-plan-row__v {
  font-variant-numeric: tabular-nums;
}

.dro-dash-plan-row__v--emerald {
  color: #059669;
}

.dro-dash-plan-row__v--muted {
  color: #94a3b8;
}

.dro-dash-plan-row__v--blue {
  color: #2563eb;
}

.dro-dash-plan-row__v--amber {
  color: #d97706;
}

.dro-dash-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: #10b981;
  flex-shrink: 0;
}

.dro-dash-dot--slate {
  background: #cbd5e1;
}

.dro-dash-dot--blue {
  background: #3b82f6;
}

.dro-dash-dot--amber {
  background: #fbbf24;
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

/** 续费卡：明日备餐嵌套区块（原先双栏收窄时的样式基类） */
.dro-stat-card-metric-wrap--prep-rows--nested {
  min-height: 0;
  margin-top: 0.1rem;
  padding: 0.15rem 0 0;
  gap: 0.35rem;
}

.dro-stat-card-asset-mid--renewal-tomorrow-only {
  justify-content: center;
  align-items: center;
  width: 100%;
}

.dro-stat-card-split-cell--tomorrow-full {
  flex: 1 1 100%;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}

.dro-stat-card-metric-wrap--prep-rows--renewal-full {
  min-height: 3.5rem;
  gap: 0.5rem;
  margin-top: 0.2rem;
}

.dro-stat-card--renewal-prep .dro-stat-card-metric-wrap--prep-rows--renewal-full .dro-stat-card-num--nest-xl {
  font-size: 2.95rem;
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
  min-width: 0;
  flex: 1 1 auto;
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
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dro-map-pickup-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
}

.dro-map-pickup-label {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/**
 * 切勿给 el-checkbox 根节点写死宽高：会把整块控件压成极小区域，文案「自提显示」被裁切。
 * 勾选态颜色通过内部元素覆盖。
 */
.dro-map-pickup-toggle :deep(.el-checkbox__label) {
  font-size: 13px;
  font-weight: 700;
  color: #475569;
}

.dro-map-pickup-toggle :deep(.el-checkbox__input.is-checked .el-checkbox__inner) {
  background-color: #10b981;
  border-color: #10b981;
}

.dro-map-pickup-toggle :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: #0f766e;
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
