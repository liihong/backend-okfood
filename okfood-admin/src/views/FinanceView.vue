<script setup>
defineOptions({ name: 'FinanceView' })
import { computed, nextTick, onActivated, onMounted, ref, watch } from 'vue'
import { CreditCard } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import RetailSkuRevenueDialog from './components/RetailSkuRevenueDialog.vue'
import StatRollNumber from '../components/StatRollNumber.vue'

const loading = ref(false)
/** 递增以强制 KPI 网格重挂载，保证 keep-alive 切回时入场动画可重播 */
const statsAnimKey = ref(0)
/** @type {import('vue').Ref<any>} */
const summary = ref(null)
/** 本月卡片选中的上海自然月 YYYY-MM */
const selectedMonth = ref('')
/** @type {import('vue').Ref<any>} */
const monthWindow = ref(null)
const monthLoading = ref(false)
/** @type {import('vue').Ref<Array<{ order_id: number; time_hm: string; card_kind: string; amount_yuan: string | number }>>} */
const todayPaidCardItems = ref([])
/** 明细列表对应的上海日历日 YYYY-MM-DD（与接口 today-paid-card-orders.shanghai_today 一致） */
const financeCardOrdersDateYmd = ref('')
/** 今日卡片选中的上海日历日 YYYY-MM-DD */
const selectedDay = ref('')
/** @type {import('vue').Ref<any>} */
const dayWindow = ref(null)
const dayLoading = ref(false)
/** 商城 SKU 营业额弹窗 */
const mallSkuVisible = ref(false)
/** @type {import('vue').Ref<'day' | 'month' | 'cumulative'>} */
const mallSkuWindow = ref('month')

/** 点击「商城订单」行，按当前卡片的时间窗口打开 SKU 明细 */
function openMallSku(windowKind) {
  mallSkuWindow.value = windowKind
  mallSkuVisible.value = true
}

