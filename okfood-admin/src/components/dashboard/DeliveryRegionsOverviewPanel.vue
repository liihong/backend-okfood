<script setup>
import { computed, onMounted, onScopeDispose, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { apiJson, adminAccessToken, dishImageDisplayUrl, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useAnimatedInteger } from '../../composables/useAnimatedInteger.js'
import DashboardPickupKitchenPanel from './DashboardPickupKitchenPanel.vue'
import DayStockAdjustmentModal from './DayStockAdjustmentModal.vue'
import { useDayStockAdjustments } from '../../composables/useDayStockAdjustments.js'

/** 电脑宽屏：数字滚动、短文案、芯片竖排。菜品图各端都显示 */
const PC_MEAL_SHELF_MQ = '(min-width: 1200px)'
const isPcMealShelf = ref(
  typeof window !== 'undefined' && window.matchMedia(PC_MEAL_SHELF_MQ).matches,
)

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

/** 暂停配送：与档案库「已暂停」筛选同源（dashboard-summary.paused_delivery_count） */
const pausedDeliveryCount = computed(
  () => Number(summaryMeta.value?.paused_delivery_count) || 0,
)

/** 同比上周兜底：后厨出餐差值（dashboard-summary 旧字段，caption 优先） */
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
 * 去掉后厨出餐周同比 caption 前导「较上周」（左侧条已写同比上周，避免重复）
 * @param {unknown} raw
 * @returns {string}
 */
function stripMealsWowCaptionLeadingPhrase(raw) {
  const t = raw == null ? '' : String(raw).trim()
  if (!t) return ''
  return t.replace(/^较上周[\s\u3000]*/, '').replace(/份$/u, '').trim()
}

/** 后厨出餐总数同比上周说明（dashboard-summary）；展示在同比条右侧 */
const todayMealsWeekOverWeekCaption = computed(() => {
  const raw = summaryMeta.value?.today_meals_week_over_week_caption
  return stripMealsWowCaptionLeadingPhrase(raw)
})
/** 明日后厨出餐总数同比上周说明；展示在同比条右侧 */
const tomorrowMealsWeekOverWeekCaption = computed(() => {
  const raw = summaryMeta.value?.tomorrow_meals_week_over_week_caption
  return stripMealsWowCaptionLeadingPhrase(raw)
})

/** 同比文案：正为增加 x 份，负为减少 x 份，零为持平 */
function formatYoyWeekHeadsText(delta) {
  if (delta == null) return '—'
  if (delta === 0) return '与上周同期持平'
  if (delta > 0) return `增加${delta}份`
  return `减少${Math.abs(delta)}份`
}

/** 同比展示：+x份 / -x份 / 0份（用于边框区块数字） */
function formatYoyWeekHeadsSigned(delta) {
  if (delta == null) return '—'
  if (delta === 0) return '0份'
  if (delta > 0) return `+${delta}份`
  return `${delta}份`
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

/** 后厨日总份数保存后：等待 dashboard-summary 全量刷新，禁止局部 patch 导致剩余与产出不同步 */
async function onMenuDayStockSaved() {
  await fetchDashboardSummary()
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
    void loadWeeklyMenuDishes()
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
/** 午餐顶卡「单次可售剩余」← today_lunch_remaining（与小程序 single_stock_remaining 同源，仅服务端返回值） */
const todayLunchRemainingDisplay = computed(() => {
  const v = summaryMeta.value?.today_lunch_remaining
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? Math.max(0, Math.trunc(n)) : null
})
/** 晚餐顶卡「后厨产出量」← today_dinner_menu_day_total_stock（meal_period=dinner，与午餐 today_menu_day_total_stock 独立） */
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
const todayDinnerPickup = computed(() => {
  const b = prepMetricsBreakdown(todayDinnerPrepMetrics.value)
  return b != null ? b.pickup : null
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
  if (todayDinnerDelivery.value == null || todayDinnerPickup.value == null) return null
  return (
    Math.trunc(Number(todayDinnerDelivery.value)) +
    Math.trunc(Number(todayDinnerPickup.value)) +
    todayDinnerRetail.value
  )
})

const stockModalRemaining = ref(null)

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
  stockModalRemaining.value = todayLunchRemainingDisplay.value
  openStockAdjustModal({
    businessDate: businessAnchorIsoNormalized.value || summaryAnchorDate.value,
    mealPeriod: 'lunch',
  })
}

function openDinnerStockAdjust() {
  stockModalRemaining.value = todayDinnerRemaining.value
  openStockAdjustModal({
    businessDate: businessAnchorIsoNormalized.value || summaryAnchorDate.value,
    mealPeriod: 'dinner',
  })
}

/** 明日单次零售：锚定日次日已支付单次零售份数（dashboard-summary.tomorrow_single_retail_total_quantity） */
const tomorrowSingleRetailTotalCount = computed(
  () => Number(summaryMeta.value?.tomorrow_single_retail_total_quantity) || 0,
)

/** 午餐顶卡「后厨产出量」← today_menu_day_total_stock（meal_period=lunch；改晚餐总数不得影响本字段） */
const menuDayTotalStock = computed(() => {
  const v = summaryMeta.value?.today_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

/** 锚定日次日午餐「日总份数」（meal_period=lunch） */
const menuDayTotalStockTomorrow = computed(() => {
  const v = summaryMeta.value?.tomorrow_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

/** 锚定日后天午餐「日总份数」（meal_period=lunch） */
const menuDayTotalStockDayAfterTomorrow = computed(() => {
  const v = summaryMeta.value?.day_after_tomorrow_menu_day_total_stock
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : null
})

const menuDayTotalStockDinner = computed(() => {
  // 与 menuDayTotalStock（午餐）同源接口、分字段；后厨面板晚餐列专用
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

const tomorrowDinnerPrepMetrics = computed(() => {
  const m = summaryMeta.value?.tomorrow_dinner_prep_metrics
  return m && typeof m === 'object' ? m : null
})
const tomorrowDinnerDelivery = computed(() => {
  const b = prepMetricsBreakdown(tomorrowDinnerPrepMetrics.value)
  return b != null ? b.delivery : null
})
const tomorrowDinnerPickup = computed(() => {
  const b = prepMetricsBreakdown(tomorrowDinnerPrepMetrics.value)
  return b != null ? b.pickup : null
})
const tomorrowDinnerRetail = computed(
  () => Number(summaryMeta.value?.tomorrow_dinner_single_retail_total_quantity) || 0,
)
const tomorrowDinnerSoldTotal = computed(() => {
  if (tomorrowDinnerDelivery.value == null || tomorrowDinnerPickup.value == null) return null
  return (
    Math.trunc(Number(tomorrowDinnerDelivery.value)) +
    Math.trunc(Number(tomorrowDinnerPickup.value)) +
    tomorrowDinnerRetail.value
  )
})
const tomorrowDinnerSellableQuantity = computed(() => {
  const stock = menuDayTotalStockTomorrowDinner.value
  if (stock == null) return null
  if (tomorrowDinnerDelivery.value == null || tomorrowDinnerPickup.value == null) return null
  return Math.max(
    0,
    stock -
      Math.trunc(Number(tomorrowDinnerDelivery.value)) -
      Math.trunc(Number(tomorrowDinnerPickup.value)) -
      tomorrowDinnerRetail.value,
  )
})
/** 明日晚餐预测主值：优先次日晚餐日总份数，否则回退为预测已售 */
const tomorrowDinnerDistributionMainTotal = computed(() => {
  if (menuDayTotalStockTomorrowDinner.value != null) return menuDayTotalStockTomorrowDinner.value
  return tomorrowDinnerSoldTotal.value ?? 0
})

/** 概览数字滚动展示（加载 / 刷新 / 换日后过渡到新值） */
const todayLeaveAnimated = useAnimatedInteger(() => summarySlice.value.todayLeave, { duration: 620 })
const tomorrowLeaveAnimated = useAnimatedInteger(() => summarySlice.value.tomorrowLeave, { duration: 620 })
const expireMealPortionsAnimated = useAnimatedInteger(() => expireMealPortions.value, { duration: 620 })
const tomorrowFirstMealNewAnimated = useAnimatedInteger(() => tomorrowFirstMealNewCount.value, {
  duration: 620,
})
const pausedDeliveryAnimated = useAnimatedInteger(() => pausedDeliveryCount.value, {
  duration: 620,
})

/** 电脑端数字滚动；手机仍读原始值 */
const menuDayTotalStockAnimated = useAnimatedInteger(() => menuDayTotalStock.value)
const dinnerMenuDayTotalStockAnimated = useAnimatedInteger(() => dinnerMenuDayTotalStock.value)
const tomorrowDistributionMainTotalAnimated = useAnimatedInteger(() => tomorrowDistributionMainTotal.value)
const tomorrowDinnerDistributionMainTotalAnimated = useAnimatedInteger(
  () => tomorrowDinnerDistributionMainTotal.value,
)
const todaySoldTotalAnimated = useAnimatedInteger(() => todaySoldTotal.value)
const todayDinnerSoldTotalAnimated = useAnimatedInteger(() => todayDinnerSoldTotal.value)
const cardTomorrowPrepTotalAnimated = useAnimatedInteger(() => cardTomorrowPrepTotal.value)
const tomorrowDinnerSoldTotalAnimated = useAnimatedInteger(() => tomorrowDinnerSoldTotal.value)
const todayMealsDeliveryAnimated = useAnimatedInteger(() => todayMealsDelivery.value)
const todayMealsPickupAnimated = useAnimatedInteger(() => todayMealsPickup.value)
const todaySingleRetailAnimated = useAnimatedInteger(() => todaySingleRetailTotalCount.value)
const todayLunchWasteAnimated = useAnimatedInteger(() => todayLunchWasteTotal.value)
const todayLunchRemainingAnimated = useAnimatedInteger(() => todayLunchRemainingDisplay.value)
const todayDinnerDeliveryAnimated = useAnimatedInteger(() => todayDinnerDelivery.value)
const todayDinnerPickupAnimated = useAnimatedInteger(() => todayDinnerPickup.value)
const todayDinnerRetailAnimated = useAnimatedInteger(() => todayDinnerRetail.value)
const todayDinnerWasteAnimated = useAnimatedInteger(() => todayDinnerWasteTotal.value)
const todayDinnerRemainingAnimated = useAnimatedInteger(() => todayDinnerRemaining.value)
const tomorrowPrepDeliveryAnimated = useAnimatedInteger(() => tomorrowPrepDelivery.value)
const tomorrowPrepPickupAnimated = useAnimatedInteger(() => tomorrowPrepPickup.value)
const tomorrowSingleRetailAnimated = useAnimatedInteger(() => tomorrowSingleRetailTotalCount.value)
const tomorrowSellableAnimated = useAnimatedInteger(() => tomorrowSellableQuantity.value)
const tomorrowDinnerDeliveryAnimated = useAnimatedInteger(() => tomorrowDinnerDelivery.value)
const tomorrowDinnerPickupAnimated = useAnimatedInteger(() => tomorrowDinnerPickup.value)
const tomorrowDinnerRetailAnimated = useAnimatedInteger(() => tomorrowDinnerRetail.value)
const tomorrowDinnerSellableAnimated = useAnimatedInteger(() => tomorrowDinnerSellableQuantity.value)
const todayYoyDeltaAnimated = useAnimatedInteger(() => todayPrepHeadsYoyDelta.value)
const tomorrowYoyDeltaAnimated = useAnimatedInteger(() => tomorrowPrepHeadsYoyDelta.value)

/**
 * 本周菜单槽位上的菜名和图片。
 * 键：`YYYY-MM-DD|lunch` / `YYYY-MM-DD|dinner`。
 * 营业概览新字段还没从线上接口返回时，用已有的周菜单接口。
 */
const weeklyDishMap = ref(/** @type {Record<string, { name: string, image: string }>} */ ({}))

/** @param {string} iso */
function mondayOfIso(iso) {
  const raw = String(iso || '').trim().slice(0, 10)
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw)
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
  const day = dt.getUTCDay()
  const delta = day === 0 ? -6 : 1 - day
  return shiftIsoYmd(raw, delta)
}

/**
 * @param {unknown} payload
 * @param {'lunch'|'dinner'} period
 * @param {Record<string, { name: string, image: string, dishId: number | null }>} into
 */
function collectWeekSlotDishes(payload, period, into) {
  const preview = payload && typeof payload === 'object' ? payload : null
  if (!preview) return
  /** @type {Array<[unknown, unknown]>} */
  const groups = []
  if ('week_start' in preview && 'slots' in preview) {
    groups.push([preview.week_start, preview.slots])
  }
  if ('this_week_start' in preview) groups.push([preview.this_week_start, preview.this_week])
  if ('next_week_start' in preview) groups.push([preview.next_week_start, preview.next_week])
  for (const [start, slots] of groups) {
    const startIso = String(start || '').slice(0, 10)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(startIso) || !Array.isArray(slots)) continue
    for (const slotRow of slots) {
      const slot = Number(slotRow?.slot)
      if (!Number.isFinite(slot)) continue
      const iso = shiftIsoYmd(startIso, slot - 1)
      if (!iso) continue
      const dishIdRaw = slotRow?.dish_id
      const dishId = dishIdRaw == null || dishIdRaw === '' ? null : Number(dishIdRaw)
      into[`${iso}|${period}`] = {
        name: String(slotRow?.name || '').trim(),
        image: dishImageDisplayUrl(String(slotRow?.image_url || '')),
        dishId: Number.isFinite(dishId) ? dishId : null,
      }
    }
  }
}

/** 按锚定日拉取午餐、晚餐周槽位，缺图时再读菜品详情 */
async function loadWeeklyMenuDishes() {
  const weeks = [
    ...new Set(
      [mondayOfIso(businessAnchorIsoNormalized.value), mondayOfIso(businessAnchorTomorrowIso.value)].filter(
        Boolean,
      ),
    ),
  ]
  const periods = /** @type {const} */ (['lunch', 'dinner'])
  const weekList = weeks.length ? weeks : ['']
  const rows = await Promise.all(
    weekList.flatMap((week) =>
      periods.map((period) => {
        const q = week
          ? `week_start=${encodeURIComponent(week)}&meal_period=${period}`
          : `meal_period=${period}`
        return apiJson(`/api/admin/menu/weekly-slots?${q}`, {}, { auth: true })
          .then((data) => ({ period, data }))
          .catch(() => ({ period, data: null }))
      }),
    ),
  )
  /** @type {Record<string, { name: string, image: string, dishId: number | null }>} */
  const map = {}
  for (const row of rows) {
    if (row.data) collectWeekSlotDishes(row.data, row.period, map)
  }
  const missingIds = [
    ...new Set(Object.values(map).filter((item) => item.dishId && !item.image).map((item) => item.dishId)),
  ]
  if (missingIds.length) {
    const details = await Promise.all(
      missingIds.map((id) => apiJson(`/api/admin/dish/${id}`, {}, { auth: true }).catch(() => null)),
    )
    /** @type {Record<number, string>} */
    const imageById = {}
    for (const detail of details) {
      if (!detail || detail.id == null) continue
      imageById[Number(detail.id)] = dishImageDisplayUrl(String(detail.image_url || ''))
    }
    for (const item of Object.values(map)) {
      if (!item.image && item.dishId && imageById[item.dishId]) item.image = imageById[item.dishId]
    }
  }
  /** @type {Record<string, { name: string, image: string }>} */
  const brief = {}
  for (const [key, item] of Object.entries(map)) {
    brief[key] = { name: item.name, image: item.image }
  }
  weeklyDishMap.value = brief
}

/**
 * 卡片菜品：优先本周菜单槽位，概览接口里的菜名字段作为补充。
 * @param {string} nameKey
 * @param {string} imageKey
 * @param {() => string} isoGetter
 * @param {'lunch'|'dinner'} period
 */
function menuDishBrief(nameKey, imageKey, isoGetter, period) {
  return computed(() => {
    const slot = weeklyDishMap.value[`${isoGetter()}|${period}`]
    const meta = summaryMeta.value
    const summaryName = String(meta?.[nameKey] ?? '').trim()
    const summaryImage = dishImageDisplayUrl(String(meta?.[imageKey] ?? ''))
    return {
      name: (slot?.name || summaryName || '').trim(),
      image: slot?.image || summaryImage || '',
    }
  })
}
const todayLunchDish = menuDishBrief(
  'today_lunch_dish_name',
  'today_lunch_dish_image_url',
  () => businessAnchorIsoNormalized.value,
  'lunch',
)
const todayDinnerDish = menuDishBrief(
  'today_dinner_dish_name',
  'today_dinner_dish_image_url',
  () => businessAnchorIsoNormalized.value,
  'dinner',
)
const tomorrowLunchDish = menuDishBrief(
  'tomorrow_lunch_dish_name',
  'tomorrow_lunch_dish_image_url',
  () => businessAnchorTomorrowIso.value,
  'lunch',
)
const tomorrowDinnerDish = menuDishBrief(
  'tomorrow_dinner_dish_name',
  'tomorrow_dinner_dish_image_url',
  () => businessAnchorTomorrowIso.value,
  'dinner',
)

/** 拆解数字：空值保持「—」，电脑端用滚动值 */
function shelfCountText(value, rolling, pc) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const n = pc ? rolling : value
  return `${Math.trunc(Number(n))}`
}

function shelfSoldText(total, rolling, pc) {
  if (total == null || Number.isNaN(Number(total))) return '—'
  const n = pc ? rolling : total
  return `${Math.trunc(Number(n))}份`
}

function yoyShelfText(caption, delta, rolling, pc) {
  if (caption) return caption
  if (delta == null) return '—'
  return formatYoyWeekHeadsSigned(pc ? rolling : delta)
}

const showDashboardOverview = computed(
  () => Boolean(summaryMeta.value) || (!dashboardStatsLoading.value && dashboardStats.value.length > 0),
)

onMounted(() => {
  const mq = window.matchMedia(PC_MEAL_SHELF_MQ)
  const syncPcShelf = () => {
    isPcMealShelf.value = mq.matches
  }
  syncPcShelf()
  mq.addEventListener('change', syncPcShelf)
  onScopeDispose(() => mq.removeEventListener('change', syncPcShelf))
  void fetchDashboardSummary()
})
</script>

<template>
  <section class="dro-page dro-page--modern ios-glass-dashboard">

    <p v-if="summaryMeta?.from_snapshot" class="dro-snapshot-hint">
      已显示归档数据（与智能配送大表口径对齐的首读留存）。
      <template v-if="summaryMeta.snapshot_recorded_at">
        归档时间 {{ summaryMeta.snapshot_recorded_at }}。
      </template>
    </p>

    <p v-if="dashboardStatsLoading && !summaryMeta" class="dro-loading">正在加载营业概览…</p>
    <p v-else-if="!dashboardStats.length && !summaryMeta" class="dro-loading">暂无营业概览数据。</p>

    <!-- 今日营业概览：今日（午|晚）+ 明日（午|晚）分栏 + 后厨/自提 -->
    <div v-if="showDashboardOverview" class="dro-dash-layout">
      <div class="dro-dash-meal-shelf" :class="{ 'dro-dash-meal-shelf--pc': isPcMealShelf }">
        <!-- 今日：午餐左、晚餐右 -->
        <section class="dro-dash-day-cluster dro-dash-day-cluster--today" aria-label="今日午晚餐">
          <header class="dro-dash-day-cluster__head">
            <span class="dro-dash-day-cluster__title">今日</span>
            <span class="dro-dash-day-cluster__meta">{{ businessAnchorMdDisplay || '—' }}</span>
            <span v-if="businessAnchorWeekdayDisplay" class="dro-dash-day-cluster__weekday">{{
              businessAnchorWeekdayDisplay
            }}</span>
            <div class="dro-dash-day-nav dro-dash-pc-day-nav" aria-label="切换营业日">
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
          </header>
          <div class="dro-dash-day-cluster__grid">
      <article class="dro-dash-kpi" :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }">
        <div class="dro-pc-dish">
          <div class="dro-pc-dish__meta">
            <span class="dro-pc-dish__menu">本周菜单：午餐</span>
            <button type="button" class="dro-dash-adjust-btn" title="报损耗" @click="openLunchStockAdjust">
              报损耗
            </button>
          </div>
          <div class="dro-pc-dish__row">
            <div class="dro-pc-photo" :class="{ 'dro-pc-photo--empty': !todayLunchDish.image }">
              <el-image
                v-if="todayLunchDish.image"
                class="dro-pc-photo__img"
                :src="todayLunchDish.image"
                :preview-src-list="[todayLunchDish.image]"
                :alt="todayLunchDish.name || '午餐'"
                :title="todayLunchDish.name ? `查看大图：${todayLunchDish.name}` : '查看大图'"
                fit="cover"
                preview-teleported
                hide-on-click-modal
                :z-index="4000"
              />
              <span v-else>未排菜</span>
            </div>
            <div class="dro-pc-dish__copy">
              <div class="dro-pc-dish__name">{{ todayLunchDish.name || '未排菜' }}</div>
              <div class="dro-dash-kpi__hero-metric">
                <span class="dro-dash-kpi__hero-metric-kicker">后厨产出量：</span>
                <span class="dro-dash-kpi__hero-metric-num-wrap">
                  <span class="dro-dash-kpi__hero-metric-num">{{
                    menuDayTotalStock != null
                      ? isPcMealShelf
                        ? menuDayTotalStockAnimated
                        : menuDayTotalStock
                      : '—'
                  }}</span>
                  <small class="dro-dash-kpi__hero-metric-unit">份</small>
                </span>
              </div>
            </div>
          </div>
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
                  已售出 {{ shelfSoldText(todaySoldTotal, todaySoldTotalAnimated, isPcMealShelf) }}
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
                      todayLunchRemainingDisplay != null && todayLunchRemainingDisplay <= 0,
                  }"
                  :style="{
                    width: distributionStackWidth(todayLunchRemainingDisplay, menuDayTotalStock),
                  }"
                />
              </div>
              <div class="dro-dash-branch-pill-grid dro-dash-branch-pill-grid--5">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(todayMealsDelivery, todayMealsDeliveryAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(todayMealsPickup, todayMealsPickupAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(todaySingleRetailTotalCount, todaySingleRetailAnimated, isPcMealShelf) }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--waste" aria-hidden="true" />损耗</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(todayLunchWasteTotal, todayLunchWasteAnimated, isPcMealShelf) }}</span>
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
                      shelfCountText(todayLunchRemainingDisplay, todayLunchRemainingAnimated, isPcMealShelf)
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
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '请假' : '今日请假' }}</span>
            <span class="dro-dash-chip__v">{{ todayLeaveAnimated }} <small></small></span>
          </div>
          <div class="dro-dash-chip dro-dash-chip--rose">
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '过期' : '当日过期' }}</span>
            <span class="dro-dash-chip__v">{{ expireMealPortionsAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--slate"
            :class="{ 'dro-dash-chip--faded': pausedDeliveryCount === 0 }"
            role="status"
            :aria-label="`暂停配送 ${pausedDeliveryCount} `"
            title="与档案库「已暂停」筛选口径一致"
          >
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '暂停' : '暂停配送' }}</span>
            <span class="dro-dash-chip__v">{{ pausedDeliveryAnimated }} <small></small></span>
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
              <span class="dro-dash-yoy-chip__prefix">{{ isPcMealShelf ? '同比' : '同比上周' }}</span>
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
                yoyShelfText(todayMealsWeekOverWeekCaption, todayPrepHeadsYoyDelta, todayYoyDeltaAnimated, isPcMealShelf)
              }}</span
            >
          </div>
        </div>
      </article>
      <article class="dro-dash-kpi dro-dash-kpi--dinner" :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }">
        <div class="dro-pc-dish">
          <div class="dro-pc-dish__meta">
            <span class="dro-pc-dish__menu">本周菜单：晚餐</span>
            <button type="button" class="dro-dash-adjust-btn" title="报损耗" @click="openDinnerStockAdjust">
              报损耗
            </button>
          </div>
          <div class="dro-pc-dish__row">
            <div class="dro-pc-photo" :class="{ 'dro-pc-photo--empty': !todayDinnerDish.image }">
              <el-image
                v-if="todayDinnerDish.image"
                class="dro-pc-photo__img"
                :src="todayDinnerDish.image"
                :preview-src-list="[todayDinnerDish.image]"
                :alt="todayDinnerDish.name || '晚餐'"
                :title="todayDinnerDish.name ? `查看大图：${todayDinnerDish.name}` : '查看大图'"
                fit="cover"
                preview-teleported
                hide-on-click-modal
                :z-index="4000"
              />
              <span v-else>未排菜</span>
            </div>
            <div class="dro-pc-dish__copy">
              <div class="dro-pc-dish__name">{{ todayDinnerDish.name || '未排菜' }}</div>
              <div class="dro-dash-kpi__hero-metric">
                <span class="dro-dash-kpi__hero-metric-kicker">后厨产出量：</span>
                <span class="dro-dash-kpi__hero-metric-num-wrap">
                  <span class="dro-dash-kpi__hero-metric-num">{{
                    dinnerMenuDayTotalStock != null
                      ? isPcMealShelf
                        ? dinnerMenuDayTotalStockAnimated
                        : dinnerMenuDayTotalStock
                      : '—'
                  }}</span>
                  <small class="dro-dash-kpi__hero-metric-unit">份</small>
                </span>
              </div>
            </div>
          </div>
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--distribution-chain">
          <div class="dro-dash-kpi__metric-top">
            <div
              class="dro-dash-distribution-chain"
              role="note"
              :aria-label="
                dinnerMenuDayTotalStock != null
                  ? `${dinnerMenuDayTotalStock}份当日晚餐出餐量等于配送、自提、单次零售与可卖数量之和`
                  : '当日晚餐出餐量未配置'
              "
            >
              <div class="dro-dash-chain-node-header">
                <span class="dro-dash-chain-node-label">配额去向拆解线</span>
                <span class="dro-dash-chain-node dro-dash-chain-node--main">
                  已售出 {{ shelfSoldText(todayDinnerSoldTotal, todayDinnerSoldTotalAnimated, isPcMealShelf) }}
                </span>
              </div>
              <div class="dro-dash-stacked-bar" aria-hidden="true">
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--deliver"
                  :style="{
                    width: distributionStackWidth(todayDinnerDelivery, dinnerMenuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--pickup"
                  :style="{
                    width: distributionStackWidth(todayDinnerPickup, dinnerMenuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--retail"
                  :style="{
                    width: distributionStackWidth(todayDinnerRetail, dinnerMenuDayTotalStock),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--sellable"
                  :class="{
                    'dro-dash-stacked-bar__seg--sellable-empty':
                      todayDinnerRemaining != null && todayDinnerRemaining <= 0,
                  }"
                  :style="{
                    width: distributionStackWidth(todayDinnerRemaining, dinnerMenuDayTotalStock),
                  }"
                />
              </div>
              <div class="dro-dash-branch-pill-grid dro-dash-branch-pill-grid--5">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(todayDinnerDelivery, todayDinnerDeliveryAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(todayDinnerPickup, todayDinnerPickupAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(todayDinnerRetail, todayDinnerRetailAnimated, isPcMealShelf) }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--waste" aria-hidden="true" />损耗</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(todayDinnerWasteTotal, todayDinnerWasteAnimated, isPcMealShelf) }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--sellable" aria-hidden="true" />剩余</span
                  >
                  <span
                    class="dro-dash-branch-pill__val dro-dash-branch-pill__val--sellable"
                    :class="{
                      'dro-dash-branch-pill__val--sellable-muted':
                        todayDinnerRemaining != null && todayDinnerRemaining <= 0,
                    }"
                    >{{
                      shelfCountText(todayDinnerRemaining, todayDinnerRemainingAnimated, isPcMealShelf)
                    }}</span
                  >
                </div>
              </div>
            </div>
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
      </article>
          </div>
        </section>

        <!-- 明日：午餐左、晚餐右 -->
        <section class="dro-dash-day-cluster dro-dash-day-cluster--tomorrow" aria-label="明日午晚餐预测">
          <header class="dro-dash-day-cluster__head">
            <span class="dro-dash-day-cluster__title">明日</span>
            <span class="dro-dash-day-cluster__meta">{{ businessAnchorTomorrowMdDisplay || '—' }}</span>
            <span v-if="businessAnchorTomorrowWeekdayDisplay" class="dro-dash-day-cluster__weekday">{{
              businessAnchorTomorrowWeekdayDisplay
            }}</span>
          </header>
          <div class="dro-dash-day-cluster__grid">
      <article
        class="dro-dash-kpi dro-dash-kpi--tomorrow"
        :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }"
      >
        <div class="dro-pc-dish">
          <div class="dro-pc-dish__meta">
            <span class="dro-pc-dish__menu">本周菜单：午餐</span>
          </div>
          <div class="dro-pc-dish__row">
            <div class="dro-pc-photo" :class="{ 'dro-pc-photo--empty': !tomorrowLunchDish.image }">
              <el-image
                v-if="tomorrowLunchDish.image"
                class="dro-pc-photo__img"
                :src="tomorrowLunchDish.image"
                :preview-src-list="[tomorrowLunchDish.image]"
                :alt="tomorrowLunchDish.name || '午餐'"
                :title="tomorrowLunchDish.name ? `查看大图：${tomorrowLunchDish.name}` : '查看大图'"
                fit="cover"
                preview-teleported
                hide-on-click-modal
                :z-index="4000"
              />
              <span v-else>未排菜</span>
            </div>
            <div class="dro-pc-dish__copy">
              <div class="dro-pc-dish__name">{{ tomorrowLunchDish.name || '未排菜' }}</div>
              <div class="dro-dash-kpi__hero-metric">
                <span class="dro-dash-kpi__hero-metric-kicker">后厨产出量：</span>
                <span class="dro-dash-kpi__hero-metric-num-wrap">
                  <span class="dro-dash-kpi__hero-metric-num">{{
                    isPcMealShelf ? tomorrowDistributionMainTotalAnimated : tomorrowDistributionMainTotal
                  }}</span>
                  <small class="dro-dash-kpi__hero-metric-unit">份</small>
                </span>
              </div>
            </div>
          </div>
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
                  已售出 {{ shelfSoldText(cardTomorrowPrepTotal, cardTomorrowPrepTotalAnimated, isPcMealShelf) }}
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
              <div class="dro-dash-branch-pill-grid dro-dash-branch-pill-grid--5">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(tomorrowPrepDelivery, tomorrowPrepDeliveryAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(tomorrowPrepPickup, tomorrowPrepPickupAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(tomorrowSingleRetailTotalCount, tomorrowSingleRetailAnimated, isPcMealShelf) }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--waste" aria-hidden="true" />损耗</span
                  >
                  <span class="dro-dash-branch-pill__val">0</span>
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
                      shelfCountText(tomorrowSellableQuantity, tomorrowSellableAnimated, isPcMealShelf)
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
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '请假' : '明日请假' }}</span>
            <span class="dro-dash-chip__v">{{ tomorrowLeaveAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--rose"
            :class="{ 'dro-dash-chip--faded': tomorrowFirstMealNewCount === 0 }"
          >
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '新客' : '首餐新客' }}</span>
            <span class="dro-dash-chip__v">{{ tomorrowFirstMealNewAnimated }} <small></small></span>
          </div>
          <div
            class="dro-dash-chip dro-dash-chip--slate"
            :class="{ 'dro-dash-chip--faded': pausedDeliveryCount === 0 }"
            role="status"
            :aria-label="`暂停配送 ${pausedDeliveryCount} `"
            title="与档案库「已暂停」筛选口径一致"
          >
            <span class="dro-dash-chip__k">{{ isPcMealShelf ? '暂停' : '暂停配送' }}</span>
            <span class="dro-dash-chip__v">{{ pausedDeliveryAnimated }} <small></small></span>
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
              <span class="dro-dash-yoy-chip__prefix">{{ isPcMealShelf ? '同比' : '同比上周' }}</span>
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
                yoyShelfText(tomorrowMealsWeekOverWeekCaption, tomorrowPrepHeadsYoyDelta, tomorrowYoyDeltaAnimated, isPcMealShelf)
              }}</span
            >
          </div>
        </div>
      </article>

      <article
        class="dro-dash-kpi dro-dash-kpi--tomorrow dro-dash-kpi--dinner"
        :class="{ 'dro-dash-kpi--dim': !summaryIsLiveToday }"
      >
        <div class="dro-pc-dish">
          <div class="dro-pc-dish__meta">
            <span class="dro-pc-dish__menu">本周菜单：晚餐</span>
          </div>
          <div class="dro-pc-dish__row">
            <div class="dro-pc-photo" :class="{ 'dro-pc-photo--empty': !tomorrowDinnerDish.image }">
              <el-image
                v-if="tomorrowDinnerDish.image"
                class="dro-pc-photo__img"
                :src="tomorrowDinnerDish.image"
                :preview-src-list="[tomorrowDinnerDish.image]"
                :alt="tomorrowDinnerDish.name || '晚餐'"
                :title="tomorrowDinnerDish.name ? `查看大图：${tomorrowDinnerDish.name}` : '查看大图'"
                fit="cover"
                preview-teleported
                hide-on-click-modal
                :z-index="4000"
              />
              <span v-else>未排菜</span>
            </div>
            <div class="dro-pc-dish__copy">
              <div class="dro-pc-dish__name">{{ tomorrowDinnerDish.name || '未排菜' }}</div>
              <div class="dro-dash-kpi__hero-metric">
                <span class="dro-dash-kpi__hero-metric-kicker">后厨产出量：</span>
                <span class="dro-dash-kpi__hero-metric-num-wrap">
                  <span class="dro-dash-kpi__hero-metric-num">{{
                    isPcMealShelf
                      ? tomorrowDinnerDistributionMainTotalAnimated
                      : tomorrowDinnerDistributionMainTotal
                  }}</span>
                  <small class="dro-dash-kpi__hero-metric-unit">份</small>
                </span>
              </div>
            </div>
          </div>
        </div>
        <div class="dro-dash-kpi__mid dro-dash-kpi__mid--distribution-chain">
          <div class="dro-dash-kpi__metric-top">
            <div
              class="dro-dash-distribution-chain dro-dash-distribution-chain--tomorrow"
              role="note"
              :aria-label="`${tomorrowDinnerDistributionMainTotal}份明日晚餐预测等于同城配送、门店自提、单次零售与可卖数量之和`"
            >
              <div class="dro-dash-chain-node-header">
                <span class="dro-dash-chain-node-label">明日排产指标线</span>
                <span class="dro-dash-chain-node dro-dash-chain-node--main dro-dash-chain-node--main-blue">
                  已售出 {{ shelfSoldText(tomorrowDinnerSoldTotal, tomorrowDinnerSoldTotalAnimated, isPcMealShelf) }}
                </span>
              </div>
              <div class="dro-dash-stacked-bar" aria-hidden="true">
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--deliver"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowDinnerDelivery,
                      tomorrowDinnerDistributionMainTotal,
                    ),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--pickup"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowDinnerPickup,
                      tomorrowDinnerDistributionMainTotal,
                    ),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--retail"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowDinnerRetail,
                      tomorrowDinnerDistributionMainTotal,
                    ),
                  }"
                />
                <div
                  class="dro-dash-stacked-bar__seg dro-dash-stacked-bar__seg--sellable"
                  :class="{
                    'dro-dash-stacked-bar__seg--sellable-empty':
                      tomorrowDinnerSellableQuantity != null && tomorrowDinnerSellableQuantity <= 0,
                  }"
                  :style="{
                    width: distributionStackWidth(
                      tomorrowDinnerSellableQuantity,
                      tomorrowDinnerDistributionMainTotal,
                    ),
                  }"
                />
              </div>
              <div class="dro-dash-branch-pill-grid dro-dash-branch-pill-grid--5">
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--deliver" aria-hidden="true" />配送</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(tomorrowDinnerDelivery, tomorrowDinnerDeliveryAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--pickup" aria-hidden="true" />自提</span
                  >
                  <span class="dro-dash-branch-pill__val">{{
                    shelfCountText(tomorrowDinnerPickup, tomorrowDinnerPickupAnimated, isPcMealShelf)
                  }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--retail" aria-hidden="true" />零售</span
                  >
                  <span class="dro-dash-branch-pill__val">{{ shelfCountText(tomorrowDinnerRetail, tomorrowDinnerRetailAnimated, isPcMealShelf) }}</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--waste" aria-hidden="true" />损耗</span
                  >
                  <span class="dro-dash-branch-pill__val">0</span>
                </div>
                <div class="dro-dash-branch-pill">
                  <span class="dro-dash-branch-pill__lbl"
                    ><span class="dro-dash-branch-dot dro-dash-branch-dot--sellable" aria-hidden="true" />剩余</span
                  >
                  <span
                    class="dro-dash-branch-pill__val dro-dash-branch-pill__val--sellable dro-dash-branch-pill__val--sellable-blue"
                    :class="{
                      'dro-dash-branch-pill__val--sellable-muted':
                        tomorrowDinnerSellableQuantity != null && tomorrowDinnerSellableQuantity <= 0,
                    }"
                    >{{
                      shelfCountText(tomorrowDinnerSellableQuantity, tomorrowDinnerSellableAnimated, isPcMealShelf)
                    }}</span
                  >
                </div>
              </div>
            </div>
          </div>
          <div class="dro-dash-kpi__mid-spacer" aria-hidden="true" />
        </div>
        <div v-if="!isPcMealShelf" class="dro-dash-kpi__stat-row dro-dash-kpi__stat-row--chips-then-yoy">
          <div
            class="dro-dash-chip dro-dash-chip--blue"
            role="status"
            :aria-label="`单次零售 ${tomorrowDinnerRetail} `"
          >
            <span class="dro-dash-chip__k">单次零售</span>
            <span class="dro-dash-chip__v">{{ shelfCountText(tomorrowDinnerRetail, tomorrowDinnerRetailAnimated, isPcMealShelf) }} <small></small></span>
          </div>
        </div>
      </article>
          </div>
        </section>
      </div>

      <!-- 后厨计划管理 / 门店自提快速核销舱 -->
      <DashboardPickupKitchenPanel
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
    </div>
  </section>

  <DayStockAdjustmentModal
    :open="stockModalOpen"
    :meal-period="stockModalMealPeriod"
    :business-date="stockModalBusinessDate"
    :remaining="stockModalRemaining"
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
/* iOS 毛玻璃方向：仅影响本页容器与 KPI 材质，不改动接口与结构 */
.ios-glass-dashboard.dro-page--modern {
  /* 画布由 admin-layout / main-body 统一铺色；本页不再叠第二层实底，避免与毛玻璃卡「打架」 */
  background: transparent;
}

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
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(186, 230, 253, 0.85);
  border-radius: 14px;
  padding: 10px 12px;
  margin: 0 0 1rem;
  line-height: 1.45;
  backdrop-filter: saturate(1.15) blur(10px);
  -webkit-backdrop-filter: saturate(1.15) blur(10px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.85) inset, 0 8px 24px rgba(15, 23, 42, 0.04);
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

