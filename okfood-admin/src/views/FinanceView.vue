<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Calendar, CalendarDays, CreditCard, DollarSign } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const loading = ref(false)
/** @type {import('vue').Ref<any>} */
const summary = ref(null)
/** @type {import('vue').Ref<Array<{ order_id: number; time_hm: string; card_kind: string; amount_yuan: string | number }>>} */
const todayPaidCardItems = ref([])

/** 顶栏电子钟（上海时区） */
const liveClockHm = ref('00:00:00')
const liveClockDate = ref('')
let clockTimer = null

function tickLiveClock() {
  const now = new Date()
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(now)
  const h = parts.find((p) => p.type === 'hour')?.value ?? '00'
  const m = parts.find((p) => p.type === 'minute')?.value ?? '00'
  const s = parts.find((p) => p.type === 'second')?.value ?? '00'
  liveClockHm.value = `${h}:${m}:${s}`

  const y = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric' }).format(now)
  const mo = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', month: 'numeric' }).format(now)
  const da = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', day: 'numeric' }).format(now)
  liveClockDate.value = `${y}年${mo}月${da}日`
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

/** 开卡 vs 单次点餐金额占比（复合卡片内微型比例条） */
function ratioPct(w) {
  const card = safeNum(w?.card_orders?.amount_yuan)
  const meal = safeNum(w?.single_meal_orders?.amount_yuan)
  const total = card + meal
  if (total <= 0) return { cardPct: 100, mealPct: 0 }
  const cardPct = Math.round((card / total) * 1000) / 10
  const mealPct = Math.round((100 - cardPct) * 10) / 10
  return { cardPct, mealPct }
}

/** 将 summary 中某区间窗口转为 KPI 卡片展示字段 */
function buildKpi(w) {
  if (!w) {
    return {
      totalText: '—',
      count: 0,
      cardCount: 0,
      cardAmt: '—',
      smCount: 0,
      smAmt: '—',
      cardPct: 100,
      mealPct: 0,
    }
  }
  const { cardPct, mealPct } = ratioPct(w)
  return {
    totalText: fmtYuan(w.total_amount_yuan),
    count: w.total_count ?? 0,
    cardCount: w.card_orders?.count ?? 0,
    cardAmt: fmtYuan(w.card_orders?.amount_yuan),
    smCount: w.single_meal_orders?.count ?? 0,
    smAmt: fmtYuan(w.single_meal_orders?.amount_yuan),
    cardPct,
    mealPct,
  }
}

const todayLabel = computed(() => {
  const t = summary.value?.shanghai_today
  return t ? String(t) : ''
})

const todayKpi = computed(() => buildKpi(summary.value?.today))
const monthKpi = computed(() => buildKpi(summary.value?.this_month))
const cumulativeKpi = computed(() => buildKpi(summary.value?.cumulative))

/** 明细表卡型胶囊（对齐参考稿配色） */
function cardKindPillClass(kind) {
  if (kind === '周卡') return 'finance-pill finance-pill--week'
  if (kind === '月卡') return 'finance-pill finance-pill--month'
  return 'finance-pill finance-pill--count'
}

async function loadSummary() {
  if (!adminAccessToken.value) {
    handleAdminLogout()
    return
  }
  loading.value = true
  try {
    const [sum, cardPack] = await Promise.all([
      apiJson('/api/admin/finance/received-summary', {}, { auth: true }),
      apiJson('/api/admin/finance/today-paid-card-orders', {}, { auth: true }),
    ])
    summary.value = sum || null
    todayPaidCardItems.value = Array.isArray(cardPack?.items) ? cardPack.items : []
  } catch (e) {
    showToast(e?.message || '加载失败', 'error')
    summary.value = null
    todayPaidCardItems.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  tickLiveClock()
  clockTimer = window.setInterval(tickLiveClock, 1000)
  loadSummary()
})

onUnmounted(() => {
  if (clockTimer != null) window.clearInterval(clockTimer)
})
</script>

<template>
  <section class="finance-page tab-content animate-up page-content-shell">
    <div class="page-content-title-row">
      <div class="page-heading">
        <h2 class="page-title">财务中心</h2>
      </div>
      <div class="finance-live-clock" aria-live="polite">
        <span class="finance-live-clock__hm">{{ liveClockHm }}</span>
        <span class="finance-live-clock__date">{{ liveClockDate }}</span>
      </div>
    </div>

    <!-- 三张复合 KPI 卡片：今日 / 本月 / 累计 -->
    <section class="finance-stats-grid" aria-label="收入概览">
      <article class="finance-stat-card finance-stat-card--primary">
        <div class="finance-stat-header">
          <span class="finance-stat-title">今日收入 / TODAY</span>
          <span class="finance-interval-badge finance-interval-badge--light">
            {{ loading ? '…' : `${todayKpi.count} 笔已确定` }}
          </span>
        </div>
        <div class="finance-stat-body">
          <p class="finance-stat-value finance-stat-value--light">
            ¥ {{ loading ? '…' : todayKpi.totalText }}
          </p>
          <div class="finance-ratio-wrap">
            <div class="finance-ratio-bar finance-ratio-bar--on-primary">
              <div class="finance-ratio-seg finance-ratio-seg--card" :style="{ width: todayKpi.cardPct + '%' }" />
              <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: todayKpi.mealPct + '%' }" />
            </div>
          </div>
        </div>
        <div class="finance-interval-breakdown finance-interval-breakdown--on-primary">
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label">
              <i class="finance-breakdown-dot finance-breakdown-dot--card-on-primary" />开卡工单
            </span>
            <span class="finance-breakdown-value finance-breakdown-value--light">
              {{ todayKpi.cardCount }} 笔 · ¥ {{ todayKpi.cardAmt }}
            </span>
          </div>
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label">
              <i class="finance-breakdown-dot finance-breakdown-dot--meal" />单次点餐
            </span>
            <span class="finance-breakdown-value finance-breakdown-value--light">
              {{ todayKpi.smCount }} 笔 · ¥ {{ todayKpi.smAmt }}
            </span>
          </div>
        </div>
        <Calendar class="finance-stat-watermark finance-stat-watermark--light" :size="48" aria-hidden="true" />
      </article>

      <article class="finance-stat-card">
        <div class="finance-stat-header">
          <span class="finance-stat-title finance-stat-title--muted">本月收入 / MONTH </span>
          <span class="finance-interval-badge">
            {{ loading ? '…' : `${monthKpi.count} 笔已确定` }}
          </span>
        </div>
        <div class="finance-stat-body">
          <p class="finance-stat-value">¥ {{ loading ? '…' : monthKpi.totalText }}</p>
          <div class="finance-ratio-wrap">
            <div class="finance-ratio-bar">
              <div class="finance-ratio-seg finance-ratio-seg--card-green" :style="{ width: monthKpi.cardPct + '%' }" />
              <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: monthKpi.mealPct + '%' }" />
            </div>
          </div>
        </div>
        <div class="finance-interval-breakdown">
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label finance-breakdown-label--muted">
              <i class="finance-breakdown-dot finance-breakdown-dot--card-green" />开卡工单
            </span>
            <span class="finance-breakdown-value">
              {{ monthKpi.cardCount }} 笔 · ¥ {{ monthKpi.cardAmt }}
            </span>
          </div>
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label finance-breakdown-label--muted">
              <i class="finance-breakdown-dot finance-breakdown-dot--meal" />单次点餐
            </span>
            <span class="finance-breakdown-value">
              {{ monthKpi.smCount }} 笔 · ¥ {{ monthKpi.smAmt }}
            </span>
          </div>
        </div>
        <CalendarDays class="finance-stat-watermark" :size="48" aria-hidden="true" />
      </article>

      <article class="finance-stat-card">
        <div class="finance-stat-header">
          <span class="finance-stat-title finance-stat-title--muted">累计已收 / ALL TIME</span>
          <span class="finance-interval-badge">
            {{ loading ? '…' : `${cumulativeKpi.count} 笔已确定` }}
          </span>
        </div>
        <div class="finance-stat-body">
          <p class="finance-stat-value">¥ {{ loading ? '…' : cumulativeKpi.totalText }}</p>
          <div class="finance-ratio-wrap">
            <div class="finance-ratio-bar">
              <div
                class="finance-ratio-seg finance-ratio-seg--card-green"
                :style="{ width: cumulativeKpi.cardPct + '%' }"
              />
              <div class="finance-ratio-seg finance-ratio-seg--meal" :style="{ width: cumulativeKpi.mealPct + '%' }" />
            </div>
          </div>
        </div>
        <div class="finance-interval-breakdown">
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label finance-breakdown-label--muted">
              <i class="finance-breakdown-dot finance-breakdown-dot--card-green" />开卡工单
            </span>
            <span class="finance-breakdown-value">
              {{ cumulativeKpi.cardCount }} 笔 · ¥ {{ cumulativeKpi.cardAmt }}
            </span>
          </div>
          <div class="finance-breakdown-row">
            <span class="finance-breakdown-label finance-breakdown-label--muted">
              <i class="finance-breakdown-dot finance-breakdown-dot--meal" />单次点餐
            </span>
            <span class="finance-breakdown-value">
              {{ cumulativeKpi.smCount }} 笔 · ¥ {{ cumulativeKpi.smAmt }}
            </span>
          </div>
        </div>
        <DollarSign class="finance-stat-watermark" :size="48" aria-hidden="true" />
      </article>
    </section>

    <!-- 今日开卡收款明细 -->
    <section class="finance-detail-section">
      <div class="finance-detail-head">
        <h3 class="finance-detail-title">
          <CreditCard :size="18" aria-hidden="true" />
          今日开卡收款明细
          <span v-if="todayLabel" class="finance-detail-title__date">({{ todayLabel }})</span>
        </h3>
        <p class="finance-detail-sub">
          已缴工单按上海时间列出；时刻与卡型对应单笔收入。口径与上方「今日收入」中的开卡统计一致（工单
          <strong class="finance-detail-sub__em">updated_at</strong> 落入当日）。
        </p>
      </div>

      <p v-if="loading && !todayPaidCardItems.length" class="finance-detail-empty">载入中…</p>
      <p v-else-if="!todayPaidCardItems.length" class="finance-detail-empty">今日暂无已缴开卡记录</p>

      <div v-else class="finance-detail-table-wrap">
        <table class="finance-detail-table">
          <thead>
            <tr>
              <th class="finance-detail-th finance-detail-th--time">时间</th>
              <th class="finance-detail-th finance-detail-th--kind">卡型</th>
              <th class="finance-detail-th finance-detail-th--amt">实收 (元)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in todayPaidCardItems" :key="row.order_id">
              <td>{{ row.time_hm || '—' }}</td>
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
.finance-page {
  --finance-primary: #0d5c46;
  --finance-meal: #3b82f6;
  --finance-border: #eaedf1;
  --finance-muted: #64748b;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.finance-live-clock {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-style: normal;
}