function fmtYuan(raw) {
  if (raw === null || raw === undefined) return '—'
  const n = Number(raw)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function safeNum(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

/** 退卡金额为 0 时不显示负号、不用警示色 */
function refundAmountNumber(amountText) {
  if (amountText === '—' || amountText == null || amountText === '') return 0
  const n = Number(String(amountText).replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

/** 拆账行：退卡且金额为 0 */
function refundIsQuiet(row) {
  return Boolean(row?.refund) && refundAmountNumber(row.amount) === 0
}

/**
 * 单张 KPI 卡拆账行配置（三列网格：标签 | 笔数 | 金额）
 * @param {ReturnType<typeof buildKpi>} kpi
 */
function breakdownRows(kpi) {
  return [
    {
      key: 'card',
      label: '开卡工单',
      dot: 'card',
      count: kpi.cardParentCount,
      unit: '笔',
      amount: kpi.cardParentAmt,
      amountRaw: kpi.cardParentAmtRaw,
    },
    {
      key: 'week',
      label: '周卡',
      dot: 'week',
      count: kpi.weekCount,
      unit: '张',
      amount: kpi.weekAmt,
      amountRaw: kpi.weekAmtRaw,
      indent: true,
    },
    {
      key: 'month',
      label: '月卡',
      dot: 'month',
      count: kpi.monthCount,
      unit: '张',
      amount: kpi.monthAmt,
      amountRaw: kpi.monthAmtRaw,
      indent: true,
    },
    {
      key: 'meal',
      label: '单次点餐',
      dot: 'meal',
      count: kpi.smCount,
      unit: '笔',
      amount: kpi.smAmt,
      amountRaw: kpi.smAmtRaw,
    },
    {
      key: 'mall',
      label: '商城订单',
      dot: 'mall',
      count: kpi.mallCount,
      unit: '笔',
      amount: kpi.mallAmt,
      amountRaw: kpi.mallAmtRaw,
    },
    {
      key: 'refund',
      label: '会员退卡',
      dot: 'refund',
      count: kpi.refundCount,
      unit: '笔',
      amount: kpi.refundAmt,
      amountRaw: kpi.refundAmtRaw,
      refund: true,
      divider: true,
    },
  ]
}

/** 拆账行圆点样式（随主色，不随卡片反白） */
function breakdownDotClass(dot) {
  const map = {
    card: 'finance-breakdown-dot--card',
    week: 'finance-breakdown-dot--week',
    month: 'finance-breakdown-dot--month',
    meal: 'finance-breakdown-dot--meal',
    mall: 'finance-breakdown-dot--mall',
    refund: 'finance-breakdown-dot--refund',
  }
  return `finance-breakdown-dot ${map[dot] || ''}`
}

/** 开卡 / 单次点餐 / 商城订单金额占比（比例条，与参考稿一致：不含退卡） */
function ratioPct(w) {
  const card =
    safeNum(w?.card_orders_weekly?.amount_yuan) + safeNum(w?.card_orders_monthly?.amount_yuan)
  const meal = safeNum(w?.single_meal_orders?.amount_yuan)
  const mall = safeNum(w?.store_retail_orders?.amount_yuan)
  const total = card + meal + mall
  if (total <= 0) return { cardPct: 0, mealPct: 0, mallPct: 0 }
  const cardPct = Math.round((card / total) * 100)
  const mealPct = Math.round((meal / total) * 100)
  const mallPct = Math.max(0, 100 - cardPct - mealPct)
  return { cardPct, mealPct, mallPct }
}

/** 将 summary 中某区间窗口转为 KPI 卡片展示字段 */
function buildKpi(w) {
  if (!w) {
    return {
      ready: false,
      totalText: '—',
      totalRaw: null,
      grossText: '—',
      netText: '—',
      count: null,
      weekCount: null,
      weekAmt: '—',
      weekAmtRaw: null,
      monthCount: null,
      monthAmt: '—',
      monthAmtRaw: null,
      cardParentCount: null,
      cardParentAmt: '—',
      cardParentAmtRaw: null,
      smCount: null,
      smAmt: '—',
      smAmtRaw: null,
      mallCount: null,
      mallAmt: '—',
      mallAmtRaw: null,
      refundCount: null,
      refundAmt: '—',
      refundAmtRaw: null,
      cardPct: null,
      mealPct: null,
      mallPct: null,
    }
  }
  const { cardPct, mealPct, mallPct } = ratioPct(w)
  const netRaw = w.net_total_amount_yuan ?? w.total_amount_yuan
  const weekCount = w.card_orders_weekly?.count ?? 0
  const monthCount = w.card_orders_monthly?.count ?? 0
  const weekAmtRaw = safeNum(w.card_orders_weekly?.amount_yuan)
  const monthAmtRaw = safeNum(w.card_orders_monthly?.amount_yuan)
  const netNum = Number(netRaw)
  return {
    ready: true,
    totalText: fmtYuan(netRaw),
    totalRaw: Number.isFinite(netNum) ? netNum : null,
    grossText: fmtYuan(w.total_amount_yuan),
    netText: fmtYuan(netRaw),
    count: w.total_count ?? 0,
    weekCount,
    weekAmt: fmtYuan(weekAmtRaw),
    weekAmtRaw,
    monthCount,
    monthAmt: fmtYuan(monthAmtRaw),
    monthAmtRaw,
    cardParentCount: weekCount + monthCount,
    cardParentAmt: fmtYuan(weekAmtRaw + monthAmtRaw),
    cardParentAmtRaw: weekAmtRaw + monthAmtRaw,
    smCount: w.single_meal_orders?.count ?? 0,
    smAmt: fmtYuan(w.single_meal_orders?.amount_yuan),
    smAmtRaw: safeNum(w.single_meal_orders?.amount_yuan),
    mallCount: w.store_retail_orders?.count ?? 0,
    mallAmt: fmtYuan(w.store_retail_orders?.amount_yuan),
    mallAmtRaw: safeNum(w.store_retail_orders?.amount_yuan),
    refundCount: w.membership_refunds?.count ?? 0,
    refundAmt: fmtYuan(w.membership_refunds?.amount_yuan),
    refundAmtRaw: safeNum(w.membership_refunds?.amount_yuan),
    cardPct,
    mealPct,
    mallPct,
  }
}

/** 明细行：上海年月日 + 时刻（接口 time_hm 为 HH:MM） */
function formatFinanceCardOrderDateTime(row) {
  const hm = (row.time_hm ?? '').trim()
  const day = financeCardOrdersDateYmd.value.trim()
  if (day && hm) return `${day} ${hm}`
  if (day) return day
  if (hm) return hm
  return '—'
}

/** 规范化日期为 YYYY-MM-DD */
function normalizeYmd(raw) {
  if (raw == null || raw === '') return ''
  const s = typeof raw === 'string' ? raw : String(raw)
  return s.length >= 10 ? s.slice(0, 10) : s
}

/** 日历日加减天数，返回 YYYY-MM-DD */
function shiftYmd(ymd, deltaDays) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd)
  if (!m) return ymd
  const dt = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  dt.setDate(dt.getDate() + deltaDays)
  const y = dt.getFullYear()
  const mo = String(dt.getMonth() + 1).padStart(2, '0')
  const d = String(dt.getDate()).padStart(2, '0')
  return `${y}-${mo}-${d}`
}

/** YYYY-MM-DD →「2026年6月4日」 */
function formatDayLabel(ymd) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd)
  if (!m) return ymd
  return `${m[1]}年${Number(m[2])}月${Number(m[3])}日`
}

const currentShanghaiToday = computed(() => normalizeYmd(summary.value?.shanghai_today))
const todayKpi = computed(() => buildKpi(dayWindow.value ?? summary.value?.today))
const todayCardBusy = computed(() => loading.value || dayLoading.value)
const isSelectedToday = computed(
  () =>
    Boolean(selectedDay.value && currentShanghaiToday.value) &&
    selectedDay.value === currentShanghaiToday.value,
)
const canGoNextDay = computed(() => {
  if (!selectedDay.value || !currentShanghaiToday.value) return false
  return selectedDay.value < currentShanghaiToday.value
})
const todayHeading = computed(() => (selectedDay.value ? formatDayLabel(selectedDay.value) : '—'))
const cardOrdersDetailTitle = computed(() => {
  if (isSelectedToday.value) return '今日开卡收款'
  const day = selectedDay.value
  return day ? `${formatDayLabel(day)}开卡收款` : '开卡收款'
})
const cardOrdersEmptyText = computed(() => {
  if (isSelectedToday.value) return '今日暂无已缴开卡记录'
  return `${formatDayLabel(selectedDay.value)}暂无已缴开卡记录`
})
const currentCalendarMonth = computed(() => String(summary.value?.shanghai_calendar_month || '').trim())
const monthKpi = computed(() => buildKpi(monthWindow.value ?? summary.value?.this_month))
const cumulativeKpi = computed(() => buildKpi(summary.value?.cumulative))
const monthCardBusy = computed(() => loading.value || monthLoading.value)
/** 每张卡数据落地后 +1，卡上数字从 0 再滚一遍 */
const dayRollKey = ref(0)
const monthRollKey = ref(0)
const cumulativeRollKey = ref(0)
watch(todayCardBusy, (busy) => {
  if (!busy && todayKpi.value.ready) dayRollKey.value += 1
})
watch(monthCardBusy, (busy) => {
  if (!busy && monthKpi.value.ready) monthRollKey.value += 1
})
watch(loading, (busy) => {
  if (!busy && cumulativeKpi.value.ready) cumulativeRollKey.value += 1
})
/** 月份卡片标题：YYYY年M月 */
const monthHeading = computed(() => (selectedMonth.value ? formatMonthLabel(selectedMonth.value) : '—'))