.dro-dash-layout {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-bottom: 0.75rem;
}

.dro-dash-layout :deep(.dpk-grid) {
  margin-bottom: 0;
}

/**
 * 营业概览：左「今日」、右「明日」分栏；每栏内午餐 | 晚餐 并排
 * 外层 .dro-dash-day-cluster 用边框/底色区分今日 vs 明日预测
 */
.dro-dash-meal-shelf {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  width: 100%;
  min-width: 0;
}

@media (min-width: 1200px) {
  .dro-dash-meal-shelf {
    flex-direction: row;
    align-items: stretch;
    gap: 0.55rem;
  }
}

.dro-dash-day-cluster {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.42rem;
  padding: 0.45rem 0.55rem 0.55rem;
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.65);
  background: rgba(255, 255, 255, 0.32);
  backdrop-filter: saturate(1.15) blur(12px);
  -webkit-backdrop-filter: saturate(1.15) blur(12px);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.42) inset;
}

/* 左栏「今日」：蓝系晕 + 浅底（与右侧主色区分） */
.dro-dash-day-cluster--today {
  border-color: color-mix(in srgb, #3b82f6 34%, rgba(255, 255, 255, 0.52));
  background: color-mix(in srgb, #3b82f6 9%, rgba(255, 255, 255, 0.34));
}

/* 右栏「明日」：主色晕 + 浅底（右侧更偏品牌暖色） */
.dro-dash-day-cluster--tomorrow {
  border-color: color-mix(in srgb, var(--el-color-primary) 30%, rgba(255, 255, 255, 0.55));
  background: color-mix(in srgb, var(--el-color-primary) 8%, rgba(255, 255, 255, 0.38));
}

.dro-dash-day-cluster__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
  padding: 0 0.15rem;
  flex-shrink: 0;
}

.dro-dash-day-cluster__title {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--el-text-color-secondary, #64748b);
}

.dro-dash-day-cluster__meta {
  font-size: 12px;
  font-weight: 700;
  color: var(--el-text-color-primary, #0f172a);
}

.dro-dash-day-cluster__weekday {
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-regular, #475569);
}

.dro-dash-day-cluster__grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.4rem;
  min-width: 0;
  align-items: stretch;
}

@media (min-width: 640px) {
  .dro-dash-day-cluster__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.4rem;
  }
}