.finance-live-clock__hm {
  font-size: 16px;
  font-weight: 800;
  color: var(--finance-primary);
}

.finance-live-clock__date {
  margin-top: 2px;
  font-size: 10px;
  font-weight: 600;
  color: var(--finance-muted);
}

/* 三张 KPI 复合卡片 */
.finance-stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
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
  justify-content: space-between;
  min-height: 280px;
  padding: 32px;
  border-radius: 32px;
  border: 1px solid var(--finance-border);
  background: #fff;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.08);
  transition:
    transform 0.3s ease,
    box-shadow 0.3s ease;
}

.finance-stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 10px 25px -10px rgba(148, 163, 184, 0.15);
}

.finance-stat-card--primary {
  background-color: var(--finance-primary);
  border-color: var(--finance-primary);
  color: #fff;
  box-shadow: 0 10px 30px -10px rgba(13, 92, 70, 0.3);
}

.finance-stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
  z-index: 2;
}

.finance-stat-title {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  opacity: 0.8;
}

.finance-stat-title--muted {
  color: var(--finance-muted);
  opacity: 1;
}

.finance-interval-badge {
  flex-shrink: 0;
  background-color: #f1f5f9;
  color: var(--finance-muted);
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 8px;
}

.finance-interval-badge--light {
  background-color: rgba(255, 255, 255, 0.15);
  color: #fff;
}

