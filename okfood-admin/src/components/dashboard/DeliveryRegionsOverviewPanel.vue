<script setup>
import { computed, onMounted, ref } from 'vue'
import { Users, TrendingUp, RefreshCw } from 'lucide-vue-next'
import { useDeliveryRegionMapOverview } from '../../composables/useDeliveryRegionMapOverview.js'
import { UNASSIGNED_AREA_LABEL } from '../../utils/regionAssignment.js'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useAnimatedInteger } from '../../composables/useAnimatedInteger.js'
import DashboardPickupKitchenPanel from './DashboardPickupKitchenPanel.vue'
import DayStockAdjustmentModal from './DayStockAdjustmentModal.vue'
import { useDayStockAdjustments } from '../../composables/useDayStockAdjustments.js'

/** 营业概览顶卡数字条（请假/备餐/当日过期份数）；与 dashboard-summary / 归档接口回填 */
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

/** @param {number | null | undefined} part @param {number | null | undefined} cap */
function distributionStackWidth(part, cap) {
  const p = Number(part)
  const c = Number(cap)
  if (!Number.isFinite(c) || c <= 0 || !Number.isFinite(p) || p <= 0) return '0%'
  return `${Math.min(100, (p / c) * 100).toFixed(1)}%`
}

/** @param {Record<string, unknown> | null} m */
function prepMetricsBreakdown(m) {
  if (!m) return null
  const hp = Number(m.home_pending_meal_total) || 0
  const hd = Number(m.home_delivered_meal_total) || 0
  const pu = Number(m.pickup_meal_total) || 0
  return { total: hp + hd + pu, delivery: hp + hd, pickup: pu }
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
  return t.replace(/^较上周[\s\u3000]*/, '').replace(/份$/u, '').trim()
}

/** 备餐份数同比上周说明（dashboard-summary）；展示在同比条右侧 */
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

/** 顶卡右上角剩余可售：图标胶囊的无障碍/悬停文案 */
function formatSellableGateLabel(qty) {
  if (qty == null) return '剩余可售：—'
  if (qty > 0) return `剩余可售：${qty}份（可售）`
  return '剩余可售：0份（已售罄）'
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

/** ISO 日历日 YYYY-MM-DD 的次日（UTC，与业务日一致） */
function addOneDayIso(iso) {
  return shiftIsoYmd(iso, 1)
}

/** 上海今日（概览锚定日上限），YYYY-MM-DD */
const shanghaiTodayIso = computed(() => {
  const raw = summaryMeta.value?.shanghai_today
  if (raw == null || String(raw).trim() === '') return ''
  const s = String(raw).trim().slice(0, 10)
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : ''
})

/** ISO 日历日 YYYY-MM-DD 加减天数（UTC，与业务日一致） */
function shiftIsoYmd(iso, deltaDays) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso).trim().slice(0, 10))
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  dt.setUTCDate(dt.getUTCDate() + deltaDays)
  return `${dt.getUTCFullYear()}-${String(dt.getUTCMonth() + 1).padStart(2, '0')}-${String(
    dt.getUTCDate(),
  ).padStart(2, '0')}`
}

const dashboardDayNavBusy = computed(() => dashboardStatsLoading.value)

/** 上一日 / 下一日快捷切换营业锚定日（含未来日，与 dashboard-summary 口径一致） */
async function shiftDashboardAnchorDay(delta) {
  const base =
    businessAnchorIsoNormalized.value ||
    shanghaiTodayIso.value ||
    summaryAnchorDate.value.trim().slice(0, 10)
  const next = shiftIsoYmd(base, delta)
  if (!next) return
  summaryAnchorDate.value = next
  await fetchDashboardSummary()
}

/** 刷新营业概览顶卡数据（保持当前锚定日） */
function refreshDashboardOverview() {
  void fetchDashboardSummary()
}

