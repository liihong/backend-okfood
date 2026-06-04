<script setup>
defineOptions({ name: 'FinanceView' })
import { computed, nextTick, onActivated, onMounted, ref } from 'vue'
import { CreditCard } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

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

/** 徽章：N 笔已收 */
function badgeLine(count) {
  return `${count} 笔已收`
}

/** 拆账网格：笔数列 */
function countUnitText(count, unit) {
  return `${count} ${unit}`
}

/** 拆账网格：金额列（¥ 与数字同字号） */
function amountColText(amountText, { refund = false } = {}) {
  if (amountText === '—') return '—'
  return refund ? `-¥${amountText}` : `¥${amountText}`
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
    },
    {
      key: 'week',
      label: '周卡',
      dot: 'week',
      count: kpi.weekCount,
      unit: '张',
      amount: kpi.weekAmt,
      indent: true,
    },
    {
      key: 'month',
      label: '月卡',
      dot: 'month',
      count: kpi.monthCount,
      unit: '张',
      amount: kpi.monthAmt,
      indent: true,
    },
    {
      key: 'meal',
      label: '单次点餐',
      dot: 'meal',
      count: kpi.smCount,
      unit: '笔',
      amount: kpi.smAmt,
    },
    {
      key: 'refund',
      label: '会员退卡',
      dot: 'refund',
      count: kpi.refundCount,
      unit: '笔',
      amount: kpi.refundAmt,
      refund: true,
      divider: true,
    },
  ]
}

/** 拆账行圆点样式 */
function breakdownDotClass(dot, onPrimary) {
  const map = {
    card: onPrimary ? 'finance-breakdown-dot--card-on-primary' : 'finance-breakdown-dot--card-green',
    week: 'finance-breakdown-dot--week',
    month: 'finance-breakdown-dot--month',
    meal: 'finance-breakdown-dot--meal',
    refund: 'finance-breakdown-dot--refund-hot',
  }
  return `finance-breakdown-dot ${map[dot] || ''}`
}

/** 周卡+月卡 vs 单次点餐金额占比（比例条，与参考稿一致：不含退卡） */
function ratioPct(w) {
  const card =
    safeNum(w?.card_orders_weekly?.amount_yuan) + safeNum(w?.card_orders_monthly?.amount_yuan)
  const meal = safeNum(w?.single_meal_orders?.amount_yuan)
  const total = card + meal
  if (total <= 0) return { cardPct: 0, mealPct: 0 }
  const cardPct = Math.round((card / total) * 100)
  const mealPct = 100 - cardPct
  return { cardPct, mealPct }
}