/* 大屏：分栏内 KPI 再收紧，四卡同屏更易一眼扫完 */
@media (min-width: 1400px) {
  .dro-dash-meal-shelf .dro-dash-kpi {
    min-height: 0;
    padding: 0.65rem 0.7rem;
    border-radius: 14px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__head {
    min-height: 1.65rem;
    margin-bottom: 0.12rem;
    gap: 0.35rem;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__head-actions {
    gap: 4px;
  }

  .dro-dash-meal-shelf .dro-dash-pill {
    font-size: 9.5px;
    padding: 0.16rem 0.45rem;
    max-width: 100%;
    white-space: normal;
    line-height: 1.25;
  }

  .dro-dash-meal-shelf .dro-dash-day-nav-btn {
    padding: 2px 6px;
    font-size: 9.5px;
  }

  .dro-dash-meal-shelf .dro-dash-adjust-btn {
    padding: 2px 7px;
    font-size: 9px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__ico-badge {
    width: 26px;
    height: 26px;
    border-radius: 8px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__ico-badge--action :deep(svg) {
    width: 14px;
    height: 14px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__ico-badge--blue :deep(svg) {
    width: 14px;
    height: 14px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__hero-metric {
    margin: 0.1rem 0 0;
    gap: 0.08rem 0.2rem;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__hero-metric-num {
    font-size: clamp(1.52rem, 1.58vw, 1.82rem);
  }

  .dro-dash-meal-shelf .dro-dash-kpi__hero-metric-kicker {
    font-size: 11px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__hero-metric-unit {
    font-size: 11px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__mid--distribution-chain {
    margin-top: 0.35rem;
  }

  .dro-dash-meal-shelf .dro-dash-distribution-chain {
    gap: 0.45rem;
    padding: 0.45rem 0.5rem;
    border-radius: 10px;
  }

  .dro-dash-meal-shelf .dro-dash-chain-node-label {
    font-size: 10px;
    font-weight: 600;
  }

  .dro-dash-meal-shelf .dro-dash-chain-node {
    padding: 0.2rem 0.46rem;
    font-size: 10px;
    font-weight: 600;
  }

  .dro-dash-meal-shelf .dro-dash-stacked-bar {
    height: 7px;
  }

  .dro-dash-meal-shelf .dro-dash-branch-pill-grid--5 {
    gap: 0.28rem;
  }

  .dro-dash-meal-shelf .dro-dash-branch-pill {
    padding: 0.22rem 0.14rem;
    border-radius: 8px;
  }

  .dro-dash-meal-shelf .dro-dash-branch-pill__lbl {
    font-size: 8.5px;
    margin-bottom: 0.06rem;
  }

  .dro-dash-meal-shelf .dro-dash-branch-dot {
    width: 4px;
    height: 4px;
  }

  .dro-dash-meal-shelf .dro-dash-branch-pill__val {
    font-size: 11.5px;
  }

  .dro-dash-meal-shelf .dro-dash-kpi__stat-row--chips-then-yoy {
    gap: 0.35rem;
    padding-top: 0.28rem;
  }

  .dro-dash-meal-shelf .dro-dash-kpi--tomorrow:not(.dro-dash-kpi--dinner) .dro-dash-kpi__stat-row--chips-then-yoy {
    padding-top: 0.2rem;
  }

  .dro-dash-meal-shelf .dro-dash-chip {
    padding: 0.36rem 0.46rem;
    font-size: 10px;
    border-radius: 8px;
  }

  .dro-dash-meal-shelf .dro-dash-chip__k {
    font-size: 10px;
  }

  .dro-dash-meal-shelf .dro-dash-chip__v {
    font-size: 0.88rem;
  }

  .dro-dash-meal-shelf .dro-dash-yoy-chip {
    padding: 0.42rem 0.52rem;
    border-radius: 8px;
    gap: 0.35rem;
  }

  .dro-dash-meal-shelf .dro-dash-yoy-chip__val {
    font-size: 0.88rem;
  }

  .dro-dash-meal-shelf .dro-dash-yoy-chip__val--caption {
    font-size: 10px;
  }

  .dro-dash-meal-shelf .dro-dash-yoy-chip__prefix {
    font-size: 10px;
  }
}

.dro-dash-forecast-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dro-dash-forecast-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

/* ——— 配送区域总览：顶部 KPI 卡（iOS 毛玻璃：统一圆角描边 + 内高光，无额外彩色顶线） ——— */
.dro-dash-kpi {
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(255, 255, 255, 0.72);
  border-radius: 18px;
  padding: 1.15rem 1.25rem;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  min-height: 232px;
  height: 100%;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.55) inset,
    0 6px 22px rgba(25, 45, 55, 0.045),
    0 2px 8px color-mix(in srgb, var(--el-color-primary, #e8927c) 8%, transparent);
  backdrop-filter: saturate(1.25) blur(16px);
  -webkit-backdrop-filter: saturate(1.25) blur(16px);
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

/** 营业概览午/晚四张顶卡：在现有卡片的宽高内略放大字号，提升扫读清晰度 */
.dro-dash-meal-shelf .dro-dash-kpi {
  padding: 1.02rem 1.08rem;
  min-height: 228px;
}

.dro-dash-kpi--dinner:hover {
  border-color: rgba(124, 58, 237, 0.22);
}

.dro-dash-kpi:hover {
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.65) inset,
    0 10px 28px rgba(25, 45, 55, 0.055),
    0 3px 12px color-mix(in srgb, var(--el-color-primary, #e8927c) 12%, transparent);
}

.dro-dash-kpi--tomorrow:hover {
  border-color: rgba(59, 130, 246, 0.28);
}

.dro-dash-kpi--maplib:hover {
  border-color: rgba(139, 92, 246, 0.26);
}

.dro-dash-kpi--dim {
  opacity: 0.88;
}

/* 顶栏右侧：报损耗 + 刷新等成组，与标题行对齐、省出中间纵向空间 */
.dro-dash-kpi__head-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.dro-dash-adjust-btn {
  border: 1px solid rgba(203, 213, 225, 0.75);
  background: rgba(255, 255, 255, 0.45);
  color: #475569;
  border-radius: 999px;
  padding: 4px 11px;
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    color 0.2s ease,
    background 0.2s ease;
}

.dro-dash-adjust-btn:hover {
  border-color: color-mix(in srgb, var(--el-color-primary) 55%, #cbd5e1);
  color: var(--el-color-primary-dark-2);
  background: color-mix(in srgb, var(--el-color-primary) 8%, rgba(255, 255, 255, 0.5));
}

.dro-dash-kpi--dinner .dro-dash-adjust-btn:hover {
  border-color: #7c3aed;
  color: #7c3aed;
  background: rgba(245, 243, 255, 0.55);
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

/** 顶卡主数字：后厨产出量：数字 + 份（读数从左到右更符合中文习惯） */
.dro-dash-kpi__hero-metric {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.12rem 0.4rem;
  margin: 0.25rem 0 0;
  line-height: 1.15;
}

.dro-dash-kpi__hero-metric-kicker {
  font-size: 12.5px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.02em;
  flex: 0 0 auto;
}

.dro-dash-kpi__hero-metric-num-wrap {
  display: inline-flex;
  align-items: baseline;
  gap: 0.15rem;
  flex: 0 1 auto;
  min-width: 0;
}

.dro-dash-kpi__hero-metric-num {
  font-size: clamp(1.6rem, 3.35vw, 1.95rem);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  letter-spacing: -0.035em;
  font-family: var(--okfood-font-number, ui-sans-serif, system-ui, sans-serif);
}

.dro-dash-kpi__hero-metric-unit {
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
}

/**
 * 营业概览四卡：收敛字号阶梯与字重（参考稿感：主数字突出，其余偏说明性、少抢戏）
 */
.dro-dash-meal-shelf .dro-dash-kpi__hero-metric {
  gap: 0.1rem 0.32rem;
}

.dro-dash-meal-shelf .dro-dash-kpi__hero-metric-kicker {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.dro-dash-meal-shelf .dro-dash-kpi__hero-metric-num {
  font-size: clamp(1.62rem, 3.4vw, 1.92rem);
  font-weight: 800;
}

.dro-dash-meal-shelf .dro-dash-kpi__hero-metric-unit {
  font-size: 12.5px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 0.2rem 0.52rem;
}

.dro-dash-meal-shelf .dro-dash-day-nav-btn {
  font-size: 10.5px;
  font-weight: 600;
  padding: 2px 8px;
}

.dro-dash-meal-shelf .dro-dash-adjust-btn {
  font-size: 10px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-kpi__mid--distribution-chain {
  margin-top: 0.5rem;
}

.dro-dash-meal-shelf .dro-dash-distribution-chain {
  gap: 0.52rem;
  padding: 0.58rem 0.72rem;
}

.dro-dash-meal-shelf .dro-dash-chain-node-label {
  font-size: 10.5px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-chain-node {
  font-size: 10.5px;
  font-weight: 600;
  padding: 0.22rem 0.48rem;
}

.dro-dash-meal-shelf .dro-dash-branch-pill {
  padding: 0.32rem 0.22rem;
}

.dro-dash-meal-shelf .dro-dash-branch-pill__lbl {
  font-size: 8.75px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-branch-pill__val {
  font-size: 11.25px;
  font-weight: 700;
}

.dro-dash-meal-shelf .dro-dash-kpi__stat-row {
  gap: 0.55rem;
  padding-top: 0.5rem;
}

.dro-dash-meal-shelf .dro-dash-kpi__stat-row--chips-then-yoy {
  gap: 0.5rem;
  padding-top: 0.45rem;
}

.dro-dash-meal-shelf .dro-dash-kpi__stat-row--chips-then-yoy .dro-dash-yoy-chip {
  padding: 0.45rem 0.55rem;
  font-size: 11px;
}

.dro-dash-meal-shelf .dro-dash-chip {
  font-size: 10.5px;
  padding: 0.38rem 0.48rem;
}

.dro-dash-meal-shelf .dro-dash-chip__k {
  font-size: 10.5px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-chip__v {
  font-size: 0.88rem;
  font-weight: 700;
}

.dro-dash-meal-shelf .dro-dash-yoy-chip {
  font-size: 11px;
  padding: 0.48rem 0.58rem;
}

.dro-dash-meal-shelf .dro-dash-yoy-chip__prefix {
  font-size: 10px;
  font-weight: 600;
}

.dro-dash-meal-shelf .dro-dash-yoy-chip__val {
  font-size: 0.88rem;
  font-weight: 700;
}

.dro-dash-meal-shelf .dro-dash-yoy-chip__week {
  font-size: 11px;
  font-weight: 700;
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
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  padding: 0.22rem 0.65rem;
  border-radius: 999px;
  border: 1px solid transparent;
  line-height: 1.2;
  white-space: nowrap;
}

.dro-dash-pill--emerald {
  background: color-mix(in srgb, var(--el-color-primary) 10%, rgba(255, 255, 255, 0.5));
  color: var(--el-text-color-primary);
  border-color: color-mix(in srgb, var(--el-color-primary) 22%, rgba(255, 255, 255, 0.55));
}

/* 今日总盘：上一日 / 下一日快捷切换 */
.dro-dash-day-nav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dro-dash-day-nav-btn {
  border: 1px solid rgba(226, 232, 240, 0.85);
  background: rgba(255, 255, 255, 0.45);
  color: #475569;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 9px;
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
  background: rgba(239, 246, 255, 0.65);
  color: #1d4ed8;
  border-color: rgba(191, 219, 254, 0.55);
}

.dro-dash-pill--purple {
  background: rgba(250, 245, 255, 0.6);
  color: #7c3aed;
  border-color: rgba(237, 233, 254, 0.55);
}

.dro-dash-pill--violet {
  background: rgba(245, 243, 255, 0.58);
  color: #6d28d9;
  border-color: rgba(221, 214, 254, 0.5);
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
  width: 32px;
  height: 32px;
  border-radius: 9px;
  flex-shrink: 0;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.55) inset;
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
  padding: 0.75rem 0.45rem;
  background: rgba(255, 255, 255, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 14px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.4) inset;
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
  gap: 0.65rem;
  width: 100%;
  padding: 0.75rem 0.9rem;
  /* 略高于玻璃主卡的不透明度：五项指标数字读数更清楚，仍带轻微透 */
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(226, 232, 240, 0.95);
  border-radius: 14px;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.92) inset;
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
  background: color-mix(in srgb, var(--el-color-primary) 88%, #0f172a);
  color: #fff;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--el-color-primary) 22%, transparent);
}

.dro-dash-chain-node--main-blue {
  background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.18);
}

/** 堆叠式比例流条 */
.dro-dash-stacked-bar {
  display: flex;
  width: 100%;
  height: 9px;
  background: rgba(226, 232, 240, 0.65);
  border-radius: 999px;
  overflow: hidden;
  box-shadow: inset 0 1px 1px rgba(15, 23, 42, 0.06);
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

.dro-dash-branch-pill-grid--5 {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

@media (max-width: 640px) {
  .dro-dash-branch-pill-grid--5 {
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.35rem;
  }

  .dro-dash-branch-pill-grid--5 .dro-dash-branch-pill {
    padding: 0.4rem 0.2rem;
  }

  .dro-dash-branch-pill-grid--5 .dro-dash-branch-pill__lbl {
    font-size: 8px;
  }

  .dro-dash-branch-pill-grid--5 .dro-dash-branch-pill__val {
    font-size: 11px;
  }
}

.dro-dash-branch-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 0;
  padding: 0.38rem 0.28rem;
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: #ffffff;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.dro-dash-branch-pill:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.04);
}

.dro-dash-branch-pill__lbl {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-bottom: 0.125rem;
  font-size: 9px;
  font-weight: 800;
  color: #475569;
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

.dro-dash-branch-dot--waste {
  background: #ef4444;
}

.dro-dash-branch-dot--sellable {
  background: #10b981;
}

.dro-dash-branch-pill__val {
  font-size: 12px;
  font-weight: 800;
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
  padding: 0.55rem 0.7rem;
  border-radius: 10px;
  border: 1px solid transparent;
  flex-shrink: 0;
}

/* 今日：翠绿底边（与今日胶囊、进度条同系） */
.dro-dash-yoy-chip--today {
  background: rgba(236, 253, 245, 0.48);
  border-color: rgba(16, 185, 129, 0.22);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.45) inset;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
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
  background: rgba(236, 253, 245, 0.48);
  border-color: rgba(16, 185, 129, 0.22);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.45) inset;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
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

/* 后厨出餐周同比文案：与左侧「同比上周」行同为 12px */
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
  font-size: 0.9rem;
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

/* 明日午餐预测：拆解区与下方请假/同比 chip 之间略收紧（晚餐明日卡保持原间距） */
.dro-dash-kpi--tomorrow:not(.dro-dash-kpi--dinner) .dro-dash-kpi__stat-row--chips-then-yoy {
  padding-top: 0.35rem;
}

.dro-dash-kpi__stat-row--plans {
  align-items: stretch;
}

/** 今日/明日：首行双 chip，次行单次零售或暂停配送 + 同比上周并排 */
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
  padding: 0.5rem 0.65rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.35rem;
  border: 1px solid rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.38);
  font-size: 11px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.dro-dash-chip__k {
  font-size: 11px;
  font-weight: 700;
}

.dro-dash-chip__v {
  font-size: 0.925rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.dro-dash-chip__v small {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.9;
}

.dro-dash-chip--amber {
  background: rgba(255, 251, 235, 0.55);
  border-color: rgba(252, 211, 77, 0.28);
  color: #b45309;
}

.dro-dash-chip--amber .dro-dash-chip__v {
  color: #b45309;
}

.dro-dash-chip--rose {
  background: rgba(255, 241, 242, 0.55);
  border-color: rgba(251, 207, 232, 0.38);
  color: #be123c;
}

.dro-dash-chip--rose .dro-dash-chip__v {
  color: #be123c;
}

.dro-dash-chip--emerald {
  background: rgba(236, 253, 245, 0.5);
  border-color: rgba(16, 185, 129, 0.28);
  color: #047857;
}

.dro-dash-chip--emerald .dro-dash-chip__v {
  color: #047857;
}

/** 今日单次零售：与「明日预测」蓝系 pill 对齐，便于与日区绿色区分 */
.dro-dash-chip--blue {
  background: rgba(239, 246, 255, 0.55);
  border-color: rgba(191, 219, 254, 0.45);
  color: #1d4ed8;
}

.dro-dash-chip--blue .dro-dash-chip__v {
  color: #2563eb;
}

.dro-dash-chip--slate {
  background: rgba(248, 250, 252, 0.45);
  border-color: rgba(226, 232, 240, 0.65);
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

/* 电脑宽屏：菜品图在菜名旁，日期切换在「今日」栏头 */
.dro-dash-meal-shelf--pc .dro-dash-day-cluster__head {
  align-items: center;
  flex-wrap: nowrap;
}

.dro-dash-pc-day-nav {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.dro-pc-dish {
  display: flex;
  flex-direction: column;
  min-width: 0;
  margin-bottom: 2px;
}

.dro-pc-dish__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  min-width: 0;
}

.dro-pc-dish__menu {
  font-size: 12px;
  font-weight: 650;
  color: #475569;
  white-space: nowrap;
}

.dro-pc-dish__row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px 10px;
  align-items: center;
  min-width: 0;
}

.dro-pc-photo {
  width: 72px;
  height: 72px;
  border-radius: 14px;
  overflow: hidden;
  background: #e8f5e9;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.7),
    0 4px 12px rgba(15, 23, 42, 0.08);
}

.dro-pc-photo img,
.dro-pc-photo__img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.dro-pc-photo__img {
  cursor: zoom-in;
}

.dro-pc-photo__img :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
}

.dro-pc-photo--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 650;
  color: #64748b;
}

.dro-pc-dish__name {
  font-size: 14px;
  font-weight: 750;
  line-height: 1.3;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #0f172a;
}

.dro-pc-dish__copy .dro-dash-kpi__hero-metric {
  margin-top: 6px;
}

/* 手机单列：菜品图与产出量同一行，栏头日期和切换按钮不要挤掉 */
@media (max-width: 639px) {
  .dro-dash-pc-day-nav {
    margin-left: auto;
  }

  .dro-pc-dish__row {
    grid-template-columns: 64px minmax(0, 1fr);
    gap: 8px;
  }

  .dro-pc-photo {
    width: 64px;
    height: 64px;
    border-radius: 12px;
  }

  .dro-pc-dish__copy .dro-dash-kpi__hero-metric-num {
    font-size: 1.55rem;
  }
}

.dro-dash-meal-shelf--pc .dro-dash-kpi__stat-row--chips-then-yoy {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.dro-dash-meal-shelf--pc .dro-dash-chip,
.dro-dash-meal-shelf--pc .dro-dash-yoy-chip {
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 1px;
}

.dro-dash-meal-shelf--pc .dro-dash-chip__k,
.dro-dash-meal-shelf--pc .dro-dash-chip__v,
.dro-dash-meal-shelf--pc .dro-dash-yoy-chip__prefix,
.dro-dash-meal-shelf--pc .dro-dash-yoy-chip__val,
.dro-dash-meal-shelf--pc .dro-dash-yoy-chip__val--caption {
  text-align: center;
  white-space: nowrap;
}

.dro-dash-meal-shelf--pc .dro-dash-yoy-chip__left {
  flex: none;
  min-width: 0;
}

.dro-dash-meal-shelf--pc .dro-dash-yoy-chip__val--caption {
  max-width: 100%;
  white-space: normal;
}
</style>
