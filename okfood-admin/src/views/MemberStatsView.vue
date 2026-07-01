<script setup>
defineOptions({ name: 'MemberStatsView' })
import { computed, onActivated, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Users,
  TrendingUp,
  Bell,
  Ticket,
  PieChart,
  UserCheck,
  Clock,
  RotateCcw,
  Activity,
  TrendingDown,
  CalendarDays,
  CalendarRange,
  Repeat,
  ChevronRight,
  UserMinus,
  PauseCircle,
  CalendarOff,
  Package,
  MapPinOff,
  Sparkles,
  ArrowUpRight,
  UtensilsCrossed,
  Banknote,
} from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { useAnimatedInteger } from '../composables/useAnimatedInteger.js'

const router = useRouter()
const loading = ref(false)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const analytics = ref(null)

function safeNum(v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

function fmtPct(raw) {
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(2)}%`
}

function fmtCount(raw) {
  if (loading.value) return '…'
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  return Number.isFinite(n) ? String(Math.trunc(n)) : '—'
}

/** 金额展示（保留两位小数） */
function fmtYuan(raw) {
  if (loading.value) return '…'
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  return Number.isFinite(n) ? n.toFixed(2) : '—'
}

/** SVG 圆环进度：pct 0–100 */
function ringDashOffset(pct) {
  const r = 34
  const c = 2 * Math.PI * r
  const p = Math.min(100, Math.max(0, Number(pct) || 0))
  return c * (1 - p / 100)
}

const totalAnimated = useAnimatedInteger(() => safeNum(analytics.value?.total), { duration: 640 })
const activeAnimated = useAnimatedInteger(() => safeNum(analytics.value?.active), { duration: 640 })
const expiredAnimated = useAnimatedInteger(() => safeNum(analytics.value?.expired), { duration: 640 })
const refundedAnimated = useAnimatedInteger(() => safeNum(analytics.value?.refunded), { duration: 640 })

const weeklyActiveAnimated = useAnimatedInteger(
  () => safeNum(analytics.value?.weekly?.active),
  { duration: 640 },
)
const monthlyActiveAnimated = useAnimatedInteger(
  () => safeNum(analytics.value?.monthly?.active),
  { duration: 640 },
)
const renewPendingAnimated = useAnimatedInteger(
  () => safeNum(analytics.value?.renew_pending?.count),
  { duration: 640 },
)
const unconsumedMealsAnimated = useAnimatedInteger(
  () => safeNum(analytics.value?.unconsumed_meals?.total),
  { duration: 640 },
)

const renewPendingThreshold = computed(() => {
  const t = Number(analytics.value?.renew_pending?.threshold)
  return Number.isFinite(t) && t >= 1 ? Math.trunc(t) : 2
})

/** 档案总览 KPI 卡片配置（含图标与色调） */
const kpiCards = computed(() => [
  {
    key: 'total',
    label: '总户数',
    hint: '周/月卡档案库',
    icon: Users,
    tone: 'neutral',
    value: loading.value ? '…' : String(totalAnimated.value),
    link: { path: '/users' },
  },
  {
    key: 'active',
    label: '生效中',
    hint: '剩余次数 > 0',
    icon: UserCheck,
    tone: 'active',
    value: loading.value ? '…' : String(activeAnimated.value),
    link: { path: '/users', query: { validity: 'active' } },
  },
  {
    key: 'expired',
    label: '已过期',
    hint: '次数用尽未退卡',
    icon: Clock,
    tone: 'muted',
    value: loading.value ? '…' : String(expiredAnimated.value),
    link: { path: '/users', query: { validity: 'expired' } },
  },
  {
    key: 'refunded',
    label: '已退款',
    hint: '已办理退卡退款',
    icon: RotateCcw,
    tone: 'danger',
    value: loading.value ? '…' : String(refundedAnimated.value),
    link: { path: '/users', query: { validity: 'refunded' } },
  },
  {
    key: 'active_rate',
    label: '活跃率',
    hint: '生效中 / 总户数',
    icon: Activity,
    tone: 'primary',
    value: loading.value ? '…' : fmtPct(analytics.value?.active_rate_percent),
    link: null,
  },
  {
    key: 'refund_rate',
    label: '退款率',
    hint: '已退款 / 总户数',
    icon: TrendingDown,
    tone: 'danger',
    value: loading.value ? '…' : fmtPct(analytics.value?.refund_rate_percent),
    link: null,
  },
])

const operationalRows = computed(() => {
  const a = analytics.value
  return [
    {
      key: 'renew_pending',
      label: '待续费',
      count: a?.renew_pending?.count,
      icon: Bell,
      tone: 'amber',
      link: { path: '/users', query: { segment: 'renew_pending' } },
      highlight: true,
    },
    {
      key: 'inactive',
      label: '未开卡',
      count: a?.inactive_count,
      icon: UserMinus,
      tone: 'slate',
      link: { path: '/users', query: { segment: 'inactive' } },
    },
    {
      key: 'paused',
      label: '暂停配送',
      count: a?.paused_delivery_count,
      icon: PauseCircle,
      tone: 'slate',
      link: { path: '/users', query: { segment: 'paused' } },
    },
    {
      key: 'leave',
      label: '请假中',
      count: a?.on_leave_count,
      icon: CalendarOff,
      tone: 'blue',
      link: { path: '/users', query: { segment: 'leave' } },
    },
    {
      key: 'pickup',
      label: '自提生效',
      count: a?.store_pickup_active_count,
      icon: Package,
      tone: 'green',
      link: { path: '/users', query: { validity: 'active' } },
    },
    {
      key: 'unassigned',
      label: '片区未分配',
      count: a?.unassigned_region_count,
      icon: MapPinOff,
      tone: 'rose',
      link: { path: '/users', query: { region: 'unassigned' } },
    },
  ]
})

async function loadAnalytics() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    analytics.value = await apiJson('/api/admin/users/analytics', {}, { auth: true })
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    analytics.value = null
    showToast(e instanceof Error ? e.message : '加载会员统计失败', 'error')
  } finally {
    loading.value = false
  }
}

function goMembers(link) {
  if (!link) return
  router.push(link)
}

function goRenewPendingMembers() {
  router.push({ path: '/users', query: { segment: 'renew_pending' } })
}

function goGrantCouponsForRenewPending() {
  router.push({
    path: '/marketing/member-coupons',
    query: { grant: '1', batch: 'renew_pending' },
  })
}

onMounted(() => {
  void loadAnalytics()
})

onActivated(() => {
  void loadAnalytics()
})
</script>

<template>
  <section class="member-stats-page tab-content animate-up page-content-shell">
    <header class="member-stats-head">
      <div class="member-stats-head__main">
        <div class="member-stats-head__title-row">
          <span class="member-stats-head__icon" aria-hidden="true">
            <PieChart :size="22" stroke-width="2.25" />
          </span>
          <h2 class="member-stats-head__title">会员运营分析</h2>
        </div>
        <p class="member-stats-head__sub">
          <Sparkles :size="14" stroke-width="2" class="member-stats-head__sub-icon" aria-hidden="true" />
          周/月卡档案库总览、套餐结构、续卡率与运营状态分布（与会员档案库统计口径一致）
        </p>
      </div>
      <button
        type="button"
        class="member-stats-refresh"
        :disabled="loading"
        aria-label="刷新会员统计"
        @click="loadAnalytics"
      >
        <RefreshCw :size="18" stroke-width="2" :class="{ 'member-stats-refresh__spin': loading }" />
        刷新
      </button>
    </header>

    <!-- 第一行：待续费 + 周/月卡占比 + 续卡率 -->
    <div class="member-stats-insight-row">
      <section class="member-stats-renew-hero member-stats-insight-card" aria-label="待续费会员">
        <div class="member-stats-renew-hero__deco" aria-hidden="true">
          <Bell :size="48" stroke-width="1.75" />
        </div>
        <div class="member-stats-renew-hero__main">
          <div class="member-stats-renew-hero__badge">
            <Bell :size="15" stroke-width="2.25" />
            <span>待续费提醒</span>
          </div>
          <div class="member-stats-renew-hero__metric">
            <strong class="member-stats-renew-hero__count">{{
              loading ? '…' : renewPendingAnimated
            }}</strong>
            <span class="member-stats-renew-hero__unit">户</span>
          </div>
          <p class="member-stats-renew-hero__desc">
            剩余 ≤ {{ renewPendingThreshold }} 次，占生效会员
            {{ loading ? '…' : fmtPct(analytics?.renew_pending?.share_of_active_percent) }}
          </p>
          <ul class="member-stats-renew-hero__breakdown">
            <li>
              <span class="member-stats-renew-hero__chip-icon member-stats-renew-hero__chip-icon--one" aria-hidden="true">1</span>
              剩余 1 次：<strong>{{ fmtCount(analytics?.renew_pending?.balance_1_count) }}</strong> 户
            </li>
            <li>
              <span class="member-stats-renew-hero__chip-icon" aria-hidden="true">{{ renewPendingThreshold }}</span>
              剩余 {{ renewPendingThreshold }} 次：<strong>{{
                fmtCount(analytics?.renew_pending?.balance_threshold_count)
              }}</strong>
              户
            </li>
          </ul>
        </div>
        <div class="member-stats-renew-hero__actions">
          <button type="button" class="member-stats-renew-btn member-stats-renew-btn--primary" @click="goRenewPendingMembers">
            <Users :size="16" stroke-width="2" />
            查看待续费会员
            <ChevronRight :size="16" stroke-width="2.25" class="member-stats-renew-btn__chev" />
          </button>
          <button
            type="button"
            class="member-stats-renew-btn member-stats-renew-btn--secondary"
            :disabled="loading || !(Number(analytics?.renew_pending?.count) > 0)"
            @click="goGrantCouponsForRenewPending"
          >
            <Ticket :size="16" stroke-width="2" />
            批量发券
          </button>
        </div>
      </section>

      <section class="member-stats-panel member-stats-insight-card" aria-label="生效会员套餐结构">
        <div class="member-stats-panel__head">
          <span class="member-stats-panel__head-icon member-stats-panel__head-icon--green" aria-hidden="true">
            <Users :size="18" stroke-width="2.25" />
          </span>
          <h3>生效 · 周/月卡占比</h3>
        </div>
        <div class="member-stats-ring-row">
          <figure class="member-stats-ring">
            <div class="member-stats-ring__tag member-stats-ring__tag--week">
              <CalendarDays :size="14" stroke-width="2.25" />
              周卡
            </div>
            <div class="member-stats-ring__wrap">
              <svg viewBox="0 0 80 80" class="member-stats-ring__svg" aria-hidden="true">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" stroke-width="8" />
                <circle
                  cx="40"
                  cy="40"
                  r="34"
                  fill="none"
                  stroke="#10b981"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="213.628"
                  :stroke-dashoffset="ringDashOffset(analytics?.active_weekly_share_percent)"
                  class="member-stats-ring__progress member-stats-ring__progress--week"
                />
              </svg>
              <span class="member-stats-ring__pct">{{
                loading ? '…' : fmtPct(analytics?.active_weekly_share_percent)
              }}</span>
            </div>
            <figcaption class="member-stats-ring__cap">
              <strong>周卡 {{ loading ? '…' : weeklyActiveAnimated }} 户</strong>
              <span>过期 {{ fmtCount(analytics?.weekly?.expired) }} 户</span>
            </figcaption>
          </figure>
          <figure class="member-stats-ring">
            <div class="member-stats-ring__tag member-stats-ring__tag--month">
              <CalendarRange :size="14" stroke-width="2.25" />
              月卡
            </div>
            <div class="member-stats-ring__wrap">
              <svg viewBox="0 0 80 80" class="member-stats-ring__svg" aria-hidden="true">
                <circle cx="40" cy="40" r="34" fill="none" stroke="#e2e8f0" stroke-width="8" />
                <circle
                  cx="40"
                  cy="40"
                  r="34"
                  fill="none"
                  stroke="#3b82f6"
                  stroke-width="8"
                  stroke-linecap="round"
                  :stroke-dasharray="213.628"
                  :stroke-dashoffset="ringDashOffset(analytics?.active_monthly_share_percent)"
                  class="member-stats-ring__progress member-stats-ring__progress--month"
                />
              </svg>
              <span class="member-stats-ring__pct">{{
                loading ? '…' : fmtPct(analytics?.active_monthly_share_percent)
              }}</span>
            </div>
            <figcaption class="member-stats-ring__cap">
              <strong>月卡 {{ loading ? '…' : monthlyActiveAnimated }} 户</strong>
              <span>过期 {{ fmtCount(analytics?.monthly?.expired) }} 户</span>
            </figcaption>
          </figure>
        </div>
      </section>

      <section class="member-stats-panel member-stats-insight-card" aria-label="续卡率">
        <div class="member-stats-panel__head">
          <span class="member-stats-panel__head-icon member-stats-panel__head-icon--primary" aria-hidden="true">
            <TrendingUp :size="18" stroke-width="2.25" />
          </span>
          <h3>续卡率</h3>
        </div>
        <p class="member-stats-panel__note">
          <Repeat :size="13" stroke-width="2" class="member-stats-panel__note-icon" aria-hidden="true" />
          含提前续卡；分母为曾有过入账会员。
        </p>
        <div class="member-stats-reorder-grid member-stats-reorder-grid--stack">
          <div class="member-stats-reorder member-stats-reorder--week">
            <span class="member-stats-reorder__icon member-stats-reorder__icon--week" aria-hidden="true">
              <CalendarDays :size="16" stroke-width="2.25" />
            </span>
            <span class="member-stats-reorder__label">周卡续卡率</span>
            <strong class="member-stats-reorder__pct">{{
              loading ? '…' : fmtPct(analytics?.weekly_reorder?.rate_percent)
            }}</strong>
            <span class="member-stats-reorder__detail">
              {{ fmtCount(analytics?.weekly_reorder?.reorder_members) }} /
              {{ fmtCount(analytics?.weekly_reorder?.base_members) }} 户
            </span>
          </div>
          <div class="member-stats-reorder member-stats-reorder--month">
            <span class="member-stats-reorder__icon member-stats-reorder__icon--month" aria-hidden="true">
              <CalendarRange :size="16" stroke-width="2.25" />
            </span>
            <span class="member-stats-reorder__label">月卡续卡率</span>
            <strong class="member-stats-reorder__pct">{{
              loading ? '…' : fmtPct(analytics?.monthly_reorder?.rate_percent)
            }}</strong>
            <span class="member-stats-reorder__detail">
              {{ fmtCount(analytics?.monthly_reorder?.reorder_members) }} /
              {{ fmtCount(analytics?.monthly_reorder?.base_members) }} 户
            </span>
          </div>
        </div>
      </section>
    </div>

    <section class="member-stats-kpi-grid" aria-label="会员档案总览">
      <article
        v-for="card in kpiCards"
        :key="card.key"
        class="member-stats-kpi"
        :class="[
          `member-stats-kpi--${card.tone}`,
          { 'member-stats-kpi--clickable': Boolean(card.link) },
        ]"
        :role="card.link ? 'button' : undefined"
        :tabindex="card.link ? 0 : undefined"
        @click="card.link && goMembers(card.link)"
        @keydown.enter="card.link && goMembers(card.link)"
      >
        <div class="member-stats-kpi__top">
          <span class="member-stats-kpi__icon" :class="`member-stats-kpi__icon--${card.tone}`" aria-hidden="true">
            <component :is="card.icon" :size="18" stroke-width="2.25" />
          </span>
          <ArrowUpRight
            v-if="card.link"
            :size="14"
            stroke-width="2.25"
            class="member-stats-kpi__jump"
            aria-hidden="true"
          />
        </div>
        <span class="member-stats-kpi__label">{{ card.label }}</span>
        <strong class="member-stats-kpi__value">{{ card.value }}</strong>
        <span class="member-stats-kpi__hint">{{ card.hint }}</span>
      </article>
    </section>

    <section class="member-stats-panel member-stats-panel--ops" aria-label="运营状态分布">
      <div class="member-stats-panel__head">
        <span class="member-stats-panel__head-icon member-stats-panel__head-icon--slate" aria-hidden="true">
          <Activity :size="18" stroke-width="2.25" />
        </span>
        <h3>运营状态分布</h3>
      </div>
      <div class="member-stats-ops-summary-row">
        <div class="member-stats-ops-summary" aria-label="未消费餐次汇总">
          <span class="member-stats-ops-summary__icon" aria-hidden="true">
            <UtensilsCrossed :size="18" stroke-width="2.25" />
          </span>
          <div class="member-stats-ops-summary__main">
            <span class="member-stats-ops-summary__label">未消费餐次总数</span>
            <strong class="member-stats-ops-summary__value">
              {{ loading ? '…' : `${unconsumedMealsAnimated} 次` }}
            </strong>
          </div>
          <p class="member-stats-ops-summary__hint">
            午餐 {{ fmtCount(analytics?.unconsumed_meals?.lunch_total) }} 次
            · 晚餐 {{ fmtCount(analytics?.unconsumed_meals?.dinner_total) }} 次
          </p>
        </div>
        <div class="member-stats-ops-summary member-stats-ops-summary--amount" aria-label="未消费金额汇总">
          <span class="member-stats-ops-summary__icon member-stats-ops-summary__icon--amount" aria-hidden="true">
            <Banknote :size="18" stroke-width="2.25" />
          </span>
          <div class="member-stats-ops-summary__main">
            <span class="member-stats-ops-summary__label">未消费金额</span>
            <strong class="member-stats-ops-summary__value">
              ¥ {{ fmtYuan(analytics?.unconsumed_meals?.total_amount_yuan) }}
            </strong>
          </div>
          <p class="member-stats-ops-summary__hint">
            午餐 ¥ {{ fmtYuan(analytics?.unconsumed_meals?.lunch_amount_yuan) }}
            · 晚餐 ¥ {{ fmtYuan(analytics?.unconsumed_meals?.dinner_amount_yuan) }}
            <span class="member-stats-ops-summary__hint-note">（实收×剩余/入账，档案库不含已退款）</span>
          </p>
        </div>
      </div>
      <ul class="member-stats-ops-list">
        <li v-for="row in operationalRows" :key="row.key">
          <button
            type="button"
            class="member-stats-ops-item"
            :class="{ 'member-stats-ops-item--highlight': row.highlight }"
            @click="goMembers(row.link)"
          >
            <span
              class="member-stats-ops-item__icon"
              :class="`member-stats-ops-item__icon--${row.tone}`"
              aria-hidden="true"
            >
              <component :is="row.icon" :size="16" stroke-width="2.25" />
            </span>
            <span class="member-stats-ops-item__label">{{ row.label }}</span>
            <strong class="member-stats-ops-item__count">{{ fmtCount(row.count) }}</strong>
            <ChevronRight :size="16" stroke-width="2.25" class="member-stats-ops-item__arrow" aria-hidden="true" />
          </button>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.member-stats-page {
  --ms-primary: #0d5c46;
  --ms-border: #eaedf1;
  --ms-muted: #64748b;
  --ms-text: #0f172a;
  --ms-active: #10b981;
  --ms-danger: #ef4444;
  display: flex;
  flex-direction: column;
  gap: 24px;
  font-family: var(--okfood-font-sans);
  padding-bottom: 1.5rem;
}

.member-stats-head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem 1.5rem;
  padding: 0 1rem;
}

.member-stats-insight-row {
  display: grid;
  grid-template-columns: 1.05fr 1fr 0.95fr;
  gap: 16px;
  padding: 0 1rem;
  align-items: stretch;
}

@media (max-width: 1180px) {
  .member-stats-insight-row {
    grid-template-columns: 1fr;
  }
}

.member-stats-insight-card {
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.member-stats-insight-card.member-stats-panel {
  margin: 0;
}

.member-stats-renew-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 1rem;
  margin: 0;
  padding: 1.35rem 1.5rem;
  border-radius: 24px;
  border: 1px solid #fde68a;
  background: linear-gradient(135deg, #fffbeb 0%, #fff 55%);
  box-shadow: 0 8px 28px rgba(245, 158, 11, 0.08);
  overflow: hidden;
  min-height: 100%;
}

.member-stats-renew-hero__deco {
  position: absolute;
  right: 0.75rem;
  top: 0.75rem;
  transform: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: rgba(254, 243, 199, 0.55);
  color: rgba(245, 158, 11, 0.28);
  pointer-events: none;
}

.member-stats-renew-hero__main {
  position: relative;
  z-index: 1;
  flex: 1 1 auto;
  min-width: 0;
  padding-right: 4.5rem;
}

@media (max-width: 1180px) {
  .member-stats-renew-hero__main {
    padding-right: 0;
  }
}

.member-stats-renew-hero__badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.65rem;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
  font-weight: 800;
  margin-bottom: 0.65rem;
}

.member-stats-renew-hero__metric {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
  margin-bottom: 0.35rem;
}

.member-stats-renew-hero__count {
  font-family: var(--okfood-font-number);
  font-size: 2.35rem;
  font-weight: 900;
  line-height: 1;
  color: #b45309;
  font-variant-numeric: tabular-nums;
}

.member-stats-renew-hero__unit {
  font-size: 1rem;
  font-weight: 800;
  color: #92400e;
}

.member-stats-renew-hero__desc {
  margin: 0 0 0.65rem;
  font-size: 12px;
  color: var(--ms-muted);
  line-height: 1.5;
  max-width: none;
}

.member-stats-renew-hero__breakdown {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
  font-size: 12px;
  color: var(--ms-muted);
}

.member-stats-renew-hero__breakdown li {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.member-stats-renew-hero__chip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 1.35rem;
  height: 1.35rem;
  padding: 0 0.25rem;
  border-radius: 8px;
  background: #fef3c7;
  color: #b45309;
  font-family: var(--okfood-font-number);
  font-size: 11px;
  font-weight: 900;
  line-height: 1;
}

.member-stats-renew-hero__chip-icon--one {
  background: #ffedd5;
  color: #c2410c;
}

.member-stats-renew-hero__breakdown strong {
  font-family: var(--okfood-font-number);
  color: #b45309;
  font-weight: 900;
}

.member-stats-renew-hero__actions {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
  width: 100%;
}

.member-stats-renew-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  width: 100%;
  min-width: 0;
  padding: 0.65rem 1.125rem;
  border-radius: 14px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  border: 1px solid transparent;
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.member-stats-panel.member-stats-insight-card {
  padding: 1.35rem 1.5rem;
  display: flex;
  flex-direction: column;
}

.member-stats-panel.member-stats-insight-card .member-stats-panel__head {
  margin-bottom: 1rem;
}

.member-stats-panel.member-stats-insight-card .member-stats-ring-row {
  flex: 1 1 auto;
  align-items: center;
}

.member-stats-panel.member-stats-insight-card .member-stats-panel__note {
  margin-bottom: 0.75rem;
}

.member-stats-reorder-grid--stack {
  grid-template-columns: 1fr;
  flex: 1 1 auto;
  align-content: start;
}

.member-stats-renew-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.member-stats-renew-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.member-stats-renew-btn--primary {
  background: #f59e0b;
  color: #fff;
  border-color: #d97706;
}

.member-stats-renew-btn--secondary {
  background: #fff;
  color: #b45309;
  border-color: #fde68a;
}

.member-stats-renew-btn__chev {
  opacity: 0.85;
  margin-left: auto;
}

.member-stats-head__title-row {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.35rem;
}

.member-stats-head__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: rgba(13, 92, 70, 0.1);
  color: var(--ms-primary);
  flex-shrink: 0;
}

.member-stats-head__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 800;
  color: var(--ms-text);
  letter-spacing: -0.02em;
}

.member-stats-head__sub {
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
  margin: 0;
  font-size: 13px;
  color: var(--ms-muted);
  line-height: 1.5;
  max-width: 42rem;
}

.member-stats-head__sub-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
  color: #94a3b8;
}

.member-stats-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 1rem;
  border-radius: 12px;
  border: 1px solid var(--ms-border);
  background: #fff;
  color: var(--ms-text);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s ease;
}

.member-stats-refresh:hover:not(:disabled) {
  background: #f8fafc;
}

.member-stats-refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.member-stats-refresh__spin {
  animation: member-stats-spin 0.85s linear infinite;
}

@keyframes member-stats-spin {
  to {
    transform: rotate(360deg);
  }
}

.member-stats-kpi-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
  padding: 0 1rem;
}

@media (max-width: 1200px) {
  .member-stats-kpi-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 640px) {
  .member-stats-kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.member-stats-kpi {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1.125rem 1.25rem;
  border-radius: 20px;
  border: 1px solid var(--ms-border);
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.03);
}

.member-stats-kpi__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.15rem;
}

.member-stats-kpi__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  flex-shrink: 0;
}

.member-stats-kpi__icon--neutral {
  background: #f1f5f9;
  color: #475569;
}

.member-stats-kpi__icon--active {
  background: #ecfdf5;
  color: #059669;
}

.member-stats-kpi__icon--muted {
  background: #f8fafc;
  color: #94a3b8;
}

.member-stats-kpi__icon--danger {
  background: #fef2f2;
  color: #ef4444;
}

.member-stats-kpi__icon--primary {
  background: rgba(13, 92, 70, 0.1);
  color: var(--ms-primary);
}

.member-stats-kpi__jump {
  color: #cbd5e1;
  flex-shrink: 0;
  transition: color 0.2s ease, transform 0.2s ease;
}

.member-stats-kpi--clickable:hover .member-stats-kpi__jump {
  color: var(--ms-primary);
  transform: translate(1px, -1px);
}

.member-stats-kpi--clickable {
  cursor: pointer;
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.member-stats-kpi--clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
}

.member-stats-kpi__label {
  font-size: 12px;
  font-weight: 800;
  color: var(--ms-muted);
  letter-spacing: 0.04em;
}

.member-stats-kpi__value {
  font-family: var(--okfood-font-number);
  font-size: 1.75rem;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: var(--ms-text);
}

.member-stats-kpi--active .member-stats-kpi__value {
  color: var(--ms-active);
}

.member-stats-kpi--primary .member-stats-kpi__value {
  color: var(--ms-primary);
}

.member-stats-kpi--danger .member-stats-kpi__value {
  color: var(--ms-danger);
}

.member-stats-kpi--muted .member-stats-kpi__value {
  color: #94a3b8;
}

.member-stats-kpi__hint {
  font-size: 11px;
  color: #94a3b8;
}

.member-stats-panel {
  padding: 1.5rem 1.75rem;
  border-radius: 24px;
  border: 1px solid var(--ms-border);
  background: #fff;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
}

.member-stats-panel__head {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 1.25rem;
}

.member-stats-panel__head-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  flex-shrink: 0;
}

.member-stats-panel__head-icon--green {
  background: #ecfdf5;
  color: #059669;
}

.member-stats-panel__head-icon--primary {
  background: rgba(13, 92, 70, 0.1);
  color: var(--ms-primary);
}

.member-stats-panel__head-icon--slate {
  background: #f1f5f9;
  color: #64748b;
}

.member-stats-panel__head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  color: var(--ms-text);
}

.member-stats-panel__note {
  display: flex;
  align-items: flex-start;
  gap: 0.35rem;
  margin: -0.5rem 0 1rem;
  font-size: 12px;
  color: var(--ms-muted);
  line-height: 1.5;
}

.member-stats-panel__note-icon {
  flex-shrink: 0;
  margin-top: 0.1rem;
  color: #94a3b8;
}

.member-stats-ring-row {
  display: flex;
  justify-content: space-around;
  gap: 1.5rem;
  padding: 0.75rem 0.5rem;
  background: #fafbfc;
  border: 1px solid var(--ms-border);
  border-radius: 20px;
}

.member-stats-ring {
  margin: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.member-stats-ring__tag {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.03em;
}

.member-stats-ring__tag--week {
  background: #ecfdf5;
  color: #059669;
}

.member-stats-ring__tag--month {
  background: #eff6ff;
  color: #2563eb;
}

.member-stats-ring__wrap {
  position: relative;
  width: 96px;
  height: 96px;
}

.member-stats-ring__svg {
  width: 96px;
  height: 96px;
  transform: rotate(-90deg);
}

.member-stats-ring__progress {
  transition: stroke-dashoffset 0.55s ease;
}

.member-stats-ring__progress--week {
  filter: drop-shadow(0 2px 4px rgba(16, 185, 129, 0.25));
}

.member-stats-ring__progress--month {
  filter: drop-shadow(0 2px 4px rgba(59, 130, 246, 0.25));
}

.member-stats-ring__pct {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--okfood-font-number);
  font-size: 16px;
  font-weight: 900;
  color: var(--ms-text);
  font-variant-numeric: tabular-nums;
}

.member-stats-ring__cap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  text-align: center;
}

.member-stats-ring__cap strong {
  font-size: 13px;
  font-weight: 800;
  color: var(--ms-text);
}

.member-stats-ring__cap span {
  font-size: 11px;
  color: var(--ms-muted);
}

.member-stats-reorder-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.member-stats-reorder {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 1.125rem 1.25rem 1.125rem 3.25rem;
  border-radius: 16px;
  background: #f8fafc;
  border: 1px solid var(--ms-border);
}

.member-stats-reorder--week {
  background: linear-gradient(135deg, #f0fdf4 0%, #f8fafc 100%);
}

.member-stats-reorder--month {
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
}

.member-stats-reorder__icon {
  position: absolute;
  left: 1rem;
  top: 1.125rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
}

.member-stats-reorder__icon--week {
  background: #dcfce7;
  color: #059669;
}

.member-stats-reorder__icon--month {
  background: #dbeafe;
  color: #2563eb;
}

.member-stats-reorder__label {
  font-size: 12px;
  font-weight: 800;
  color: var(--ms-muted);
}

.member-stats-reorder__pct {
  font-family: var(--okfood-font-number);
  font-size: 1.75rem;
  font-weight: 900;
  color: var(--ms-primary);
  font-variant-numeric: tabular-nums;
}

.member-stats-reorder__detail {
  font-size: 12px;
  color: var(--ms-muted);
  font-variant-numeric: tabular-nums;
}

.member-stats-panel--ops {
  margin: 0 1rem;
}

.member-stats-ops-summary-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 1rem;
}

@media (max-width: 960px) {
  .member-stats-ops-summary-row {
    grid-template-columns: 1fr;
  }
}

.member-stats-ops-summary {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  gap: 0.35rem 0.85rem;
  align-items: center;
  padding: 1rem 1.125rem;
  border-radius: 16px;
  border: 1px solid #bbf7d0;
  background: linear-gradient(135deg, #f0fdf4 0%, #fafbfc 100%);
}

.member-stats-ops-summary--amount {
  border-color: #bfdbfe;
  background: linear-gradient(135deg, #eff6ff 0%, #fafbfc 100%);
}

.member-stats-ops-summary__icon {
  grid-row: 1 / span 2;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: #dcfce7;
  color: #059669;
}

.member-stats-ops-summary__icon--amount {
  background: #dbeafe;
  color: #2563eb;
}

.member-stats-ops-summary__main {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.5rem 1rem;
}

.member-stats-ops-summary__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--ms-text);
}

.member-stats-ops-summary__value {
  font-family: var(--okfood-font-number);
  font-size: 1.5rem;
  font-weight: 900;
  color: var(--ms-primary);
  font-variant-numeric: tabular-nums;
}

.member-stats-ops-summary__hint {
  grid-column: 2;
  margin: 0;
  font-size: 12px;
  color: var(--ms-muted);
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}

.member-stats-ops-summary__hint-note {
  color: #94a3b8;
}

.member-stats-ops-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

@media (max-width: 1200px) {
  .member-stats-ops-list {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 960px) {
  .member-stats-ops-list {
    grid-template-columns: repeat(2, 1fr);
  }
}

.member-stats-ops-item {
  width: 100%;
  display: grid;
  grid-template-columns: auto 1fr auto auto;
  align-items: center;
  gap: 0.65rem;
  padding: 0.875rem 1rem;
  border-radius: 16px;
  border: 1px solid var(--ms-border);
  background: #fafbfc;
  cursor: pointer;
  text-align: left;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    transform 0.2s ease;
}

.member-stats-ops-item:hover {
  background: #f1f5f9;
  transform: translateY(-1px);
}

.member-stats-ops-item__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  flex-shrink: 0;
}

.member-stats-ops-item__icon--amber {
  background: #fef3c7;
  color: #d97706;
}

.member-stats-ops-item__icon--slate {
  background: #f1f5f9;
  color: #64748b;
}

.member-stats-ops-item__icon--blue {
  background: #dbeafe;
  color: #2563eb;
}

.member-stats-ops-item__icon--green {
  background: #dcfce7;
  color: #059669;
}

.member-stats-ops-item__icon--rose {
  background: #ffe4e6;
  color: #e11d48;
}

.member-stats-ops-item--highlight {
  border-color: #fde68a;
  background: #fffbeb;
}

.member-stats-ops-item--highlight:hover {
  background: #fef3c7;
}

.member-stats-ops-item__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--ms-text);
}

.member-stats-ops-item__count {
  font-family: var(--okfood-font-number);
  font-size: 1.25rem;
  font-weight: 900;
  color: var(--ms-primary);
  font-variant-numeric: tabular-nums;
}

.member-stats-ops-item__arrow {
  color: #94a3b8;
  flex-shrink: 0;
  transition: color 0.2s ease, transform 0.2s ease;
}

.member-stats-ops-item:hover .member-stats-ops-item__arrow {
  color: var(--ms-primary);
  transform: translateX(2px);
}
</style>