/** 后厨日总份数保存后：先乐观更新顶卡，再拉 dashboard-summary 与服务端对齐 */
function onMenuDayStockSaved(payload) {
  if (summaryMeta.value && payload && typeof payload === 'object') {
    const next = { ...summaryMeta.value }
    if (Number.isFinite(payload.today) && payload.today >= 0) {
      next.today_menu_day_total_stock = Math.trunc(payload.today)
    }
    if (Number.isFinite(payload.tomorrow) && payload.tomorrow >= 0) {
      next.tomorrow_menu_day_total_stock = Math.trunc(payload.tomorrow)
    }
    if (Number.isFinite(payload.dayAfterTomorrow) && payload.dayAfterTomorrow >= 0) {
      next.day_after_tomorrow_menu_day_total_stock = Math.trunc(payload.dayAfterTomorrow)
    }
    if (Number.isFinite(payload.todayDinner) && payload.todayDinner >= 0) {
      next.today_dinner_menu_day_total_stock = Math.trunc(payload.todayDinner)
    }
    if (Number.isFinite(payload.tomorrowDinner) && payload.tomorrowDinner >= 0) {
      next.tomorrow_dinner_menu_day_total_stock = Math.trunc(payload.tomorrowDinner)
    }
    if (Number.isFinite(payload.dayAfterTomorrowDinner) && payload.dayAfterTomorrowDinner >= 0) {
      next.day_after_tomorrow_dinner_menu_day_total_stock = Math.trunc(payload.dayAfterTomorrowDinner)
    }
    summaryMeta.value = next
  }
  void fetchDashboardSummary()
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
      { label: '当日过期份数', value: te, unit: '份', mapFilter: null },
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

const {
  loading,
  error,
  load,
  regionsSorted,
  regionColorById,
  membersCountByArea,
  mapEligiblePlanCounts,
} = useDeliveryRegionMapOverview()

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

/** 当日已消费殆尽的末次出餐份数（份数，非人数） */
const expireMealPortions = computed(() => Number(dashboardStats.value[4]?.value) || 0)

/** 今日单次零售总计数量（dashboard-summary.today_single_retail_total_quantity） */
const todaySingleRetailTotalCount = computed(
  () => Number(summaryMeta.value?.today_single_retail_total_quantity) || 0,
)
const todayLunchWasteTotal = computed(() => Number(summaryMeta.value?.today_lunch_waste_total) || 0)
const todayLunchRemainingDisplay = computed(() => {
  const v = summaryMeta.value?.today_lunch_remaining
  if (v != null && v !== '') {
    const n = Number(v)
    if (Number.isFinite(n)) return Math.max(0, Math.trunc(n))
  }
  return todaySellableQuantity.value
})
const dinnerMenuDayTotalStock = computed(() => {
  const v = summaryMeta.value?.today_dinner_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})
const todayDinnerPrepMetrics = computed(() => {
  const m = summaryMeta.value?.today_dinner_prep_metrics
  return m && typeof m === 'object' ? m : null
})
const todayDinnerDelivery = computed(() => {
  const b = prepMetricsBreakdown(todayDinnerPrepMetrics.value)
  return b != null ? b.delivery : null
})
const todayDinnerRetail = computed(
  () => Number(summaryMeta.value?.today_dinner_single_retail_total_quantity) || 0,
)
const todayDinnerWasteTotal = computed(() => Number(summaryMeta.value?.today_dinner_waste_total) || 0)
const todayDinnerRemaining = computed(() => {
  const v = summaryMeta.value?.today_dinner_remaining
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : null
})
const todayDinnerSoldTotal = computed(() => {
  if (todayDinnerDelivery.value == null) return null
  return Math.trunc(Number(todayDinnerDelivery.value)) + todayDinnerRetail.value
})

const {
  modalOpen: stockModalOpen,
  modalMealPeriod: stockModalMealPeriod,
  modalBusinessDate: stockModalBusinessDate,
  modalDelta: stockModalDelta,
  modalReason: stockModalReason,
  modalRemark: stockModalRemark,
  submitting: stockAdjustSubmitting,
  openAdjustModal: openStockAdjustModal,
  submitAdjustment: submitStockAdjustment,
} = useDayStockAdjustments({ onSuccess: () => fetchDashboardSummary() })

function openLunchStockAdjust() {
  openStockAdjustModal({
    businessDate: businessAnchorIsoNormalized.value || summaryAnchorDate.value,
    mealPeriod: 'lunch',
  })
}
function openDinnerStockAdjust() {
  openStockAdjustModal({
    businessDate: businessAnchorIsoNormalized.value || summaryAnchorDate.value,
    mealPeriod: 'dinner',
  })
}

/** 明日单次零售：锚定日次日已支付单次零售份数（dashboard-summary.tomorrow_single_retail_total_quantity） */
const tomorrowSingleRetailTotalCount = computed(
  () => Number(summaryMeta.value?.tomorrow_single_retail_total_quantity) || 0,
)

/** 锚定日周菜单「日总份数」（供后厨计划面板读取，与本周菜单配置同源） */
const menuDayTotalStock = computed(() => {
  const v = summaryMeta.value?.today_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

/** 锚定日次日周菜单「日总份数」（供后厨计划面板读取） */
const menuDayTotalStockTomorrow = computed(() => {
  const v = summaryMeta.value?.tomorrow_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

/** 锚定日后天周菜单「日总份数」（供后厨计划面板读取） */
const menuDayTotalStockDayAfterTomorrow = computed(() => {
  const v = summaryMeta.value?.day_after_tomorrow_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

const menuDayTotalStockDinner = computed(() => {
  const v = summaryMeta.value?.today_dinner_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

const menuDayTotalStockTomorrowDinner = computed(() => {
  const v = summaryMeta.value?.tomorrow_dinner_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

const menuDayTotalStockDayAfterTomorrowDinner = computed(() => {
  const v = summaryMeta.value?.day_after_tomorrow_dinner_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

/** 锚定日次日 ISO（YYYY-MM-DD） */
const businessAnchorTomorrowIso = computed(() =>
  businessAnchorIsoNormalized.value ? addOneDayIso(businessAnchorIsoNormalized.value) : '',
)

/** 锚定日后天 ISO（YYYY-MM-DD） */
const businessAnchorDayAfterTomorrowIso = computed(() =>
  businessAnchorTomorrowIso.value ? addOneDayIso(businessAnchorTomorrowIso.value) : '',
)

/** 配送餐=到家待送达+已送达；自提=门店自提分组 */
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

/** 可卖数量 = 日总份数 − 配送 − 自提 − 单次零售（日总份数未配置时为 null） */
const todaySellableQuantity = computed(() => {
  const stock = menuDayTotalStock.value
  if (stock == null) return null
  if (todayMealsDelivery.value == null || todayMealsPickup.value == null) return null
  return Math.max(
    0,
    stock -
      Math.trunc(Number(todayMealsDelivery.value)) -
      Math.trunc(Number(todayMealsPickup.value)) -
      todaySingleRetailTotalCount.value,
  )
})

/** 今日已售出 = 同城配送 + 门店自提 + 单次零售 */
const todaySoldTotal = computed(() => {
  if (todayMealsDelivery.value == null || todayMealsPickup.value == null) return null
  return (
    Math.trunc(Number(todayMealsDelivery.value)) +
    Math.trunc(Number(todayMealsPickup.value)) +
    todaySingleRetailTotalCount.value
  )
})

/** 明日顶卡「总销售量」= 明日配送份数 + 明日单次零售 + 明日门店自提 */
const cardTomorrowPrepTotal = computed(() => {
  const b = prepMetricsBreakdown(tomorrowPrepMetrics.value)
  const retail = tomorrowSingleRetailTotalCount.value
  if (b != null) {
    return Math.max(
      0,
      Math.trunc(b.delivery) + Math.trunc(retail) + Math.trunc(b.pickup),
    )
  }
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

/** 明日可卖数量 = 次日日总份数 − 配送 − 自提 − 单次零售（未配置日总份数时为 null） */
const tomorrowSellableQuantity = computed(() => {
  const stock = menuDayTotalStockTomorrow.value
  if (stock == null) return null
  if (tomorrowPrepDelivery.value == null || tomorrowPrepPickup.value == null) return null
  return Math.max(
    0,
    stock -
      Math.trunc(Number(tomorrowPrepDelivery.value)) -
      Math.trunc(Number(tomorrowPrepPickup.value)) -
      tomorrowSingleRetailTotalCount.value,
  )
})

/** 明日顶卡链条主值：优先次日日总份数，否则回退为预测总销售量 */
const tomorrowDistributionMainTotal = computed(() => {
  if (menuDayTotalStockTomorrow.value != null) return menuDayTotalStockTomorrow.value
  return cardTomorrowPrepTotal.value
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

/** 续卡率：同一卡型二次及以上入账人数 ÷ 曾有过该卡型入账人数（含提前续卡） */
function membershipReorderRatePct(reorderMembers, baseMembers) {
  const n = Math.max(0, Math.trunc(Number(reorderMembers) || 0))
  const base = Math.max(0, Math.trunc(Number(baseMembers) || 0))
  if (base <= 0) return null
  return Math.round((n / base) * 1000) / 10
}

function formatRenewalRatePct(v) {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return `${Number(v).toFixed(1)}%`
}

const mapLibWeeklyRenewalRatePct = computed(() => {
  if (!mapLibFromApi.value) return null
  return membershipReorderRatePct(
    summaryMeta.value?.weekly_card_reorder_members,
    summaryMeta.value?.weekly_card_reorder_base_members,
  )
})
const mapLibMonthlyRenewalRatePct = computed(() => {
  if (!mapLibFromApi.value) return null
  return membershipReorderRatePct(
    summaryMeta.value?.monthly_card_reorder_members,
    summaryMeta.value?.monthly_card_reorder_base_members,
  )
})

const mapLibActivityRatePct = computed(() => {
  const t = mapLibTotal.value
  if (t <= 0) return 0
  return Math.round(((mapLibActiveWeekly.value + mapLibActiveMonthly.value) / t) * 100)
})

/** 有效会员总数（周卡有效 + 月卡有效，作占比分母） */
const mapLibActiveMemberTotal = computed(
  () => mapLibActiveWeekly.value + mapLibActiveMonthly.value,
)

/** 有效会员中周卡人数占比 */
const mapLibWeeklyActiveSharePct = computed(() => {
  const t = mapLibActiveMemberTotal.value
  if (t <= 0) return 0
  return Math.round((mapLibActiveWeekly.value / t) * 100)
})

/** 有效会员中月卡人数占比 */
const mapLibMonthlyActiveSharePct = computed(() => {
  const t = mapLibActiveMemberTotal.value
  if (t <= 0) return 0
  return Math.round((mapLibActiveMonthly.value / t) * 100)
})

const MAP_LIB_RING_R = 34
const MAP_LIB_RING_CIRCUMFERENCE = 2 * Math.PI * MAP_LIB_RING_R

/**
 * SVG 圆环进度（参考稿：r=34、描边 6、-90deg 起笔）
 * @param {number} pct 0–100
 */
function buildMapLibRingStroke(pct) {
  const p = Math.min(100, Math.max(0, Math.round(Number(pct) || 0)))
  return {
    dasharray: MAP_LIB_RING_CIRCUMFERENCE,
    dashoffset: MAP_LIB_RING_CIRCUMFERENCE * (1 - p / 100),
  }
}

const mapLibWeeklyRingStroke = computed(() =>
  buildMapLibRingStroke(mapLibWeeklyActiveSharePct.value),
)
const mapLibMonthlyRingStroke = computed(() =>
  buildMapLibRingStroke(mapLibMonthlyActiveSharePct.value),
)

const mapLibRingAria = computed(() => {
  const t = mapLibActiveMemberTotal.value
  const aw = mapLibActiveWeekly.value
  const am = mapLibActiveMonthly.value
  if (t <= 0) return '有效会员周卡、月卡占比：暂无数据'
  return `有效会员 ${t} 人：周卡占比 ${mapLibWeeklyActiveSharePct.value}%（${aw} 人），月卡占比 ${mapLibMonthlyActiveSharePct.value}%（${am} 人）`
})

/** 概览数字滚动展示（加载 / 刷新 / 换日后过渡到新值） */
const todayLeaveAnimated = useAnimatedInteger(() => summarySlice.value.todayLeave, { duration: 620 })
const tomorrowLeaveAnimated = useAnimatedInteger(() => summarySlice.value.tomorrowLeave, { duration: 620 })
const expireMealPortionsAnimated = useAnimatedInteger(() => expireMealPortions.value, { duration: 620 })
const todaySingleRetailTotalAnimated = useAnimatedInteger(() => todaySingleRetailTotalCount.value, {
  duration: 620,
})
const tomorrowSingleRetailTotalAnimated = useAnimatedInteger(
  () => tomorrowSingleRetailTotalCount.value,
  { duration: 620 },
)
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

onMounted(async () => {
  // 概览 KPI 优先；地图聚合较重，稍后再拉，避免同屏争抢 DB/连接
  await fetchDashboardSummary()
  void load()
})
</script>

<template>
  <section class="dro-page dro-page--modern">

    <p v-if="summaryMeta?.from_snapshot" class="dro-snapshot-hint">
      已显示归档数据（与智能配送大表口径对齐的首读留存）。
      <template v-if="summaryMeta.snapshot_recorded_at">
        归档时间 {{ summaryMeta.snapshot_recorded_at }}。
      </template>
    </p>

    <p v-if="dashboardStatsLoading && !summaryMeta" class="dro-loading">正在加载营业概览…</p>
    <p v-else-if="!dashboardStats.length && !loading" class="dro-loading">
      暂无营业概览数据，片区覆盖仍可查看。
    </p>

    <!-- 三张概览卡：今日备餐 / 明日预测 / 地图会员库（样式对齐设计稿） -->
    <div
      v-if="(!dashboardStatsLoading && dashboardStats.length) || showDeliveryMetrics"
      class="dro-dash-stat-grid"
    >
      <article class="dro-dash-kpi" :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }">
        <div class="dro-dash-kpi__head">
          <div class="dro-dash-kpi__tags">
            <span class="dro-dash-pill dro-dash-pill--emerald">
              {{ summaryIsLiveToday ? '今日总盘' : '当日' }} · {{ businessAnchorMdDisplay || '—'
              }}<template v-if="businessAnchorWeekdayDisplay">
                {{ businessAnchorWeekdayDisplay }}</template
              >
            </span>
            <nav class="dro-dash-day-nav" aria-label="切换营业日">
              <button
                type="button"
                class="dro-dash-day-nav-btn"
                :disabled="dashboardDayNavBusy"
                @click="shiftDashboardAnchorDay(-1)"
              >
                上一日
              </button>
              <button
                type="button"
                class="dro-dash-day-nav-btn"
                :disabled="dashboardDayNavBusy"
                @click="shiftDashboardAnchorDay(1)"
              >
                下一日
              </button>
            </nav>
          </div>
          <button
            type="button"
            class="dro-dash-kpi__ico-badge dro-dash-kpi__ico-badge--emerald dro-dash-kpi__ico-badge--action"
            :disabled="dashboardStatsLoading"
            title="刷新营业概览"
            aria-label="刷新营业概览"
            @click="refreshDashboardOverview"
          >
            <RefreshCw
              :size="18"
              :class="{ 'dro-dash-refresh-spin': dashboardStatsLoading }"
              aria-hidden="true"
            />
          </button>
        </div>
        <div class="dro-dash-kpi__hero-metric">
          <span class="dro-dash-kpi__hero-metric-num">{{
            menuDayTotalStock != null ? menuDayTotalStock : '—'
          }}</span>
          <small class="dro-dash-kpi__hero-metric-suffix">份-后厨产出量</small>
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--distribution-chain">
          <div class="dro-dash-kpi__metric-top">
            <div
              class="dro-dash-distribution-chain"
              role="note"
              :aria-label="
                menuDayTotalStock != null
                  ? `${menuDayTotalStock}份当日出餐量等于配送、自提、单次零售与可卖数量之和`
                  : '当日出餐量未配置'
              "
            >
              <div class="dro-dash-chain-node-header">
                <span class="dro-dash-chain-node-label">配额去向拆解线</span>
                <span class="dro-dash-chain-node dro-dash-chain-node--main">
                  已售出 {{ todaySoldTotal != null ? `${todaySoldTotal}份` : '—' }}
                </span>
              </div>
              <div class="dro-dash-stacked-bar" aria-hidden="true">
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--deliver"
                  :style="{
                    width: distributionStackWidth(todayMealsDelivery, menuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--pickup"
                  :style="{
                    width: distributionStackWidth(todayMealsPickup, menuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--retail"
                  :style="{
                    width: distributionStackWidth(todaySingleRetailTotalCount, menuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--sellable"
                  :class="{
                    'dro-dash-stacked-bar__seg--sellable-empty':
                      todaySellableQuantity != null && todaySellableQuantity <= 0,
                  }"
                  :style="{
                    width: distributionStackWidth(todayLunchRemainingDisplay, menuDayTotalStock),
                  }"
                />
              </div>
              <div class="dro-dash-branch-pill-grid">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    todayMealsDelivery == null ? '—' : `${Math.trunc(Number(todayMealsDelivery))}`
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    todayMealsPickup == null ? '—' : `${Math.trunc(Number(todayMealsPickup))}`
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ todaySingleRetailTotalCount }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--waste" aria-hidden="true" />损耗</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ todayLunchWasteTotal }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--sellable" aria-hidden="true" />剩余</span
                  >
                  <span
                    class="dro-dash-branch-pill__val dro-dash-branch-pill__val--sellable"
                    :class="{
                      'dro-dash-branch-pill__val--sellable-muted':
                        todayLunchRemainingDisplay != null && todayLunchRemainingDisplay <= 0,
                    }"
                    >{{
                      todayLunchRemainingDisplay == null ? '—' : `${todayLunchRemainingDisplay}`
                    }}</span
                  >
                </div>
              </div>
            </div>
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__foot-row">
          <button type="button" class="dro-dash-adjust-btn" @click="openLunchStockAdjust">报损耗</button>
        </div>
        <div class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--chips-then-yoy">
          <div class="dro-dash-chip dro-dash-chip--amber">
            <span class="dro-dash-chip__k">今日请假</span>
            <span class="dro-dash-chip__v">{{ todayLeaveAnimated }} <small></small></span>
          </div>
          <div class="dro-dash-chip dro-dash-chip--rose">
            <span class="dro-dash-chip__k">当日过期</span>
            <span class="dro-dash-chip__v">{{ expireMealPortionsAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--blue"
            role="status"
            :aria-label="`单次零售 ${todaySingleRetailTotalCount} `"
          >
            <span class="dro-dash-chip__k">单次零售</span>
            <span class="dro-dash-chip__v">{{ todaySingleRetailTotalAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-yoy-chip dro-dash-yoy-chip--today"
            role="status"
            :aria-label="
              '同比上周，' +
              (todayMealsWeekOverWeekCaption || formatYoyWeekHeadsText(todayPrepHeadsYoyDelta))
            "
          >
            <div class="dro-dash-yoy-chip__left">
              <span class="dro-dash-yoy-chip__prefix">同比上周</span>
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

      <article class="dro-dash-kpi dro-dash-kpi--dinner" :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }">
        <div class="dro-dash-kpi__head">
          <div class="dro-dash-kpi__tags">
            <span class="dro-dash-pill dro-dash-pill--violet">晚餐总盘 · {{ businessAnchorMdDisplay || '—' }}</span>
          </div>
        </div>
        <div class="dro-dash-kpi__hero-metric">
          <span class="dro-dash-kpi__hero-metric-num">{{
            dinnerMenuDayTotalStock != null ? dinnerMenuDayTotalStock : '—'
          }}</span>
          <small class="dro-dash-kpi__hero-metric-suffix">份-后厨产出量</small>
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--distribution-chain">
          <div class="dro-dash-chain-node-header">
            <span class="dro-dash-chain-node-label">配额去向拆解线</span>
            <span class="dro-dash-chain-node dro-dash-chain-node--main">
              已售出 {{ todayDinnerSoldTotal != null ? `${todayDinnerSoldTotal}份` : '—' }}
            </span>
          </div>
          <div class="dro-dash-branch-pill-grid">
            <div class="dro-dash-branch-pill">
              <span class="dro-dash-branch-pill__lbl">配送</span>
              <span class="dro-dash-branch-pill__val">{{
                todayDinnerDelivery == null ? '—' : `${Math.trunc(Number(todayDinnerDelivery))}`
              }}</span>
            </div>
            <div class="dro-dash-branch-pill">
              <span class="dro-dash-branch-pill__lbl">零售</span>
              <span class="dro-dash-branch-pill__val">{{ todayDinnerRetail }}</span>
            </div>
            <div class="dro-dash-branch-pill">
              <span class="dro-dash-branch-pill__lbl">损耗</span>
              <span class="dro-dash-branch-pill__val">{{ todayDinnerWasteTotal }}</span>
            </div>
            <div class="dro-dash-branch-pill">
              <span class="dro-dash-branch-pill__lbl">剩余</span>
              <span class="dro-dash-branch-pill__val">{{
                todayDinnerRemaining == null ? '—' : `${todayDinnerRemaining}`
              }}</span>
            </div>
          </div>
        </div>
        <div class="dro-dash-kpi__foot-row">
          <button type="button" class="dro-dash-adjust-btn" @click="openDinnerStockAdjust">报损耗</button>
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
          </div>
          <span
            class="dro-dash-kpi__ico-badge dro-dash-kpi__ico-badge--blue"
            role="status"
            :title="formatSellableGateLabel(tomorrowSellableQuantity)"
            :aria-label="formatSellableGateLabel(tomorrowSellableQuantity)"
          >
            <TrendingUp :size="18" aria-hidden="true" />
          </span>
        </div>
        <div class="dro-dash-kpi__hero-metric">
          <span class="dro-dash-kpi__hero-metric-num">{{ tomorrowDistributionMainTotal }}</span>
          <small class="dro-dash-kpi__hero-metric-suffix">份-后厨产出量</small>
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--distribution-chain">
          <div class="dro-dash-kpi__metric-top">
            <div
              class="dro-dash-distribution-chain dro-dash-distribution-chain--tomorrow"
              role="note"
              :aria-label="`${tomorrowDistributionMainTotal}份明日预测等于同城配送、门店自提、单次零售与可卖数量之和`"
            >
              <div class="dro-dash-chain-node-header">
                <span class="dro-dash-chain-node-label">明日排产指标线</span>
                <span class="dro-dash-chain-node dro-dash-chain-node--main dro-dash-chain-node--main-blue">
                  已售出 {{ cardTomorrowPrepTotal }}份
                </span>
              </div>
              <div class="dro-dash-stacked-bar" aria-hidden="true">
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--deliver"
                  :style="{
                    width: distributionStackWidth(tomorrowPrepDelivery, tomorrowDistributionMainTotal),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--pickup"
                  :style="{
                    width: distributionStackWidth(tomorrowPrepPickup, tomorrowDistributionMainTotal),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--retail"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowSingleRetailTotalCount,
                      tomorrowDistributionMainTotal,
                    ),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--sellable"
                  :class="{
                    'dro-dash-stacked-bar__seg--sellable-empty':
                      tomorrowSellableQuantity != null && tomorrowSellableQuantity <= 0,
                  }"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowSellableQuantity,
                      tomorrowDistributionMainTotal,
                    ),
                  }"
                />
              </div>
              <div class="dro-dash-branch-pill-grid">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    tomorrowPrepDelivery == null ? '—' : `${Math.trunc(Number(tomorrowPrepDelivery))}`
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    tomorrowPrepPickup == null ? '—' : `${Math.trunc(Number(tomorrowPrepPickup))}`
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ tomorrowSingleRetailTotalCount }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--sellable" aria-hidden="true" />剩余</span
                  >
                  <span
                    class="dro-dash-branch-pill__val dro-dash-branch-pill__val--sellable dro-dash-branch-pill__val--sellable-blue"
                    :class="{
                      'dro-dash-branch-pill__val--sellable-muted':
                        tomorrowSellableQuantity != null && tomorrowSellableQuantity <= 0,
                    }"
                    >{{
                      tomorrowSellableQuantity == null ? '—' : `${tomorrowSellableQuantity}`
                    }}</span
                  >
                </div>
              </div>
            </div>
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--chips-then-yoy">
          <div class="dro-dash-chip dro-dash-chip--amber">
            <span class="dro-dash-chip__k">明日请假</span>
            <span class="dro-dash-chip__v">{{ tomorrowLeaveAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--rose"
            :class="{ 'dro-dash-chip--faded': tomorrowFirstMealNewCount === 0 }"
          >
            <span class="dro-dash-chip__k">首餐新客</span>
            <span class="dro-dash-chip__v">{{ tomorrowFirstMealNewAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--blue"
            role="status"
            :aria-label="`单次零售 ${tomorrowSingleRetailTotalCount} `"
          >
            <span class="dro-dash-chip__k">单次零售</span>
            <span class="dro-dash-chip__v">{{ tomorrowSingleRetailTotalAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-yoy-chip dro-dash-yoy-chip--tomorrow"
            role="status"
            :aria-label="
              '同比上周，' +
              (tomorrowMealsWeekOverWeekCaption || formatYoyWeekHeadsText(tomorrowPrepHeadsYoyDelta))
            "
          >
            <div class="dro-dash-yoy-chip__left">
              <span class="dro-dash-yoy-chip__prefix">同比上周</span>
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
        <div class="dro-dash-kpi__hero-metric dro-dash-kpi__hero-metric--maplib">
          <span class="dro-dash-kpi__hero-metric-num">{{ mapLibTotalAnimated }}</span>
          <small class="dro-dash-kpi__hero-metric-suffix">位总会员</small>
          <span
            class="dro-dash-kpi__rate dro-dash-kpi__rate--maplib-end"
            role="status"
            :aria-label="`活跃率 ${mapLibActivityRatePct}%`"
            >活跃率 {{ mapLibActivityRatePct }}%</span
          >
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--maplib">
          <div class="dro-map-ring-panel" role="img" :aria-label="mapLibRingAria">
            <figure class="dro-map-ring">
              <div class="dro-map-ring__wrap">
                <svg class="dro-map-ring__svg" viewBox="0 0 80 80" aria-hidden="true">
                  <defs>
                    <linearGradient id="dro-map-ring-weekly" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#10b981" />
                      <stop offset="100%" stop-color="#34d399" />
                    </linearGradient>
                  </defs>
                  <circle
                    cx="40"
                    cy="40"
                    :r="MAP_LIB_RING_R"
                    stroke="#f1f5f9"
                    stroke-width="6"
                    fill="transparent"
                  />
                  <circle
                    cx="40"
                    cy="40"
                    :r="MAP_LIB_RING_R"
                    stroke="url(#dro-map-ring-weekly)"
                    stroke-width="6"
                    fill="transparent"
                    :stroke-dasharray="mapLibWeeklyRingStroke.dasharray"
                    :stroke-dashoffset="mapLibWeeklyRingStroke.dashoffset"
                    stroke-linecap="round"
                    class="dro-map-ring__progress dro-map-ring__progress--week"
                  />
                </svg>
                <span class="dro-map-ring__pct">{{ mapLibWeeklyActiveSharePct }}%</span>
              </div>
              <figcaption class="dro-map-ring__lbl">周卡比例</figcaption>
            </figure>
            <figure class="dro-map-ring">
              <div class="dro-map-ring__wrap">
                <svg class="dro-map-ring__svg" viewBox="0 0 80 80" aria-hidden="true">
                  <defs>
                    <linearGradient id="dro-map-ring-monthly" x1="0%" y1="0%" x2="100%" y2="100%">
                      <stop offset="0%" stop-color="#3b82f6" />
                      <stop offset="100%" stop-color="#60a5fa" />
                    </linearGradient>
                  </defs>
                  <circle
                    cx="40"
                    cy="40"
                    :r="MAP_LIB_RING_R"
                    stroke="#f1f5f9"
                    stroke-width="6"
                    fill="transparent"
                  />
                  <circle
                    cx="40"
                    cy="40"
                    :r="MAP_LIB_RING_R"
                    stroke="url(#dro-map-ring-monthly)"
                    stroke-width="6"
                    fill="transparent"
                    :stroke-dasharray="mapLibMonthlyRingStroke.dasharray"
                    :stroke-dashoffset="mapLibMonthlyRingStroke.dashoffset"
                    stroke-linecap="round"
                    class="dro-map-ring__progress dro-map-ring__progress--month"
                  />
                </svg>
                <span class="dro-map-ring__pct">{{ mapLibMonthlyActiveSharePct }}%</span>
              </div>
              <figcaption class="dro-map-ring__lbl">月卡比例</figcaption>
            </figure>
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
              <div
                class="dro-dash-plan-row dro-dash-plan-row--renewal"
                title="续卡率 = 同一卡型二次及以上购卡入账人数 ÷ 曾有过该卡型购卡入账人数（含提前续卡，如未用完又续）"
              >
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot dro-dash-dot--purple" />续卡率</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--renewal">{{
                  formatRenewalRatePct(mapLibWeeklyRenewalRatePct)
                }}</span>
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
              <div
                class="dro-dash-plan-row dro-dash-plan-row--renewal"
                title="续卡率 = 同一卡型二次及以上购卡入账人数 ÷ 曾有过该卡型购卡入账人数（含提前续卡，如未用完又续）"
              >
                <span class="dro-dash-plan-row__k"
                  ><i class="dro-dash-dot dro-dash-dot--purple" />续卡率</span
                >
                <span class="dro-dash-plan-row__v dro-dash-plan-row__v--renewal">{{
                  formatRenewalRatePct(mapLibMonthlyRenewalRatePct)
                }}</span>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <DashboardPickupKitchenPanel
      v-if="(!dashboardStatsLoading && dashboardStats.length) || showDeliveryMetrics"
      :business-date="businessAnchorIsoNormalized"
      :tomorrow-business-date="businessAnchorTomorrowIso"
      :day-after-tomorrow-business-date="businessAnchorDayAfterTomorrowIso"
      :menu-day-total-stock="menuDayTotalStock"
      :menu-day-total-stock-tomorrow="menuDayTotalStockTomorrow"
      :menu-day-total-stock-day-after-tomorrow="menuDayTotalStockDayAfterTomorrow"
      :menu-day-total-stock-dinner="menuDayTotalStockDinner"
      :menu-day-total-stock-tomorrow-dinner="menuDayTotalStockTomorrowDinner"
      :menu-day-total-stock-day-after-tomorrow-dinner="menuDayTotalStockDayAfterTomorrowDinner"
      :shanghai-today="String(summaryMeta?.shanghai_today || '')"
      :summary-loading="dashboardStatsLoading"
      @menu-day-stock-saved="onMenuDayStockSaved"
    />

    <p v-if="loading && !regionsSorted.length" class="dro-loading">加载配送数据…</p>
    <p v-else-if="error" class="dro-error">{{ error }}</p>

    <div v-else-if="showDeliveryMetrics" class="dro-rank-section">
      <article class="dro-rank-card dro-rank-card--horizontal" aria-label="片区覆盖排行">
        <div class="dro-rank-head">
          <h3 class="dro-rank-title">片区覆盖排行</h3>
          <TrendingUp :size="18" class="dro-rank-trend-ico" aria-hidden="true" />
        </div>
        <div class="dro-rank-grid">
          <div v-for="row in regionCoverageRows" :key="row.id" class="dro-rank-tile">
            <div class="dro-rank-tile__head">
              <p class="dro-rank-name">{{ row.name }}</p>
              <span class="dro-rank-pct">{{ row.coveragePercent }}%</span>
            </div>
            <p class="dro-rank-count">
              {{ row.memberCount }}
              <span class="dro-rank-count-unit">Member</span>
            </p>
            <div class="dro-rank-bar">
              <div
                class="dro-rank-bar-fill"
                :style="{ width: row.coveragePercent + '%', background: row.color }"
              />
            </div>
          </div>
        </div>
      </article>
    </div>
  </section>

  <DayStockAdjustmentModal
    :open="stockModalOpen"
    :meal-period="stockModalMealPeriod"
    :business-date="stockModalBusinessDate"
    :delta="stockModalDelta"
    :reason="stockModalReason"
    :remark="stockModalRemark"
    :submitting="stockAdjustSubmitting"
    @update:open="(v) => (stockModalOpen = v)"
    @update:delta="(v) => (stockModalDelta = v)"
    @update:reason="(v) => (stockModalReason = v)"
    @update:remark="(v) => (stockModalRemark = v)"
    @submit="submitStockAdjustment"
  />
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
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: stretch;
}

@media (min-width: 768px) {
  .dro-dash-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (min-width: 1120px) {
  .dro-dash-stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

/* ——— 配送区域总览：顶部三张 KPI 卡（对齐 Tailwind 参考稿） ——— */
.dro-dash-kpi {
  background: #fff;
  border: 1px solid #eaedf1;
  border-radius: 28px;
  padding: 1.5rem 1.75rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  min-height: 250px;
  height: 100%;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease,
    border-color 0.3s ease;
}

.dro-dash-kpi:not(.dro-dash-kpi--tomorrow):not(.dro-dash-kpi--maplib):not(.dro-dash-kpi--dinner) {
  border-top: 4px solid #0d5c46;
}

.dro-dash-kpi--dinner {
  border-top: 4px solid #7c3aed;
}

.dro-dash-kpi--dinner:hover {
  border-color: rgba(124, 58, 237, 0.25);
}

.dro-dash-kpi--tomorrow {
  border-top: 4px solid #3b82f6;
}

.dro-dash-kpi--maplib {
  border-top: 4px solid #7c3aed;
}

.dro-dash-kpi:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(148, 163, 184, 0.08);
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

.dro-dash-kpi__foot-row {
  display: flex;
  justify-content: flex-end;
  margin-top: auto;
  padding-top: 0.5rem;
}

.dro-dash-adjust-btn {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #475569;
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background 0.2s ease;
}

.dro-dash-adjust-btn:hover {
  border-color: #0d5c46;
  color: #0d5c46;
  background: #ecfdf5;
}

.dro-dash-kpi--dinner .dro-dash-adjust-btn:hover {
  border-color: #7c3aed;
  color: #7c3aed;
  background: #f5f3ff;
}

.dro-dash-kpi__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.25rem;
  gap: 0.5rem;
  flex-shrink: 0;
  min-height: 2rem;
}

/** 顶卡主数字：已售/预计 */
.dro-dash-kpi__hero-metric {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.15rem 0.35rem;
  margin: 0.25rem 0 0;
  line-height: 1.1;
}

.dro-dash-kpi__hero-metric-num {
  font-size: clamp(2.15rem, 5vw, 2.5rem);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  letter-spacing: -0.04em;
}

.dro-dash-kpi__hero-metric-suffix {
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
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

/* 今日总盘：上一日 / 下一日快捷切换 */
.dro-dash-day-nav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dro-dash-day-nav-btn {
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  font-size: 11px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease;
}

.dro-dash-day-nav-btn:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #334155;
}

.dro-dash-day-nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.dro-dash-day-nav-btn:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgba(100, 116, 139, 0.28);
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

/** 今日/明日顶卡：圆角底托图标（与右侧会员库纯线型图标区分） */
.dro-dash-kpi__ico-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  flex-shrink: 0;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.72) inset;
}

.dro-dash-kpi__ico-badge--emerald {
  background: rgba(236, 253, 245, 0.92);
  border: 1px solid rgba(167, 243, 208, 0.85);
  color: #059669;
}

button.dro-dash-kpi__ico-badge--action {
  cursor: pointer;
  padding: 0;
  margin: 0;
  outline: none;
}

button.dro-dash-kpi__ico-badge--action:hover:not(:disabled) {
  background: rgba(209, 250, 229, 0.95);
  border-color: rgba(110, 231, 183, 0.9);
}

button.dro-dash-kpi__ico-badge--action:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

button.dro-dash-kpi__ico-badge--action:focus-visible {
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.35);
}

.dro-dash-refresh-spin {
  animation: dro-dash-refresh-spin 0.85s linear infinite;
}

@keyframes dro-dash-refresh-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.dro-dash-kpi__ico-badge--blue {
  background: rgba(239, 246, 255, 0.92);
  border: 1px solid rgba(191, 219, 254, 0.85);
  color: #2563eb;
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0;
  flex: 0 0 auto;
  min-height: 0;
}

/** 左侧：总销售量主数字 */
.dro-dash-kpi__main-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.35rem;
  min-width: 0;
  flex: 1 1 auto;
}

.dro-dash-kpi__mid {
  display: grid;
  grid-template-rows: minmax(2.45rem, auto) minmax(2.55rem, auto) 8px minmax(0, 1fr);
  row-gap: 0.1rem;
  flex: 1 1 auto;
  min-height: 0;
  margin-bottom: 0;
  align-content: start;
}

/** 今日/明日顶卡：配额链条 */
.dro-dash-kpi__mid--distribution-chain {
  grid-template-rows: auto minmax(0, 1fr);
  margin-top: 0.65rem;
}

/** 地图会员库：周/月有效占比圆环 + 弹性留白 */
.dro-dash-kpi__mid--maplib {
  grid-template-rows: auto minmax(0, 1fr);
  margin-top: 0.15rem;
}

/** 主数字行与明日预测顶卡一致，活跃率仍靠右 */
.dro-dash-kpi__hero-metric--maplib {
  width: 100%;
}

.dro-dash-kpi__hero-metric--maplib .dro-dash-kpi__rate--maplib-end {
  margin-left: auto;
  align-self: center;
  flex-shrink: 0;
}

/** 有效会员周卡/月卡占比圆环（对齐参考稿 ring 面板） */
.dro-map-ring-panel {
  display: flex;
  justify-content: space-around;
  align-items: center;
  gap: 1rem;
  width: 100%;
  padding: 0.875rem 0.5rem;
  background: #fafbfc;
  border: 1px solid #eaedf1;
  border-radius: 20px;
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.01);
  flex-shrink: 0;
}

.dro-map-ring {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.375rem;
  min-width: 0;
}

.dro-map-ring__wrap {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dro-map-ring__svg {
  width: 80px;
  height: 80px;
  transform: rotate(-90deg);
}

.dro-map-ring__progress {
  transition: stroke-dashoffset 0.5s ease;
}

.dro-map-ring__progress--week {
  filter: drop-shadow(0 2px 4px rgba(16, 185, 129, 0.25));
}

.dro-map-ring__progress--month {
  filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.25));
}

.dro-map-ring__pct {
  position: absolute;
  font-family: var(--okfood-font-number);
  font-size: 15px;
  font-weight: 900;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  pointer-events: none;
}

.dro-map-ring__lbl {
  margin: 0;
  font-size: 11px;
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.05em;
}

/** 出餐流向链条（对齐参考稿 distribution-chain） */
.dro-dash-distribution-chain {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
  padding: 0.875rem 1.125rem;
  background: #f8fafc;
  border: 1px solid #eaedf1;
  border-radius: 20px;
}

.dro-dash-chain-node-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
}

.dro-dash-chain-node-label {
  font-size: 11px;
  font-weight: 900;
  color: #64748b;
}

.dro-dash-chain-node {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.25rem 0.625rem;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 900;
  line-height: 1.2;
  white-space: nowrap;
}

.dro-dash-chain-node--main {
  background: #0d5c46;
  color: #fff;
  box-shadow: 0 4px 10px rgba(13, 92, 70, 0.15);
}

.dro-dash-chain-node--main-blue {
  background: #3b82f6;
  box-shadow: 0 4px 10px rgba(59, 130, 246, 0.15);
}

/** 堆叠式比例流条 */
.dro-dash-stacked-bar {
  display: flex;
  width: 100%;
  height: 12px;
  background: #e2e8f0;
  border-radius: 999px;
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.05);
}

.dro-dash-stacked-bar__seg {
  height: 100%;
  transition: width 0.4s ease;
  flex-shrink: 0;
}

.dro-dash-stacked-bar__seg--deliver {
  background: #3b82f6;
}

.dro-dash-stacked-bar__seg--pickup {
  background: #8b5cf6;
}

.dro-dash-stacked-bar__seg--retail {
  background: #f59e0b;
}

.dro-dash-stacked-bar__seg--sellable {
  background: #10b981;
}

.dro-dash-stacked-bar__seg--sellable-empty {
  background: #cbd5e1;
}

.dro-dash-branch-pill-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.dro-dash-branch-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0.5rem 0.375rem;
  border-radius: 12px;
  border: 1px solid #eaedf1;
  background: #fff;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.dro-dash-branch-pill:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(148, 163, 184, 0.05);
}

.dro-dash-branch-pill__lbl {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-bottom: 0.125rem;
  font-size: 9px;
  font-weight: 900;
  color: #64748b;
  line-height: 1.2;
  text-align: center;
}

.dro-dash-branch-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dro-dash-branch-dot--deliver {
  background: #3b82f6;
}

.dro-dash-branch-dot--pickup {
  background: #8b5cf6;
}

.dro-dash-branch-dot--retail {
  background: #f59e0b;
}

.dro-dash-branch-dot--sellable {
  background: #10b981;
}

.dro-dash-branch-pill__val {
  font-size: 13px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
  color: #0f172a;
}

.dro-dash-branch-pill__val--sellable {
  color: #10b981;
}

.dro-dash-branch-pill__val--sellable-blue {
  color: #3b82f6;
}

.dro-dash-branch-pill__val--sellable-muted {
  color: #64748b;
}

/** 中间弹性区：三卡等高时把底部 chip / 周月明细顶到卡片最下沿 */
.dro-dash-kpi__mid-spacer {
  min-height: 0;
  width: 100%;
}

.dro-dash-kpi__hero-formula-wrap {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-self: end;
  min-height: 2.55rem;
  min-width: 0;
}
.dro-dash-kpi__mid .dro-dash-kpi__hero-formula--block {
  margin: 0;
}

/** 三卡主数字行 */
.dro-dash-kpi__metric-top {
  display: flex;
  align-items: stretch;
  justify-content: stretch;
  width: 100%;
  margin-bottom: 0;
  flex-shrink: 0;
  min-height: 0;
}

.dro-dash-kpi__mid .dro-dash-kpi__main {
  margin-bottom: 0.55rem;
}

.dro-prep-bar {
  display: flex;
  width: 100%;
  height: 6px;
  border-radius: 4px;
  overflow: hidden;
  background: #f1f5f9;
  flex-shrink: 0;
  align-self: stretch;
  margin-top: 0.75rem;
}

.dro-prep-bar__seg {
  height: 100%;
  min-width: 0;
  transition: width 0.45s ease;
}

.dro-prep-bar__seg--today-done {
  background: #0d5c46;
}

.dro-prep-bar__seg--today-pending {
  background: rgba(13, 92, 70, 0.28);
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

/* 明日卡片「同比上周」：与今日同比条同为翠绿系，便于对齐阅读 */
.dro-dash-yoy-chip--tomorrow {
  background: rgba(236, 253, 245, 0.94);
  border-color: rgba(16, 185, 129, 0.38);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.72) inset;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__prefix {
  color: #059669;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__date {
  color: #047857;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__week {
  color: #065f46;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__val--up {
  color: #047857;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__val--flat {
  color: #059669;
}

.dro-dash-yoy-chip--tomorrow .dro-dash-yoy-chip__val--muted {
  color: #0d9488;
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
  color: #047857;
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

.dro-dash-kpi__hero {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.15rem 0.35rem;
  min-width: 0;
}

/** 今日/明日顶卡：总值后同一行展示「总销售量 = 配送份数 + 单次零售 + 自提」拆解（窄屏可换行） */
.dro-dash-kpi__hero--total-out {
  flex-direction: row;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.35rem 0.65rem;
}

/** 今日/明日顶卡：主数字单独一行，公式在下方 */
.dro-dash-kpi__hero-formula--block {
  display: block;
  margin: 0;
  font-size: clamp(13px, 1.5vw, 15px);
  font-weight: 800;
  line-height: 1.3;
  letter-spacing: 0.02em;
  color: #475569;
}

/** 三卡公式区等高（wrap 承担 min-height；无 wrap 的明日/地图卡仍用 block 自身撑高） */
.dro-dash-kpi__mid>.dro-dash-kpi__hero-formula--block {
  min-height: 2.55rem;
  align-self: end;
}

.dro-dash-kpi__hero-formula {
  display: inline;
  margin: 0;
  font-size: clamp(13px, 1.5vw, 15px);
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: 0.02em;
  color: #475569;
  max-width: none;
  flex: 1 1 auto;
  min-width: 0;
}

.dro-dash-kpi__hero-formula-eq {
  color: #64748b;
  font-weight: 800;
}

.dro-dash-kpi__hero-formula-plus {
  color: #94a3b8;
  font-weight: 800;
}

.dro-dash-kpi__hero-formula-part {
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.dro-dash-kpi__hero-formula-part--delivery {
  color: #047857;
}

.dro-dash-kpi__hero-formula-part--retail {
  color: #1d4ed8;
}

.dro-dash-kpi__hero-formula-part--pickup {
  color: #dc2626;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.dro-dash-kpi__hero-formula-note {
  margin: 0.2rem 0 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  color: #94a3b8;
}
.dro-dash-kpi__hero--compact {
  margin-bottom: 0;
}

/** 今日顶卡：销售量 / 后厨出餐量（日总份数，与下方后厨计划面板同源） */
.dro-dash-kpi__hero--dual {
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.1rem 0.35rem;
  line-height: 1;
}

/** 与下方「计算规则 =」同源字号/字色 */
.dro-dash-kpi__hero-unit {
  font-size: clamp(13px, 1.5vw, 15px);
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

.dro-dash-kpi__hero-slash {
  font-size: clamp(2.35rem, 5.8vw, 2.85rem);
  font-weight: 900;
  color: #cbd5e1;
  line-height: 1;
  flex-shrink: 0;
}

.dro-dash-kpi__hero-kitchen-missing {
  font-weight: 800;
  color: #94a3b8;
}

.dro-dash-kpi__hero--dual .dro-dash-kpi__hero-num {
  flex-shrink: 0;
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
  font-size: clamp(2.35rem, 5.8vw, 2.85rem);
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

/** 地图会员库：「位总会员」与今日/明日「总销售量」公式同行对齐 */
.dro-dash-kpi__hero-suffix--below {
  margin-left: 0;
  font-size: clamp(13px, 1.5vw, 15px);
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.02em;
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
  padding-top: 0.75rem;
  flex-shrink: 0;
  margin-top: auto;
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
  padding: 0.625rem 0.875rem;
  border-radius: 10px;
  min-width: 0;
  font-size: 11.5px;
}

.dro-dash-chip {
  border-radius: 10px;
  padding: 0.625rem 0.875rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  border: 1px solid transparent;
  background: #f8fafc;
  font-size: 11.5px;
}

.dro-dash-chip__k {
  font-size: 11.5px;
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

/** 今日单次零售：与「明日预测」蓝系 pill 对齐，便于与日区绿色区分 */
.dro-dash-chip--blue {
  background: rgba(239, 246, 255, 0.92);
  border-color: rgba(191, 219, 254, 0.75);
  color: #1d4ed8;
}

.dro-dash-chip--blue .dro-dash-chip__v {
  color: #2563eb;
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

.dro-dash-kpi__rate {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 800;
  color: #059669;
  background: #ecfdf5;
  padding: 0.25rem 0.55rem;
  border-radius: 0.375rem;
}

.dro-dash-plan-box {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 0.85rem;
  padding: 0.55rem 0.65rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
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

.dro-dash-plan-row--renewal {
  margin-top: 0.1rem;
  padding-top: 0.4rem;
  border-top: 2px solid #cbd5e1;
}

.dro-dash-plan-row__v--renewal {
  color: #7c3aed;
  font-weight: 900;
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

.dro-dash-dot--purple {
  background: #7c3aed;
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
 * 与备餐卡黄框「配送餐…自提…」行一致：14px / 700 / #475569；数字强调 #047857（同 dro-stat-card-prep-split-num）
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

/* 片区覆盖排行：全宽横向卡片（对齐设计稿图2） */
.dro-rank-section {
  margin-top: 0;
}

.dro-rank-card {
  background: #fff;
  border-radius: 2.5rem;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  padding: 1.75rem 1.75rem 1.5rem;
  display: flex;
  flex-direction: column;
}

.dro-rank-card--horizontal {
  min-height: 0;
}

.dro-rank-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.dro-rank-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 900;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.dro-rank-trend-ico {
  color: #10b981;
  flex-shrink: 0;
}

.dro-rank-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

@media (min-width: 768px) {
  .dro-rank-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (min-width: 1120px) {
  .dro-rank-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.dro-rank-tile {
  background: #fafbfc;
  border: 1px solid #f1f5f9;
  border-radius: 1.25rem;
  padding: 1.15rem 1.25rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  min-width: 0;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.dro-rank-tile:hover {
  border-color: #e2e8f0;
  box-shadow: 0 4px 14px -6px rgba(15, 23, 42, 0.12);
}

.dro-rank-tile__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
}

.dro-rank-name {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
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

.dro-rank-pct {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 900;
  color: #059669;
  font-variant-numeric: tabular-nums;
  font-family: var(--okfood-font-number);
}

.dro-rank-bar {
  height: 6px;
  background: #eef2f7;
  border-radius: 999px;
  overflow: hidden;
  margin-top: 0.35rem;
}

.dro-rank-bar-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.45s ease;
}
</style>