/** YYYY-MM 展示为「2026年6月」 */
function formatMonthLabel(ym) {
  if (!/^\d{4}-\d{2}$/.test(ym)) return ym
  const [y, m] = ym.split('-')
  return `${y}年${Number(m)}月`
}

/** 明细表交易种类胶囊（对齐参考稿 card-tag-badge） */
function cardKindPillClass(kind) {
  if (kind === '周卡') return 'finance-pill finance-pill--week'
  if (kind === '月卡') return 'finance-pill finance-pill--month'
  if (kind === '退卡') return 'finance-pill finance-pill--refund'
  if (kind === '单次点餐') return 'finance-pill finance-pill--once'
  return 'finance-pill finance-pill--count'
}

/** 拉取指定月份的已收窗口（与 summary 本月口径一致） */
async function loadMonthWindow() {
  const ym = selectedMonth.value.trim()
  if (!ym || !adminAccessToken.value) return
  if (ym === currentCalendarMonth.value && summary.value?.this_month) {
    monthWindow.value = summary.value.this_month
    return
  }
  monthLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/finance/received-month?calendar_month=${encodeURIComponent(ym)}`,
      {},
      { auth: true },
    )
    monthWindow.value = data?.window ?? null
  } catch (e) {
    showToast(e?.message || '月份数据加载失败', 'error')
    monthWindow.value = null
  } finally {
    monthLoading.value = false
  }
}

async function onMonthPickerChange() {
  await loadMonthWindow()
}

/** 拉取指定日的已收窗口 */
async function loadDayWindow() {
  const ymd = selectedDay.value.trim()
  if (!ymd || !adminAccessToken.value) return
  if (ymd === currentShanghaiToday.value && summary.value?.today) {
    dayWindow.value = summary.value.today
    return
  }
  try {
    const data = await apiJson(
      `/api/admin/finance/received-day?calendar_date=${encodeURIComponent(ymd)}`,
      {},
      { auth: true },
    )
    dayWindow.value = data?.window ?? null
  } catch (e) {
    showToast(e?.message || '日期数据加载失败', 'error')
    dayWindow.value = null
  }
}

/** 拉取指定日开卡收款明细 */
async function loadPaidCardOrdersForDay() {
  const ymd = selectedDay.value.trim()
  if (!ymd || !adminAccessToken.value) return
  const path =
    ymd === currentShanghaiToday.value
      ? '/api/admin/finance/today-paid-card-orders'
      : `/api/admin/finance/today-paid-card-orders?calendar_date=${encodeURIComponent(ymd)}`
  try {
    const cardPack = await apiJson(path, {}, { auth: true })
    todayPaidCardItems.value = Array.isArray(cardPack?.items) ? cardPack.items : []
    financeCardOrdersDateYmd.value = normalizeYmd(cardPack?.shanghai_today)
  } catch (e) {
    showToast(e?.message || '开卡明细加载失败', 'error')
    todayPaidCardItems.value = []
    financeCardOrdersDateYmd.value = ''
  }
}

/** 切换业务日后刷新今日卡与下方明细 */
async function loadDayBundle() {
  if (!adminAccessToken.value) return
  dayLoading.value = true
  try {
    await Promise.all([loadDayWindow(), loadPaidCardOrdersForDay()])
  } finally {
    dayLoading.value = false
  }
}

/** 上一日 / 下一日 */
async function shiftDay(delta) {
  const next = shiftYmd(selectedDay.value, delta)
  const max = currentShanghaiToday.value
  if (!next) return
  if (max && next > max) return
  selectedDay.value = next
  await loadDayBundle()
}

async function loadSummary() {
  if (!adminAccessToken.value) {
    handleAdminLogout()
    return
  }
  loading.value = true
  try {
    const sum = await apiJson('/api/admin/finance/received-summary', {}, { auth: true })
    summary.value = sum || null
    const curDay = normalizeYmd(sum?.shanghai_today)
    if (curDay) {
      if (!selectedDay.value || selectedDay.value > curDay) {
        selectedDay.value = curDay
      }
      if (selectedDay.value === curDay) {
        dayWindow.value = sum?.today ?? null
      }
    }
    const curMonth = String(sum?.shanghai_calendar_month || '').trim()
    if (curMonth) {
      if (!selectedMonth.value || selectedMonth.value > curMonth) {
        selectedMonth.value = curMonth
      }
      if (selectedMonth.value === curMonth) {
        monthWindow.value = sum?.this_month ?? null
      } else {
        await loadMonthWindow()
      }
    }
    if (selectedDay.value) {
      if (selectedDay.value !== curDay) {
        await loadDayWindow()
      }
      await loadPaidCardOrdersForDay()
    }
  } catch (e) {
    showToast(e?.message || '加载失败', 'error')
    summary.value = null
    monthWindow.value = null
    dayWindow.value = null
    todayPaidCardItems.value = []
    financeCardOrdersDateYmd.value = ''
  } finally {
    loading.value = false
  }
}

/** 重挂载 KPI 网格以重播 CSS 入场动画；并滚回主内容区顶部 */
async function replayStatsEnterAnimation() {
  statsAnimKey.value += 1
  await nextTick()
  window.scrollTo({ top: 0, behavior: 'smooth' })
  document.querySelector('.main-body')?.scrollTo?.({ top: 0, behavior: 'smooth' })
}

onMounted(() => {
  replayStatsEnterAnimation()
  loadSummary()
})

onActivated(() => {
  replayStatsEnterAnimation()
})
</script>

<template>
  <section class="finance-page tab-content animate-up page-content-shell members-view-fill">
    <!-- 三张 KPI：今日毛玻璃强调，本月与累计白底 -->
    <section
      :key="statsAnimKey"
      class="finance-stats-grid finance-stats-grid--animate"
      aria-label="收入概览"
    >
      <article class="finance-stat-card finance-stat-card--today" style="--finance-card-delay: 0ms">
        <div class="finance-stat-top">
          <div class="finance-stat-title">
            <p class="finance-eyebrow">日净收入</p>
            <div class="finance-stat-title-row">
              <h2 class="finance-card-heading">{{ todayHeading }}</h2>
              <nav class="finance-day-nav" aria-label="切换业务日">
                <button type="button" class="finance-day-nav-btn" :disabled="todayCardBusy" @click="shiftDay(-1)">
                  上一日
                </button>
                <button
                  type="button"
                  class="finance-day-nav-btn"
                  :disabled="todayCardBusy || !canGoNextDay"
                  @click="shiftDay(1)"
                >
                  下一日
                </button>
              </nav>
            </div>
          </div>
          <span class="finance-interval-badge">
            <span class="finance-metric finance-metric--badge">
              <template v-if="todayCardBusy || !todayKpi.ready">…</template>
              <template v-else>
                <StatRollNumber :value="todayKpi.count" :replay-key="dayRollKey" /> 笔已收
              </template>
            </span>
          </span>
        </div>
        <p class="finance-stat-value">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              <template v-if="todayCardBusy || todayKpi.totalRaw == null">…</template>
              <StatRollNumber v-else :value="todayKpi.totalRaw" :digits="2" :replay-key="dayRollKey" />
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar" aria-hidden="true">
          <div class="finance-ratio-seg finance-ratio-seg--card" :style="{ width: (todayKpi.cardPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: (todayKpi.mealPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--mall" :style="{ width: (todayKpi.mallPct ?? 0) + '%' }" />
        </div>
        <ul class="finance-ratio-legend">
          <li><i class="finance-swatch finance-swatch--card" />开卡 <b><template v-if="todayCardBusy || todayKpi.cardPct == null">…</template><StatRollNumber v-else :value="todayKpi.cardPct" suffix="%" :replay-key="dayRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--meal" />点餐 <b><template v-if="todayCardBusy || todayKpi.mealPct == null">…</template><StatRollNumber v-else :value="todayKpi.mealPct" suffix="%" :replay-key="dayRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--mall" />商城 <b><template v-if="todayCardBusy || todayKpi.mallPct == null">…</template><StatRollNumber v-else :value="todayKpi.mallPct" suffix="%" :replay-key="dayRollKey" /></b></li>
        </ul>
        <div class="finance-breakdown-grid">
          <template v-for="row in breakdownRows(todayKpi)" :key="`${selectedDay}-${row.key}`">
            <div v-if="row.divider" class="finance-breakdown-divider" />
            <span
              class="finance-breakdown-label"
              :class="{
                'finance-breakdown-label--indent': row.indent,
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              :role="row.key === 'mall' ? 'button' : undefined"
              :tabindex="row.key === 'mall' ? 0 : undefined"
              :title="row.key === 'mall' ? '查看 SKU 营业额' : undefined"
              @click="row.key === 'mall' && openMallSku('day')"
              @keydown.enter="row.key === 'mall' && openMallSku('day')"
            >
              <i :class="breakdownDotClass(row.dot)" />{{ row.label }}
              <em v-if="row.key === 'mall'" class="finance-sku-mark">SKU</em>
            </span>
            <span
              class="finance-metric finance-breakdown-count"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('day')"
            >
              {{ todayCardBusy || row.count == null ? '…' : '' }}
              <template v-if="!(todayCardBusy || row.count == null)">
                <StatRollNumber :value="row.count" :replay-key="dayRollKey" /> {{ row.unit }}
              </template>
            </span>
            <span
              class="finance-metric finance-breakdown-amt"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('day')"
            >
              <template v-if="todayCardBusy || row.amountRaw == null">…</template>
              <template v-else>
                {{ row.refund && !refundIsQuiet(row) ? '-' : '' }}¥<StatRollNumber
                  :value="row.amountRaw"
                  :digits="2"
                  :replay-key="dayRollKey"
                />
              </template>
            </span>
          </template>
        </div>
      </article>

      <article class="finance-stat-card" style="--finance-card-delay: 90ms">
        <div class="finance-stat-top">
          <div class="finance-stat-title">
            <p class="finance-eyebrow">月净收入</p>
            <div class="finance-stat-title-row">
              <h2 class="finance-card-heading">{{ monthHeading }}</h2>
              <label class="finance-month-picker" :title="`查看${formatMonthLabel(selectedMonth)}已收`">
                <input
                  v-model="selectedMonth"
                  type="month"
                  class="finance-month-picker-input"
                  aria-label="月份"
                  :max="currentCalendarMonth || undefined"
                  :disabled="monthCardBusy || !currentCalendarMonth"
                  @change="onMonthPickerChange"
                />
              </label>
            </div>
          </div>
          <span class="finance-interval-badge">
            <span class="finance-metric finance-metric--badge">
              <template v-if="monthCardBusy || !monthKpi.ready">…</template>
              <template v-else>
                <StatRollNumber :value="monthKpi.count" :replay-key="monthRollKey" /> 笔已收
              </template>
            </span>
          </span>
        </div>
        <p class="finance-stat-value">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              <template v-if="monthCardBusy || monthKpi.totalRaw == null">…</template>
              <StatRollNumber v-else :value="monthKpi.totalRaw" :digits="2" :replay-key="monthRollKey" />
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar" aria-hidden="true">
          <div class="finance-ratio-seg finance-ratio-seg--card" :style="{ width: (monthKpi.cardPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: (monthKpi.mealPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--mall" :style="{ width: (monthKpi.mallPct ?? 0) + '%' }" />
        </div>
        <ul class="finance-ratio-legend">
          <li><i class="finance-swatch finance-swatch--card" />开卡 <b><template v-if="monthCardBusy || monthKpi.cardPct == null">…</template><StatRollNumber v-else :value="monthKpi.cardPct" suffix="%" :replay-key="monthRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--meal" />点餐 <b><template v-if="monthCardBusy || monthKpi.mealPct == null">…</template><StatRollNumber v-else :value="monthKpi.mealPct" suffix="%" :replay-key="monthRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--mall" />商城 <b><template v-if="monthCardBusy || monthKpi.mallPct == null">…</template><StatRollNumber v-else :value="monthKpi.mallPct" suffix="%" :replay-key="monthRollKey" /></b></li>
        </ul>
        <div class="finance-breakdown-grid">
          <template v-for="row in breakdownRows(monthKpi)" :key="`${selectedMonth}-${row.key}`">
            <div v-if="row.divider" class="finance-breakdown-divider" />
            <span
              class="finance-breakdown-label"
              :class="{
                'finance-breakdown-label--indent': row.indent,
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              :role="row.key === 'mall' ? 'button' : undefined"
              :tabindex="row.key === 'mall' ? 0 : undefined"
              :title="row.key === 'mall' ? '查看 SKU 营业额' : undefined"
              @click="row.key === 'mall' && openMallSku('month')"
              @keydown.enter="row.key === 'mall' && openMallSku('month')"
            >
              <i :class="breakdownDotClass(row.dot)" />{{ row.label }}
              <em v-if="row.key === 'mall'" class="finance-sku-mark">SKU</em>
            </span>
            <span
              class="finance-metric finance-breakdown-count"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('month')"
            >
              {{ monthCardBusy || row.count == null ? '…' : '' }}
              <template v-if="!(monthCardBusy || row.count == null)">
                <StatRollNumber :value="row.count" :replay-key="monthRollKey" /> {{ row.unit }}
              </template>
            </span>
            <span
              class="finance-metric finance-breakdown-amt"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('month')"
            >
              <template v-if="monthCardBusy || row.amountRaw == null">…</template>
              <template v-else>
                {{ row.refund && !refundIsQuiet(row) ? '-' : '' }}¥<StatRollNumber
                  :value="row.amountRaw"
                  :digits="2"
                  :replay-key="monthRollKey"
                />
              </template>
            </span>
          </template>
        </div>
      </article>

      <article class="finance-stat-card" style="--finance-card-delay: 180ms">
        <div class="finance-stat-top">
          <div>
            <p class="finance-eyebrow">累计净收入</p>
            <h2 class="finance-card-heading">全部已入账</h2>
          </div>
          <span class="finance-interval-badge">
            <span class="finance-metric finance-metric--badge">
              <template v-if="loading || !cumulativeKpi.ready">…</template>
              <template v-else>
                <StatRollNumber :value="cumulativeKpi.count" :replay-key="cumulativeRollKey" /> 笔已收
              </template>
            </span>
          </span>
        </div>
        <p class="finance-stat-value">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              <template v-if="loading || cumulativeKpi.totalRaw == null">…</template>
              <StatRollNumber v-else :value="cumulativeKpi.totalRaw" :digits="2" :replay-key="cumulativeRollKey" />
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar" aria-hidden="true">
          <div class="finance-ratio-seg finance-ratio-seg--card" :style="{ width: (cumulativeKpi.cardPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: (cumulativeKpi.mealPct ?? 0) + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--mall" :style="{ width: (cumulativeKpi.mallPct ?? 0) + '%' }" />
        </div>
        <ul class="finance-ratio-legend">
          <li><i class="finance-swatch finance-swatch--card" />开卡 <b><template v-if="loading || cumulativeKpi.cardPct == null">…</template><StatRollNumber v-else :value="cumulativeKpi.cardPct" suffix="%" :replay-key="cumulativeRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--meal" />点餐 <b><template v-if="loading || cumulativeKpi.mealPct == null">…</template><StatRollNumber v-else :value="cumulativeKpi.mealPct" suffix="%" :replay-key="cumulativeRollKey" /></b></li>
          <li><i class="finance-swatch finance-swatch--mall" />商城 <b><template v-if="loading || cumulativeKpi.mallPct == null">…</template><StatRollNumber v-else :value="cumulativeKpi.mallPct" suffix="%" :replay-key="cumulativeRollKey" /></b></li>
        </ul>
        <div class="finance-breakdown-grid">
          <template v-for="row in breakdownRows(cumulativeKpi)" :key="row.key">
            <div v-if="row.divider" class="finance-breakdown-divider" />
            <span
              class="finance-breakdown-label"
              :class="{
                'finance-breakdown-label--indent': row.indent,
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              :role="row.key === 'mall' ? 'button' : undefined"
              :tabindex="row.key === 'mall' ? 0 : undefined"
              :title="row.key === 'mall' ? '查看 SKU 营业额' : undefined"
              @click="row.key === 'mall' && openMallSku('cumulative')"
              @keydown.enter="row.key === 'mall' && openMallSku('cumulative')"
            >
              <i :class="breakdownDotClass(row.dot)" />{{ row.label }}
              <em v-if="row.key === 'mall'" class="finance-sku-mark">SKU</em>
            </span>
            <span
              class="finance-metric finance-breakdown-count"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('cumulative')"
            >
              {{ loading || row.count == null ? '…' : '' }}
              <template v-if="!(loading || row.count == null)">
                <StatRollNumber :value="row.count" :replay-key="cumulativeRollKey" /> {{ row.unit }}
              </template>
            </span>
            <span
              class="finance-metric finance-breakdown-amt"
              :class="{
                'finance-metric--refund-danger': row.refund && !refundIsQuiet(row),
                'finance-metric--quiet': refundIsQuiet(row),
                'finance-breakdown--clickable': row.key === 'mall',
              }"
              @click="row.key === 'mall' && openMallSku('cumulative')"
            >
              <template v-if="loading || row.amountRaw == null">…</template>
              <template v-else>
                {{ row.refund && !refundIsQuiet(row) ? '-' : '' }}¥<StatRollNumber
                  :value="row.amountRaw"
                  :digits="2"
                  :replay-key="cumulativeRollKey"
                />
              </template>
            </span>
          </template>
        </div>
      </article>
    </section>

    <!-- 开卡收款明细：表头固定，仅明细行滚动 -->
    <section class="finance-detail-section">
      <div class="finance-detail-head">
        <h3 class="finance-detail-title">
          <CreditCard :size="16" aria-hidden="true" />
          {{ cardOrdersDetailTitle }}
        </h3>
        <p class="finance-detail-note">与上方「日」同一天</p>
      </div>

      <p v-if="todayCardBusy && !todayPaidCardItems.length" class="finance-detail-empty">载入中…</p>
      <p v-else-if="!todayPaidCardItems.length" class="finance-detail-empty">{{ cardOrdersEmptyText }}</p>

      <div v-else class="finance-detail-table-wrap">
        <table class="finance-detail-table finance-detail-table--body-scroll">
          <thead>
            <tr>
              <th class="finance-detail-th finance-detail-th--time">交易时间</th>
              <th class="finance-detail-th finance-detail-th--kind">交易种类</th>
              <th class="finance-detail-th finance-detail-th--amt">实收 / 轧减（元）</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in todayPaidCardItems" :key="row.order_id">
              <td class="finance-detail-datetime">{{ formatFinanceCardOrderDateTime(row) }}</td>
              <td>
                <span v-if="row.card_kind" :class="cardKindPillClass(row.card_kind)">{{ row.card_kind }}</span>
                <span v-else class="finance-detail-muted">—</span>
              </td>
              <td class="finance-detail-amt">¥{{ fmtYuan(row.amount_yuan) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <RetailSkuRevenueDialog
      v-model:visible="mallSkuVisible"
      :window="mallSkuWindow"
      :calendar-date="selectedDay"
      :calendar-month="selectedMonth"
    />
  </section>
</template>

<style scoped>
.finance-page.page-content-shell {
  /* 抵消 main-body 左右 padding，报表区沾满主内容宽度后再留出内边距 */
  margin-left: -1rem;
  margin-right: -1rem;
  width: calc(100% + 2rem);
  box-sizing: border-box;
  /* 吃满主视区，底边与左侧菜单底对齐；去掉壳层自带的底部留白 */
  padding-bottom: 0;
  overflow: hidden;
}

.finance-page {
  --finance-p: var(--el-color-primary, #8b7ec8);
  --finance-text: #1d1f21;
  --finance-muted: #5c6670;
  --finance-quiet: #8b949e;
  --finance-refund: #c4544a;
  --finance-line: rgba(15, 23, 42, 0.06);
  /* 构成三色跟主题走，但往深色压，避免浅主色下点餐/商城发白看不清 */
  --finance-tone-card: color-mix(in srgb, var(--finance-p) 86%, #1a120e);
  --finance-tone-meal: color-mix(in srgb, var(--finance-p) 62%, #1a3044);
  --finance-tone-mall: color-mix(in srgb, var(--finance-p) 34%, #12161c);
  --finance-sans: var(--okfood-font-sans);
  --finance-mono: var(--okfood-font-number);
  --finance-metric-size: 13px;
  --finance-metric-weight: 750;
  font-family: var(--finance-sans);
  color: var(--finance-text);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.finance-metric {
  font-family: var(--finance-mono);
  font-size: var(--finance-metric-size);
  font-weight: var(--finance-metric-weight);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  line-height: 1.35;
  white-space: nowrap;
}

.finance-hero-amount {
  display: inline-flex;
  align-items: baseline;
  font-size: 34px;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1.05;
  color: var(--finance-text);
}

.finance-hero-currency {
  margin-right: 0.12em;
  font-family: var(--finance-mono);
  font-size: 0.62em;
  font-weight: 700;
  letter-spacing: 0;
  font-variant-numeric: tabular-nums;
}

.finance-metric--hero-num {
  font-size: 1em;
  font-weight: 800;
  letter-spacing: -0.045em;
  line-height: 1.05;
}

.finance-metric--badge {
  display: inline-flex;
  align-items: center;
  gap: 0.28em;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
}

.finance-metric--refund-danger {
  color: var(--finance-refund);
}

.finance-metric--quiet {
  color: var(--finance-quiet);
}

.finance-stats-grid {
  display: grid;
  flex-shrink: 0;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  padding-left: 1rem;
  padding-right: 1rem;
  box-sizing: border-box;
}

@media (max-width: 900px) {
  .finance-page.page-content-shell {
    margin-left: 0;
    margin-right: 0;
    width: 100%;
  }

  .finance-stats-grid {
    padding-left: 0;
    padding-right: 0;
  }

  .finance-detail-section {
    margin-left: 0;
    margin-right: 0;
  }
}

@media (max-width: 1024px) {
  .finance-stats-grid {
    grid-template-columns: 1fr;
  }

  .finance-hero-amount {
    font-size: 32px;
  }
}

.finance-stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 18px 18px 16px;
  border-radius: 22px;
  border: 1px solid var(--finance-line);
  background: #fff;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.9) inset, 0 12px 32px rgba(25, 45, 55, 0.05);
}

.finance-stat-card--today {
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--finance-p) 16%, transparent), transparent 46%),
    rgba(255, 255, 255, 0.78);
  border-color: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(14px) saturate(1.25);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.95) inset,
    0 18px 40px color-mix(in srgb, var(--finance-p) 16%, transparent);
}

.finance-stats-grid--animate .finance-stat-card {
  animation: finance-stat-card-in 0.85s cubic-bezier(0.23, 1, 0.32, 1) both;
  animation-delay: var(--finance-card-delay, 0ms);
}

@keyframes finance-stat-card-in {
  0% {
    opacity: 0;
    transform: translateY(36px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .finance-stats-grid--animate .finance-stat-card {
    animation: none;
  }
}

.finance-stat-top {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  column-gap: 10px;
}

.finance-stat-title {
  min-width: 0;
}

.finance-eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--finance-muted);
}

.finance-card-heading {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--finance-text);
}

.finance-stat-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 3px;
}

.finance-interval-badge {
  align-self: start;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  color: var(--finance-muted);
}

.finance-interval-badge .finance-metric--badge {
  color: inherit;
}

/* 滚动数字和「笔已收」同一中线，避免位数不同把徽章撑偏 */
.finance-interval-badge :deep(.stat-roll),
.finance-breakdown-count :deep(.stat-roll),
.finance-breakdown-amt :deep(.stat-roll),
.finance-ratio-legend :deep(.stat-roll),
.finance-hero-amount :deep(.stat-roll) {
  vertical-align: baseline;
  height: 1em;
}

.finance-day-nav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.finance-day-nav-btn,
.finance-month-picker {
  height: 30px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.86);
  color: var(--finance-text);
}

.finance-day-nav-btn {
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.finance-day-nav-btn:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--finance-p) 45%, #fff);
}

.finance-day-nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.finance-month-picker {
  display: inline-flex;
  flex: none;
  align-items: center;
  height: 30px;
  padding: 0 10px 0 12px;
  cursor: pointer;
  position: relative;
  z-index: 1;
}

.finance-month-picker-input {
  border: none;
  background: transparent;
  font-family: var(--finance-mono);
  font-size: 12px;
  font-weight: 700;
  color: var(--finance-text);
  outline: none;
  cursor: pointer;
  padding: 0;
  /* 中文「2026年11月」加右侧日历图标，避免被金额行挡住 */
  width: 9.4rem;
  min-width: 9.4rem;
  height: 28px;
  line-height: 28px;
}

.finance-month-picker-input::-webkit-calendar-picker-indicator {
  margin-left: 4px;
  cursor: pointer;
}

.finance-month-picker-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.finance-month-picker:focus-within {
  border-color: color-mix(in srgb, var(--finance-p) 55%, #fff);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--finance-p) 16%, transparent);
}

.finance-stat-value {
  margin: 12px 0 10px;
}

.finance-ratio-bar {
  display: flex;
  height: 8px;
  width: 100%;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.05);
}

.finance-ratio-seg {
  height: 100%;
  min-width: 0;
  transition: width 0.35s ease;
}

.finance-ratio-seg--card {
  background: var(--finance-tone-card);
}

.finance-ratio-seg--meal {
  background: var(--finance-tone-meal);
}

.finance-ratio-seg--mall {
  background: var(--finance-tone-mall);
}

.finance-ratio-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
  color: var(--finance-muted);
  font-size: 11px;
  font-weight: 700;
}

.finance-ratio-legend b {
  color: var(--finance-text);
  font-variant-numeric: tabular-nums;
}

.finance-swatch {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 5px;
  border-radius: 50%;
  vertical-align: 1px;
}

.finance-swatch--card {
  background: var(--finance-tone-card);
}

.finance-swatch--meal {
  background: var(--finance-tone-meal);
}

.finance-swatch--mall {
  background: var(--finance-tone-mall);
}

.finance-breakdown-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 4.8rem 9.2rem;
  column-gap: 8px;
  row-gap: 8px;
  align-items: baseline;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(15, 23, 42, 0.05);
  font-size: 13px;
}

.finance-breakdown-divider {
  grid-column: 1 / -1;
  height: 1px;
  background: var(--finance-line);
}

.finance-breakdown-label {
  display: flex;
  align-items: center;
  min-width: 0;
  font-weight: 750;
  color: var(--finance-text);
}

.finance-breakdown-label--indent {
  padding-left: 16px;
  color: var(--finance-muted);
  font-weight: 650;
}

.finance-breakdown-count,
.finance-breakdown-amt {
  justify-self: end;
  text-align: right;
}

.finance-breakdown-count {
  color: var(--finance-muted);
}

.finance-breakdown-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  margin-right: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.finance-breakdown-dot--card {
  background: var(--finance-p);
}

.finance-breakdown-dot--week {
  background: #5cbf8e;
}

.finance-breakdown-dot--month {
  background: #8b7ec8;
}

.finance-breakdown-dot--meal {
  background: color-mix(in srgb, var(--finance-p) 70%, #7aa2c4);
}

.finance-breakdown-dot--mall {
  background: #9aa6b2;
}

.finance-breakdown-dot--refund {
  background: #d07a74;
}

.finance-breakdown--clickable {
  cursor: pointer;
}

.finance-breakdown-label.finance-breakdown--clickable {
  color: color-mix(in srgb, var(--finance-p) 78%, #3d3558);
}

.finance-sku-mark {
  margin-left: 6px;
  font-style: normal;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  opacity: 0.8;
}

.finance-breakdown--clickable:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
}

.finance-detail-section {
  flex: 1 1 0%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-left: 1rem;
  margin-right: 1rem;
  padding: 6px 8px 8px;
  border-radius: 22px;
  border: 1px solid var(--finance-line);
  background: #fff;
  box-shadow: 0 12px 32px rgba(25, 45, 55, 0.04);
  box-sizing: border-box;
}

.finance-detail-head {
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 12px 8px;
}

.finance-detail-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: var(--finance-text);
}

.finance-detail-title :deep(svg) {
  color: var(--finance-p);
}

.finance-detail-note {
  margin: 0;
  color: var(--finance-quiet);
  font-size: 12px;
  font-weight: 700;
}

.finance-detail-empty {
  flex: 1 1 0%;
  min-height: 0;
  margin: 0;
  padding: 2rem 12px;
  text-align: center;
  font-weight: 700;
  color: var(--finance-quiet);
  font-size: 13px;
}

.finance-detail-table-wrap {
  flex: 1 1 0%;
  min-height: 0;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
}

.finance-detail-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.finance-detail-th {
  position: sticky;
  top: 0;
  z-index: 1;
  padding: 8px 12px 10px;
  font-size: 12px;
  font-weight: 800;
  color: var(--finance-muted);
  background: #fff;
  border-bottom: 1px solid var(--finance-line);
  vertical-align: bottom;
}

.finance-detail-th--time {
  width: 38%;
  text-align: left;
}

.finance-detail-th--kind {
  width: 32%;
  text-align: left;
}

.finance-detail-th--amt {
  width: 30%;
  text-align: right;
}

.finance-detail-table tbody tr:hover {
  background: #f8fafc;
}

.finance-detail-table td {
  padding: 12px;
  font-size: 13px;
  font-weight: 650;
  border-bottom: 1px solid #f3f5f7;
  color: #3d4650;
}

.finance-detail-table tbody tr:last-child td {
  border-bottom: 0;
}

.finance-detail-datetime {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.finance-detail-amt {
  text-align: right;
  font-family: var(--finance-mono);
  font-size: 13px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--finance-text);
}

.finance-detail-muted {
  color: #94a3b8;
}

.finance-pill {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1;
}

.finance-pill--week {
  background: #e7f6ee;
  color: #1c7a4a;
}

.finance-pill--month {
  background: #eef0fb;
  color: #5347a0;
}

.finance-pill--once,
.finance-pill--count {
  background: #fff4e8;
  color: #b8611a;
}

.finance-pill--refund {
  background: #fdecec;
  color: var(--finance-refund);
}
</style>