.finance-stat-body {
  margin-top: 16px;
  z-index: 2;
}

.finance-stat-value {
  margin: 0;
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #0f172a;
  font-family: 'Plus Jakarta Sans', ui-monospace, monospace;
}

.finance-stat-value--light {
  color: #fff;
}

.finance-ratio-wrap {
  margin-top: 12px;
  margin-bottom: 16px;
}

.finance-ratio-bar {
  height: 8px;
  border-radius: 6px;
  display: flex;
  overflow: hidden;
  background-color: #f1f5f9;
  border: 1px solid rgba(226, 232, 240, 0.5);
}

.finance-ratio-bar--on-primary {
  background-color: rgba(255, 255, 255, 0.1);
  border-color: rgba(255, 255, 255, 0.15);
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

.finance-interval-breakdown {
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-top: 1px dashed var(--finance-border);
  padding-top: 14px;
  z-index: 2;
}

.finance-interval-breakdown--on-primary {
  border-top-color: rgba(255, 255, 255, 0.15);
}

.finance-breakdown-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 12px;
  font-weight: 600;
}

.finance-breakdown-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.8);
}

.finance-breakdown-label--muted {
  color: var(--finance-muted);
}

.finance-breakdown-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
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

.finance-breakdown-value {
  font-weight: 700;
  color: #0f172a;
  text-align: right;
  white-space: nowrap;
}