/** 将 summary 中某区间窗口转为 KPI 卡片展示字段 */
function buildKpi(w) {
  if (!w) {
    return {
      totalText: '—',
      grossText: '—',
      netText: '—',
      count: 0,
      weekCount: 0,
      weekAmt: '—',
      monthCount: 0,
      monthAmt: '—',
      cardParentCount: 0,
      cardParentAmt: '—',
      smCount: 0,
      smAmt: '—',
      refundCount: 0,
      refundAmt: '—',
      cardPct: 0,
      mealPct: 0,
    }
  }
  const { cardPct, mealPct } = ratioPct(w)
  const netRaw = w.net_total_amount_yuan ?? w.total_amount_yuan
  const weekCount = w.card_orders_weekly?.count ?? 0
  const monthCount = w.card_orders_monthly?.count ?? 0
  const weekAmtRaw = safeNum(w.card_orders_weekly?.amount_yuan)
  const monthAmtRaw = safeNum(w.card_orders_monthly?.amount_yuan)
  return {
    totalText: fmtYuan(netRaw),
    grossText: fmtYuan(w.total_amount_yuan),
    netText: fmtYuan(netRaw),
    count: w.total_count ?? 0,
    weekCount,
    weekAmt: fmtYuan(weekAmtRaw),
    monthCount,
    monthAmt: fmtYuan(monthAmtRaw),
    cardParentCount: weekCount + monthCount,
    cardParentAmt: fmtYuan(weekAmtRaw + monthAmtRaw),
    smCount: w.single_meal_orders?.count ?? 0,
    smAmt: fmtYuan(w.single_meal_orders?.amount_yuan),
    refundCount: w.membership_refunds?.count ?? 0,
    refundAmt: fmtYuan(w.membership_refunds?.amount_yuan),
    cardPct,
    mealPct,
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
const todayCardTitle = computed(() => {
  if (isSelectedToday.value) return '今日净收入 / TODAY'
  return `${formatDayLabel(selectedDay.value)}净收入 / DAY`
})
const cardOrdersDetailTitle = computed(() => {
  if (isSelectedToday.value) return '今日开卡收款明细'
  const day = selectedDay.value
  return day ? `${formatDayLabel(day)} 开卡收款明细` : '开卡收款明细'
})
const cardOrdersEmptyText = computed(() => {
  if (isSelectedToday.value) return '今日暂无已缴开卡记录'
  return `${formatDayLabel(selectedDay.value)}暂无已缴开卡记录`
})
const currentCalendarMonth = computed(() => String(summary.value?.shanghai_calendar_month || '').trim())
const monthKpi = computed(() => buildKpi(monthWindow.value ?? summary.value?.this_month))
const cumulativeKpi = computed(() => buildKpi(summary.value?.cumulative))
const monthCardBusy = computed(() => loading.value || monthLoading.value)
const isSelectedCurrentMonth = computed(
  () =>
    Boolean(selectedMonth.value && currentCalendarMonth.value) &&
    selectedMonth.value === currentCalendarMonth.value,
)
/** 月份卡片标题：选中当月显示「本月」，否则显示「YYYY年M月」 */
const monthCardTitle = computed(() => {
  if (isSelectedCurrentMonth.value) return '本月净收入 / MONTH'
  const ym = selectedMonth.value
  if (!/^\d{4}-\d{2}$/.test(ym)) return '月度净收入 / MONTH'
  const [y, m] = ym.split('-')
  return `${y}年${Number(m)}月净收入 / MONTH`
})

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
  <section class="finance-page tab-content animate-up page-content-shell">
    <!-- 三张 KPI 卡片：今日 / 本月 / 累计（对齐财务中心参考稿） -->
    <section
      :key="statsAnimKey"
      class="finance-stats-grid finance-stats-grid--animate"
      aria-label="收入概览"
    >
      <article
        class="finance-stat-card finance-stat-card--primary"
        style="--finance-card-delay: 0ms"
      >
        <div class="finance-stat-header finance-stat-header--today">
          <div class="finance-stat-header-main">
            <span class="finance-stat-title">{{ todayCardTitle }}</span>
            <nav class="finance-day-nav" aria-label="切换业务日">
              <button
                type="button"
                class="finance-day-nav-btn"
                :disabled="todayCardBusy"
                @click="shiftDay(-1)"
              >
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
          <span class="finance-interval-badge finance-interval-badge--light">
            <span class="finance-metric finance-metric--badge finance-metric--on-primary">
              {{ todayCardBusy ? '…' : badgeLine(todayKpi.count) }}
            </span>
          </span>
        </div>
        <p class="finance-stat-value finance-stat-value--light">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              {{ todayCardBusy ? '…' : todayKpi.totalText }}
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar finance-ratio-bar--on-primary">
          <div class="finance-ratio-seg finance-ratio-seg--card" :style="{ width: todayKpi.cardPct + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: todayKpi.mealPct + '%' }" />
        </div>
        <div class="finance-breakdown-grid finance-breakdown-grid--on-primary">
          <template v-for="row in breakdownRows(todayKpi)" :key="`${selectedDay}-${row.key}`">
            <div v-if="row.divider" class="finance-breakdown-divider finance-breakdown-divider--on-primary" />
            <span
              class="finance-breakdown-label"
              :class="{ 'finance-breakdown-label--indent': row.indent }"
            >
              <i :class="breakdownDotClass(row.dot, true)" />{{ row.label }}
            </span>
            <span
              class="finance-metric finance-breakdown-count finance-metric--on-primary"
              :class="{ 'finance-metric--refund-warn': row.refund }"
            >
              {{ todayCardBusy ? '…' : countUnitText(row.count, row.unit) }}
            </span>
            <span
              class="finance-metric finance-breakdown-amt finance-metric--on-primary"
              :class="{ 'finance-metric--refund-warn': row.refund }"
            >
              {{ todayCardBusy ? '…' : amountColText(row.amount, { refund: row.refund }) }}
            </span>
          </template>
        </div>
      </article>

      <article class="finance-stat-card finance-stat-card--month" style="--finance-card-delay: 90ms">
        <div class="finance-stat-header finance-stat-header--month">
          <div class="finance-stat-header-main">
            <span class="finance-stat-title finance-stat-title--muted">{{ monthCardTitle }}</span>
            <label class="finance-month-picker" :title="`查看${formatMonthLabel(selectedMonth)}已收`">
              <span class="finance-month-picker-label">月份</span>
              <input
                v-model="selectedMonth"
                type="month"
                class="finance-month-picker-input"
                :max="currentCalendarMonth || undefined"
                :disabled="monthCardBusy || !currentCalendarMonth"
                @change="onMonthPickerChange"
              />
            </label>
          </div>
          <span class="finance-interval-badge">
            <span class="finance-metric finance-metric--badge">
              {{ monthCardBusy ? '…' : badgeLine(monthKpi.count) }}
            </span>
          </span>
        </div>
        <p class="finance-stat-value">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              {{ monthCardBusy ? '…' : monthKpi.totalText }}
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar">
          <div class="finance-ratio-seg finance-ratio-seg--card-green" :style="{ width: monthKpi.cardPct + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: monthKpi.mealPct + '%' }" />
        </div>
        <div class="finance-breakdown-grid">
          <template v-for="row in breakdownRows(monthKpi)" :key="`${selectedMonth}-${row.key}`">
            <div v-if="row.divider" class="finance-breakdown-divider" />
            <span
              class="finance-breakdown-label finance-breakdown-label--muted"
              :class="{ 'finance-breakdown-label--indent': row.indent }"
            >
              <i :class="breakdownDotClass(row.dot, false)" />{{ row.label }}
            </span>
            <span class="finance-metric finance-breakdown-count">
              {{ monthCardBusy ? '…' : countUnitText(row.count, row.unit) }}
            </span>
            <span
              class="finance-metric finance-breakdown-amt"
              :class="{ 'finance-metric--refund-danger': row.refund }"
            >
              {{ monthCardBusy ? '…' : amountColText(row.amount, { refund: row.refund }) }}
            </span>
          </template>
        </div>
      </article>

      <article class="finance-stat-card" style="--finance-card-delay: 180ms">
        <div class="finance-stat-header">
          <span class="finance-stat-title finance-stat-title--muted">累计净收入 / ALL TIME</span>
          <span class="finance-interval-badge">
            <span class="finance-metric finance-metric--badge">
              {{ loading ? '…' : badgeLine(cumulativeKpi.count) }}
            </span>
          </span>
        </div>
        <p class="finance-stat-value">
          <span class="finance-hero-amount">
            <span class="finance-hero-currency">¥</span>
            <span class="finance-metric finance-metric--hero-num">
              {{ loading ? '…' : cumulativeKpi.totalText }}
            </span>
          </span>
        </p>
        <div class="finance-ratio-bar">
          <div class="finance-ratio-seg finance-ratio-seg--card-green" :style="{ width: cumulativeKpi.cardPct + '%' }" />
          <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: cumulativeKpi.mealPct + '%' }" />
        </div>
        <div class="finance-breakdown-grid">
          <template v-for="row in breakdownRows(cumulativeKpi)" :key="row.key">
            <div v-if="row.divider" class="finance-breakdown-divider" />
            <span
              class="finance-breakdown-label finance-breakdown-label--muted"
              :class="{ 'finance-breakdown-label--indent': row.indent }"
            >
              <i :class="breakdownDotClass(row.dot, false)" />{{ row.label }}
            </span>
            <span class="finance-metric finance-breakdown-count">
              {{ loading ? '…' : countUnitText(row.count, row.unit) }}
            </span>
            <span
              class="finance-metric finance-breakdown-amt"
              :class="{ 'finance-metric--refund-danger': row.refund }"
            >
              {{ loading ? '…' : amountColText(row.amount, { refund: row.refund }) }}
            </span>
          </template>
        </div>
      </article>
    </section>

    <!-- 今日开卡收款明细：表头固定在标题下方，仅明细行区域滚动 -->
    <section class="finance-detail-section">
      <div class="finance-detail-head">
        <h3 class="finance-detail-title">
          <CreditCard :size="18" aria-hidden="true" />
          {{ cardOrdersDetailTitle }}
        </h3>
      </div>

      <p v-if="todayCardBusy && !todayPaidCardItems.length" class="finance-detail-empty">载入中…</p>
      <p v-else-if="!todayPaidCardItems.length" class="finance-detail-empty">{{ cardOrdersEmptyText }}</p>

      <div v-else class="finance-detail-table-wrap">
        <table class="finance-detail-table finance-detail-table--body-scroll">
          <thead>
            <tr>
              <th class="finance-detail-th finance-detail-th--time">交易时间</th>
              <th class="finance-detail-th finance-detail-th--kind">交易种类</th>
              <th class="finance-detail-th finance-detail-th--amt">实收/轧减金额 (元)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in todayPaidCardItems" :key="row.order_id">
              <td class="finance-detail-datetime">{{ formatFinanceCardOrderDateTime(row) }}</td>
              <td>
                <span v-if="row.card_kind" :class="cardKindPillClass(row.card_kind)">{{ row.card_kind }}</span>
                <span v-else class="finance-detail-muted">—</span>
              </td>
              <td class="finance-detail-amt">¥ {{ fmtYuan(row.amount_yuan) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>

<style scoped>
.finance-page.page-content-shell {
  /* 抵消 main-body 左右 padding，报表区尽量沾满主内容宽度 */
  margin-left: -1rem;
  margin-right: -1rem;
  width: calc(100% + 2rem);
  box-sizing: border-box;
  padding-bottom: 0.75rem;
}

.finance-page {
  --finance-primary: #0d5c46;
  --finance-card-dark: #093f30;
  --finance-meal: #3b82f6;
  --finance-week: #10b981;
  --finance-week-bg: #ecfdf5;
  --finance-week-text: #0369a1;
  --finance-month-bg: #eff6ff;
  --finance-month-text: #4338ca;
  --finance-once-bg: #fffbeb;
  --finance-once-text: #c2410c;
  --finance-refund: #ef4444;
  --finance-refund-bg: #fef2f2;
  --finance-refund-text: #dc2626;
  --finance-refund-warn: #ffaa00;
  --finance-border: #eaedf1;
  --finance-muted: #64748b;
  --finance-text-main: #0f172a;
  --finance-sans: var(--okfood-font-sans);
  font-family: var(--finance-sans);
  /* 金额/笔数/时间与明细表一致，统一高质感数字体 */
  --finance-mono: var(--okfood-font-number);
  --finance-metric-size: 14px;
  --finance-metric-weight: 700;
  --finance-hero-size: 40px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/**
 * 所有金额/笔数字符串统一排版（整段渲染，¥ 与数字同字号）
 * 拆账行、徽章、副标题共用 metric 字号；仅顶部净收入用 hero 字号。
 */
.finance-metric {
  font-family: var(--finance-mono);
  font-size: var(--finance-metric-size);
  font-weight: var(--finance-metric-weight);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.01em;
  line-height: 1.35;
  white-space: nowrap;
}

/* 主金额：¥ 与数字分列，统一间距 */
.finance-hero-amount {
  display: inline-flex;
  align-items: baseline;
  gap: 0.28em;
}

.finance-hero-currency,
.finance-metric--hero-num {
  font-family: var(--finance-mono);
  font-size: var(--finance-hero-size);
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.08;
  font-variant-numeric: tabular-nums;
}

.finance-stat-value--light .finance-hero-currency,
.finance-stat-value--light .finance-metric--hero-num {
  color: #fff;
}

.finance-metric--badge {
  font-size: var(--finance-metric-size);
  font-weight: var(--finance-metric-weight);
}

.finance-metric--on-primary {
  color: #fff;
}

.finance-metric--refund-warn {
  color: var(--finance-refund-warn);
}

.finance-metric--refund-danger {
  color: var(--finance-refund);
}

/* 三张 KPI 复合卡片；左右留白与主内容区内边距对齐（抵消父级负 margin 拉满后的贴边感） */
.finance-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
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

  /* 小屏已无负边距拉满时，不必再向内缩一档，否则会与 main-body padding 双重留白 */
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
}

.finance-stat-card {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 330px;
  padding: 28px;
  border-radius: 28px;
  border: 1px solid var(--finance-border);
  background: #fff;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease;
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

.finance-stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(148, 163, 184, 0.08);
}

@media (prefers-reduced-motion: reduce) {
  .finance-stats-grid--animate .finance-stat-card {
    animation: none;
  }

  .finance-stat-card:hover {
    transform: none;
  }
}

.finance-stat-card--primary {
  background-color: var(--finance-card-dark);
  border: none;
  color: #fff;
  box-shadow: 0 10px 30px -10px rgba(9, 63, 48, 0.3);
}

.finance-stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  z-index: 2;
}

.finance-stat-header--today,
.finance-stat-header--month {
  align-items: center;
}

/* 今日卡：上一日 / 下一日 */
.finance-day-nav {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.finance-day-nav-btn {
  border: 1px solid rgba(255, 255, 255, 0.22);
  background-color: rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.92);
  font-size: 11px;
  font-weight: 800;
  padding: 4px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease;
}

.finance-day-nav-btn:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.35);
}