.finance-breakdown-value--light {
  color: #fff;
}

.finance-stat-watermark {
  position: absolute;
  right: 24px;
  bottom: 74px;
  opacity: 0.06;
  color: #cbd5e1;
  pointer-events: none;
}

.finance-stat-watermark--light {
  color: rgba(255, 255, 255, 0.98);
  opacity: 0.12;
}

/* 明细区 */
.finance-detail-section {
  background: #fff;
  border-radius: 32px;
  border: 1px solid var(--finance-border);
  padding: 32px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.05);
}

.finance-detail-head {
  margin-bottom: 24px;
}

.finance-detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #0f172a;
}

.finance-detail-title__date {
  font-weight: 500;
  color: var(--finance-muted);
  margin-left: 2px;
}

.finance-detail-sub {
  margin: 6px 0 0;
  font-size: 11px;
  font-weight: 500;
  color: var(--finance-muted);
  line-height: 1.55;
  max-width: 52rem;
}

.finance-detail-sub__em {
  color: var(--finance-primary);
  font-weight: 800;
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
}

.finance-detail-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.finance-detail-th {
  font-size: 11px;
  font-weight: 800;
  color: var(--finance-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 16px;
  border-bottom: 1px solid var(--finance-border);
}

.finance-detail-th--time {
  width: 25%;
}

.finance-detail-th--kind {
  width: 35%;
}

.finance-detail-th--amt {
  width: 40%;
  text-align: right;
}

.finance-detail-table td {
  padding: 16px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--finance-border);
  color: #0f172a;
}

.finance-detail-amt {
  text-align: right;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 14px;
  font-weight: 700;
  color: #10b981;
}

.finance-detail-muted {
  color: #94a3b8;
}

.finance-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
}

.finance-pill--count {
  background-color: #fef3c7;
  color: #d97706;
}

.finance-pill--week {
  background-color: #d1fae5;
  color: #065f46;
}

.finance-pill--month {
  background-color: #dbeafe;
  color: #1e40af;
}
</style>