.finance-day-nav-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* 标题与月份选择同一顶栏横排 */
.finance-stat-header-main {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

/* 本月卡片：月份选择（原生 month，与参考稿胶囊风格一致） */
.finance-month-picker {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 8px;
  background-color: #f8fafc;
  border: 1px solid var(--finance-border);
  cursor: pointer;
}

.finance-month-picker-label {
  font-size: 10px;
  font-weight: 800;
  color: var(--finance-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.finance-month-picker-input {
  border: none;
  background: transparent;
  font-family: var(--finance-mono);
  font-size: var(--finance-metric-size);
  font-weight: var(--finance-metric-weight);
  color: #0f172a;
  outline: none;
  cursor: pointer;
  padding: 0;
  min-width: 6.5rem;
}

.finance-month-picker-input:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.finance-month-picker:focus-within {
  border-color: var(--finance-primary);
  box-shadow: 0 0 0 2px rgba(13, 92, 70, 0.12);
}

.finance-stat-title {
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.7;
}

.finance-stat-title--muted {
  color: var(--finance-muted);
  opacity: 1;
}

.finance-interval-badge {
  flex-shrink: 0;
  background-color: #f1f5f9;
  color: var(--finance-muted);
  padding: 4px 10px;
  border-radius: 8px;
}

.finance-interval-badge .finance-metric--badge {
  color: inherit;
}

.finance-interval-badge--light {
  background-color: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.finance-stat-value {
  margin: 15px 0;
  color: #0f172a;
}

.finance-ratio-bar {
  height: 6px;
  width: 100%;
  border-radius: 3px;
  margin-bottom: 20px;
  display: flex;
  overflow: hidden;
  background-color: #f1f5f9;
}

.finance-ratio-bar--on-primary {
  background-color: rgba(255, 255, 255, 0.1);
}

.finance-ratio-seg {
  height: 100%;
  min-width: 0;
  transition: width 0.35s ease;
}

.finance-ratio-seg--card {
  background-color: #fff;
}

.finance-ratio-seg--card-green {
  background-color: var(--finance-primary);
}

.finance-ratio-seg--meal {
  background-color: var(--finance-meal);
}

/**
 * 拆账三列网格：标签 | 笔数 | 金额
 * 列宽与行列间距固定，保证各卡、各行数字纵向对齐。
 */
.finance-breakdown-grid {
  --finance-grid-row-gap: 10px;
  --finance-grid-col-gap: 12px;
  --finance-grid-count-col: 4.5rem;
  --finance-grid-amt-col: 9.75rem;
  display: grid;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px dashed var(--finance-border);
  grid-template-columns: minmax(0, 1fr) var(--finance-grid-count-col) var(--finance-grid-amt-col);
  column-gap: var(--finance-grid-col-gap);
  row-gap: var(--finance-grid-row-gap);
  align-items: center;
}

.finance-breakdown-grid--on-primary {
  border-top-color: rgba(255, 255, 255, 0.08);
}

.finance-breakdown-divider {
  grid-column: 1 / -1;
  height: 0;
  margin-top: 2px;
  border-top: 1px dashed var(--finance-border);
}

.finance-breakdown-divider--on-primary {
  border-top-color: rgba(255, 255, 255, 0.08);
}

.finance-breakdown-count,
.finance-breakdown-amt {
  justify-self: end;
  text-align: right;
}

.finance-breakdown-count {
  min-width: var(--finance-grid-count-col);
}

.finance-breakdown-amt {
  min-width: var(--finance-grid-amt-col);
}

.finance-breakdown-label {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.8);
}

.finance-breakdown-label--muted {
  color: var(--finance-muted);
}

.finance-breakdown-label--indent {
  padding-left: 14px;
}

.finance-breakdown-grid--on-primary .finance-breakdown-label--indent {
  opacity: 0.75;
}

.finance-breakdown-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.finance-breakdown-dot--week {
  background-color: var(--finance-week);
}

.finance-breakdown-dot--month {
  background-color: var(--finance-meal);
}

.finance-breakdown-dot--card-on-primary {
  background-color: #fff;
}

.finance-breakdown-dot--card-green {
  background-color: var(--finance-primary);
}

.finance-breakdown-dot--meal {
  background-color: var(--finance-meal);
}

.finance-breakdown-dot--refund-hot {
  background-color: #ff3b30;
}

/* 开卡收款明细列表（字体/字号对齐参考稿 finance-table） */
.finance-detail-section {
  background: #fff;
  border-radius: 28px;
  border: 1px solid var(--finance-border);
  padding: 24px 28px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  margin-left: 1rem;
  margin-right: 1rem;
  box-sizing: border-box;
  font-family: var(--finance-sans);
}

.finance-detail-head {
  margin-bottom: 20px;
}

.finance-detail-title {
  margin: 0;
  font-size: 15px;
  font-weight: 900;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--finance-text-main);
}

.finance-detail-empty {
  margin: 0;
  padding: 2rem 0;
  text-align: center;
  font-weight: 700;
  color: #94a3b8;
  font-size: 13px;
}

.finance-detail-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--finance-border);
  border-radius: 16px;
  background: #fff;
}

.finance-detail-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-family: var(--finance-sans);
}

/**
 * 仅 tbody 区域纵向滚动，表头不随列表滚动（display:block 分块表格常见写法）
 */
.finance-detail-table--body-scroll thead,
.finance-detail-table--body-scroll tbody tr {
  display: table;
  width: 100%;
  table-layout: fixed;
}

.finance-detail-table--body-scroll tbody {
  display: block;
  max-height: min(54vh, 520px);
  overflow-y: auto;
  overflow-x: hidden;
  -webkit-overflow-scrolling: touch;
}

.finance-detail-table--body-scroll thead {
  box-shadow: 0 1px 0 var(--finance-border);
}

.finance-detail-th {
  font-size: 12px;
  font-weight: 800;
  color: var(--finance-muted);
  text-transform: none;
  letter-spacing: 0;
  padding: 14px 16px;
  border-bottom: 1px solid var(--finance-border);
  background-color: #f8fafc;
  vertical-align: bottom;
}

.finance-detail-table--body-scroll thead .finance-detail-th {
  border-bottom: none;
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

.finance-detail-table tbody tr {
  transition: background-color 0.2s ease;
}

.finance-detail-table tbody tr:hover {
  background-color: #f8fafc;
}

.finance-detail-table td {
  padding: 14px 16px;
  font-size: 13px;
  font-weight: 600;
  font-family: var(--finance-sans);
  border-bottom: 1px solid var(--finance-border);
  color: var(--finance-text-main);
}

.finance-detail-table td:first-child {
  text-align: left;
}

.finance-detail-datetime {
  white-space: nowrap;
}

.finance-detail-table td:nth-child(2) {
  /* 与表头「交易种类」同一左缘；胶囊左对齐不占满整格居中 */
  text-align: left;
  vertical-align: middle;
}

.finance-detail-table td:nth-child(2) .finance-detail-muted {
  display: inline-block;
}

.finance-detail-amt {
  text-align: right;
  font-family: var(--finance-mono);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--finance-text-main);
}

.finance-detail-muted {
  color: #94a3b8;
}

.finance-pill {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 800;
  font-family: var(--finance-sans);
  line-height: 1.35;
}

.finance-pill--count {
  background-color: var(--finance-once-bg);
  color: var(--finance-once-text);
}

.finance-pill--week {
  background-color: var(--finance-week-bg);
  color: var(--finance-week-text);
}

.finance-pill--month {
  background-color: var(--finance-month-bg);
  color: var(--finance-month-text);
}

.finance-pill--once {
  background-color: var(--finance-once-bg);
  color: var(--finance-once-text);
}

.finance-pill--refund {
  background-color: var(--finance-refund-bg);
  color: var(--finance-refund-text);
}
</style>
