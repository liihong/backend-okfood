<script setup>
defineOptions({ name: 'MemberStatsView' })
import { computed, onActivated, onMounted, provide, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Bell,
  ChevronRight,
  UserMinus,
  ClipboardList,
  PauseCircle,
  CalendarOff,
  Package,
  MapPinOff,
  ArrowUpRight,
  UtensilsCrossed,
} from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import StatRollNumber from '../components/StatRollNumber.vue'

const router = useRouter()
const loading = ref(false)
/** 每次统计加载成功后 +1，页面上的数字重新滚动 */
const rollToken = ref(0)
provide('memberStatsRollToken', rollToken)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const analytics = ref(null)

/** 统计数字；没有值时交给滚动组件显示占位 */
function metric(raw) {
  if (raw == null || raw === '') return null
  const n = Number(raw)
  return Number.isFinite(n) ? n : null
}

function fmtPct(raw) {
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  if (!Number.isFinite(n)) return '—'
  return `${n.toFixed(2)}%`
}

/** 占比条宽度，限制在 0–100 */
function barWidth(raw) {
  const n = Number(raw)
  if (!Number.isFinite(n)) return '0%'
  return `${Math.min(100, Math.max(0, n))}%`
}

const renewPendingThreshold = computed(() => {
  const t = Number(analytics.value?.renew_pending?.threshold)
  return Number.isFinite(t) && t >= 1 ? Math.trunc(t) : 2
})

/** 档案总览：一条六格，颜色只落在生效与退款 */
const kpiCards = computed(() => [
  {
    key: 'total',
    label: '总户数',
    hint: '周/月卡档案库',
    tone: 'neutral',
    amount: metric(analytics.value?.total),
    digits: 0,
    suffix: '',
    link: { path: '/users' },
  },
  {
    key: 'active',
    label: '生效中',
    hint: '剩余次数 > 0',
    tone: 'ok',
    amount: metric(analytics.value?.active),
    digits: 0,
    suffix: '',
    link: { path: '/users', query: { validity: 'active' } },
  },
  {
    key: 'expired',
    label: '已过期',
    hint: '次数用尽未退卡',
    tone: 'neutral',
    amount: metric(analytics.value?.expired),
    digits: 0,
    suffix: '',
    link: { path: '/users', query: { validity: 'expired' } },
  },
  {
    key: 'refunded',
    label: '已退款',
    hint: '已办理退卡退款',
    tone: 'rose',
    amount: metric(analytics.value?.refunded),
    digits: 0,
    suffix: '',
    link: { path: '/users', query: { validity: 'refunded' } },
  },
  {
    key: 'active_rate',
    label: '活跃率',
    hint: '生效中 / 总户数',
    tone: 'neutral',
    amount: metric(analytics.value?.active_rate_percent),
    digits: 2,
    suffix: '%',
    link: null,
  },
  {
    key: 'refund_rate',
    label: '退款率',
    hint: '已退款 / 总户数',
    tone: 'rose',
    amount: metric(analytics.value?.refund_rate_percent),
    digits: 2,
    suffix: '%',
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
      key: 'awaiting_setup',
      label: '待完善',
      count: a?.awaiting_setup_count,
      icon: ClipboardList,
      tone: 'amber',
      link: { path: '/users', query: { segment: 'awaiting_setup' } },
      highlight: true,
    },
    {
      key: 'paused',
      label: '已暂停',
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
    rollToken.value += 1
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
      <div>
        <p class="member-stats-crumb">数据统计 / <b>会员统计</b></p>
        <h2 class="member-stats-head__title">会员运营分析</h2>
        <p class="member-stats-head__sub">
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
        <RefreshCw :size="15" stroke-width="2" :class="{ 'member-stats-refresh__spin': loading }" />
        刷新
      </button>
    </header>

    <!-- 待续费是唯一强调卡；占比与续卡率并进一张白卡 -->
    <div class="member-stats-top">
      <section class="member-stats-hero" aria-label="待续费会员">
        <div class="member-stats-hero__glow" aria-hidden="true"></div>
        <div class="member-stats-hero__body">
          <span class="member-stats-badge">
            <Bell :size="14" stroke-width="2.2" />
            待续费提醒
          </span>
          <div class="member-stats-hero__metric">
            <strong><StatRollNumber :value="metric(analytics?.renew_pending?.count)" /></strong>
            <span class="member-stats-hero__unit">户</span>
          </div>
          <p class="member-stats-hero__desc">
            剩余 ≤ {{ renewPendingThreshold }} 次，占生效会员
            <StatRollNumber
              :value="metric(analytics?.renew_pending?.share_of_active_percent)"
              :digits="2"
              suffix="%"
            />
          </p>
          <ul class="member-stats-hero__splits">
            <li>
              剩余 1 次
              <b><StatRollNumber :value="metric(analytics?.renew_pending?.balance_1_count)" /> 户</b>
            </li>
            <li>
              剩余 {{ renewPendingThreshold }} 次
              <b><StatRollNumber :value="metric(analytics?.renew_pending?.balance_threshold_count)" /> 户</b>
            </li>
          </ul>
        </div>
        <div class="member-stats-hero__actions">
          <button type="button" class="member-stats-btn member-stats-btn--primary" @click="goRenewPendingMembers">
            查看待续费会员
            <ChevronRight :size="15" stroke-width="2.4" />
          </button>
          <button
            type="button"
            class="member-stats-btn member-stats-btn--ghost"
            :disabled="loading || !(Number(analytics?.renew_pending?.count) > 0)"
            @click="goGrantCouponsForRenewPending"
          >
            批量发券
          </button>
        </div>
      </section>

      <article class="member-stats-panel member-stats-structure" aria-label="生效结构与续卡率">
        <div class="member-stats-structure__col">
          <p class="member-stats-kicker">生效中 <StatRollNumber :value="metric(analytics?.active)" /> 户</p>
          <h3>周 / 月卡占比</h3>
          <div class="member-stats-mix">
            <div
              class="member-stats-mix__bar"
              role="img"
              :aria-label="`周卡 ${fmtPct(analytics?.active_weekly_share_percent)}，月卡 ${fmtPct(analytics?.active_monthly_share_percent)}`"
            >
              <span class="member-stats-mix__week" :style="{ width: barWidth(analytics?.active_weekly_share_percent) }"></span>
              <span class="member-stats-mix__month" :style="{ width: barWidth(analytics?.active_monthly_share_percent) }"></span>
            </div>
            <div class="member-stats-mix__cols">
              <p>
                <span class="member-stats-mix__label"><i class="member-stats-dot member-stats-dot--week"></i>周卡</span>
                <strong><StatRollNumber :value="metric(analytics?.active_weekly_share_percent)" :digits="2" suffix="%" /></strong>
                <em>
                  <StatRollNumber :value="metric(analytics?.weekly?.active)" /> 户
                  · 过期 <StatRollNumber :value="metric(analytics?.weekly?.expired)" /> 户
                </em>
              </p>
              <p>
                <span class="member-stats-mix__label"><i class="member-stats-dot member-stats-dot--month"></i>月卡</span>
                <strong><StatRollNumber :value="metric(analytics?.active_monthly_share_percent)" :digits="2" suffix="%" /></strong>
                <em>
                  <StatRollNumber :value="metric(analytics?.monthly?.active)" /> 户
                  · 过期 <StatRollNumber :value="metric(analytics?.monthly?.expired)" /> 户
                </em>
              </p>
            </div>
          </div>
        </div>
        <div class="member-stats-structure__col">
          <p class="member-stats-kicker">曾有过入账会员</p>
          <h3>续卡率</h3>
          <p class="member-stats-note">含提前续卡。分母为曾有过入账会员。</p>
          <div class="member-stats-reorder">
            <div class="member-stats-reorder__row">
              <span>周卡</span>
              <strong><StatRollNumber :value="metric(analytics?.weekly_reorder?.rate_percent)" :digits="2" suffix="%" /></strong>
              <em>
                <StatRollNumber :value="metric(analytics?.weekly_reorder?.reorder_members)" />
                /
                <StatRollNumber :value="metric(analytics?.weekly_reorder?.base_members)" />
                户
              </em>
              <div class="member-stats-track" aria-hidden="true">
                <i :style="{ width: barWidth(analytics?.weekly_reorder?.rate_percent) }"></i>
              </div>
            </div>
            <div class="member-stats-reorder__row">
              <span>月卡</span>
              <strong><StatRollNumber :value="metric(analytics?.monthly_reorder?.rate_percent)" :digits="2" suffix="%" /></strong>
              <em>
                <StatRollNumber :value="metric(analytics?.monthly_reorder?.reorder_members)" />
                /
                <StatRollNumber :value="metric(analytics?.monthly_reorder?.base_members)" />
                户
              </em>
              <div class="member-stats-track" aria-hidden="true">
                <i :style="{ width: barWidth(analytics?.monthly_reorder?.rate_percent) }"></i>
              </div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <section class="member-stats-panel member-stats-archive" aria-label="会员档案总览">
      <component
        :is="card.link ? 'button' : 'div'"
        v-for="card in kpiCards"
        :key="card.key"
        class="member-stats-kpi"
        :class="[`member-stats-kpi--${card.tone}`, { 'member-stats-kpi--link': Boolean(card.link) }]"
        :type="card.link ? 'button' : undefined"
        @click="card.link && goMembers(card.link)"
      >
        <span class="member-stats-kpi__label">
          {{ card.label }}
          <ArrowUpRight v-if="card.link" :size="13" stroke-width="2.2" aria-hidden="true" />
        </span>
        <strong>
          <StatRollNumber :value="card.amount" :digits="card.digits" :suffix="card.suffix" />
        </strong>
        <small>{{ card.hint }}</small>
      </component>
    </section>

    <section class="member-stats-panel member-stats-ops" aria-label="运营状态分布">
      <div class="member-stats-ops__head">
        <div class="member-stats-ops__title">
          <div class="member-stats-ops__name">
            <span class="member-stats-meals__icon" aria-hidden="true">
              <UtensilsCrossed :size="15" stroke-width="2" />
            </span>
            <h3>运营状态分布</h3>
          </div>
          <div class="member-stats-meals" aria-label="未消费餐次汇总">
            <span class="member-stats-meals__item">
              <span class="member-stats-meals__label">未消费餐次</span>
              <strong class="member-stats-meals__figure">
                <StatRollNumber :value="metric(analytics?.unconsumed_meals?.total)" />
                <small>次</small>
              </strong>
            </span>
            <span class="member-stats-meals__item">
              <span class="member-stats-meals__label">午餐</span>
              <strong class="member-stats-meals__figure member-stats-meals__figure--lunch">
                <StatRollNumber :value="metric(analytics?.unconsumed_meals?.lunch_total)" />
                <small>次</small>
              </strong>
            </span>
            <span class="member-stats-meals__item">
              <span class="member-stats-meals__label">晚餐</span>
              <strong class="member-stats-meals__figure member-stats-meals__figure--dinner">
                <StatRollNumber :value="metric(analytics?.unconsumed_meals?.dinner_total)" />
                <small>次</small>
              </strong>
            </span>
          </div>
        </div>
      </div>
      <div class="member-stats-ops__grid">
        <button
          v-for="row in operationalRows"
          :key="row.key"
          type="button"
          class="member-stats-op"
          :class="{
            'member-stats-op--hot': row.highlight,
            'member-stats-op--rose': row.tone === 'rose',
          }"
          @click="goMembers(row.link)"
        >
          <span class="member-stats-op__icon" aria-hidden="true">
            <component :is="row.icon" :size="15" stroke-width="2" />
          </span>
          <span class="member-stats-op__name">{{ row.label }}</span>
          <strong class="member-stats-op__count"><StatRollNumber :value="metric(row.count)" /></strong>
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.member-stats-page {
  --ms-ink: #1d1f21;
  --ms-muted: #5c6670;
  --ms-faint: #8b949e;
  --ms-line: rgba(15, 23, 42, 0.06);
  --ms-ok: #1f8a5b;
  --ms-rose: #c45c66;
  --ms-month: #7e93a8;
  display: flex;
  flex-direction: column;
  gap: 16px;
  /* 与讨论稿同宽。宽屏主区里若拉满，占比条、六格和状态格会被扯开 */
  width: min(1200px, 100%);
  max-width: 1200px;
  align-self: flex-start;
  padding-bottom: 1.5rem;
  color: var(--ms-ink);
  font-family: var(--okfood-font-sans);
}

.member-stats-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 2px 0;
}

.member-stats-crumb {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--ms-faint);
}

.member-stats-crumb b {
  color: var(--el-color-primary-dark-2);
  font-weight: 700;
}

.member-stats-head__title {
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  letter-spacing: -0.03em;
  font-weight: 700;
}

.member-stats-head__sub {
  margin: 6px 0 0;
  max-width: 40rem;
  color: var(--ms-muted);
  font-size: 13px;
  line-height: 1.5;
}

.member-stats-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid var(--ms-line);
  background: rgba(255, 255, 255, 0.9);
  color: var(--ms-ink);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.member-stats-refresh:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--el-color-primary) 45%, #fff);
  color: var(--el-color-primary-dark-2);
}

.member-stats-refresh:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.member-stats-refresh__spin {
  animation: member-stats-spin 0.8s linear infinite;
}

@keyframes member-stats-spin {
  to { transform: rotate(360deg); }
}

.member-stats-top {
  display: grid;
  grid-template-columns: minmax(280px, 340px) minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
}

.member-stats-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 22px 18px;
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.62), color-mix(in srgb, var(--el-color-primary-light-9) 88%, #fff));
  border: 1px solid rgba(255, 255, 255, 0.85);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 18px 40px color-mix(in srgb, var(--el-color-primary) 16%, transparent);
}

.member-stats-hero__glow {
  position: absolute;
  width: 180px;
  height: 180px;
  right: -50px;
  top: -60px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--el-color-primary) 28%, transparent);
  filter: blur(28px);
  pointer-events: none;
}

.member-stats-hero__body,
.member-stats-hero__actions {
  position: relative;
  z-index: 1;
}

.member-stats-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 10px 0 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-primary) 16%, #fff);
  color: var(--el-color-primary-dark-2);
  font-size: 12px;
  font-weight: 700;
}

.member-stats-hero__metric {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-top: 14px;
}

.member-stats-hero__metric strong {
  font-size: 80px;
  line-height: 1;
  letter-spacing: -0.045em;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.member-stats-hero__unit {
  font-size: 14px;
  color: var(--ms-muted);
  font-weight: 600;
}

.member-stats-hero__desc {
  margin: 10px 0 0;
  color: var(--ms-muted);
  font-size: 13px;
}

.member-stats-hero__splits {
  display: flex;
  gap: 8px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.member-stats-hero__splits li {
  flex: 1;
  padding: 8px 10px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  color: var(--ms-muted);
}

.member-stats-hero__splits b {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 2px;
  color: var(--ms-ink);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.member-stats-hero__actions {
  display: flex;
  gap: 8px;
}

.member-stats-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.member-stats-btn--primary {
  flex: 1;
  border: 0;
  color: #fff;
  background: var(--el-color-primary);
  box-shadow: 0 8px 18px color-mix(in srgb, var(--el-color-primary) 32%, transparent);
}

.member-stats-btn--primary:hover {
  background: var(--el-color-primary-dark-2);
}

.member-stats-btn--ghost {
  border: 1px solid var(--ms-line);
  background: rgba(255, 255, 255, 0.86);
  color: var(--ms-ink);
}

.member-stats-btn--ghost:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--el-color-primary) 40%, #fff);
}

.member-stats-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.member-stats-panel {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
}

.member-stats-structure {
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  min-width: 0;
}

.member-stats-structure__col {
  min-width: 0;
  padding: 20px 22px 18px;
}

.member-stats-structure__col + .member-stats-structure__col {
  border-left: 1px solid var(--ms-line);
}

.member-stats-kicker {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: var(--ms-faint);
}

.member-stats-structure h3,
.member-stats-ops h3 {
  margin: 4px 0 0;
  font-size: 16px;
  letter-spacing: -0.02em;
  font-weight: 700;
}

.member-stats-note {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--ms-faint);
  line-height: 1.45;
}

.member-stats-mix {
  margin-top: 18px;
}

.member-stats-mix__bar {
  display: flex;
  height: 10px;
  border-radius: 999px;
  overflow: hidden;
  background: #eef2f4;
}

.member-stats-mix__week,
.member-stats-mix__month {
  transition: width 0.78s cubic-bezier(0.16, 1, 0.3, 1);
}

.member-stats-mix__week {
  background: var(--el-color-primary);
}

.member-stats-mix__month {
  background: var(--ms-month);
}

.member-stats-mix__cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 14px;
}

.member-stats-mix__cols p {
  margin: 0;
}

.member-stats-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  margin-right: 6px;
  border-radius: 50%;
  vertical-align: 1px;
}

.member-stats-dot--week { background: var(--el-color-primary); }
.member-stats-dot--month { background: var(--ms-month); }

.member-stats-mix__label {
  font-size: 12px;
  color: var(--ms-muted);
  font-weight: 700;
}

.member-stats-mix__cols strong {
  display: block;
  margin-top: 4px;
  font-size: 26px;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.member-stats-mix__cols em,
.member-stats-reorder__row em {
  display: block;
  margin-top: 2px;
  font-style: normal;
  font-size: 12px;
  color: var(--ms-faint);
}

.member-stats-reorder {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.member-stats-reorder__row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 2px 12px;
  align-items: baseline;
}

.member-stats-reorder__row > span {
  font-size: 13px;
  color: var(--ms-muted);
  font-weight: 650;
}

.member-stats-reorder__row > strong {
  font-size: 22px;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.member-stats-reorder__row em {
  grid-column: 1 / -1;
}

.member-stats-track {
  grid-column: 1 / -1;
  height: 6px;
  margin-top: 6px;
  border-radius: 999px;
  background: #e4eaee;
  overflow: hidden;
}

.member-stats-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--el-color-primary);
  transition: width 0.78s cubic-bezier(0.16, 1, 0.3, 1);
}

.member-stats-archive {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
}

.member-stats-kpi {
  padding: 16px 16px 14px;
  text-align: left;
  background: transparent;
  border: 0;
  border-right: 1px solid var(--ms-line);
  color: inherit;
}

.member-stats-kpi:last-child {
  border-right: 0;
}

.member-stats-kpi--link {
  cursor: pointer;
}

.member-stats-kpi--link:hover {
  background: color-mix(in srgb, var(--el-color-primary) 7%, #fff);
}

.member-stats-kpi__label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: var(--ms-muted);
  font-weight: 700;
}

.member-stats-kpi__label svg {
  color: var(--ms-faint);
}

.member-stats-kpi strong {
  display: block;
  margin-top: 8px;
  font-size: 28px;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.member-stats-kpi--ok strong { color: var(--ms-ok); }
.member-stats-kpi--rose strong { color: var(--ms-rose); }

.member-stats-kpi small {
  display: block;
  margin-top: 4px;
  color: var(--ms-faint);
  font-size: 12px;
}

.member-stats-ops {
  padding: 18px 18px 14px;
}

.member-stats-ops__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 4px 14px;
}

.member-stats-ops__title {
  display: flex;
  align-items: center;
  gap: 18px;
  min-width: 0;
}

.member-stats-ops__title h3 {
  margin: 0;
}

.member-stats-ops__name {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: none;
}

.member-stats-meals {
  display: flex;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 22px;
  min-width: 0;
  color: var(--ms-muted);
  text-align: left;
}

.member-stats-meals__icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  margin-bottom: 1px;
  flex: none;
  border-radius: 9px;
  background: #f6f8f9;
  color: var(--ms-muted);
}

.member-stats-meals__item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.member-stats-meals__label {
  font-size: 12px;
  line-height: 1;
  font-weight: 700;
  color: var(--ms-muted);
}

.member-stats-meals__figure {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-size: 22px;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  color: var(--el-color-primary-dark-2);
}

.member-stats-meals__figure--lunch {
  color: var(--ms-ok);
}

.member-stats-meals__figure--dinner {
  color: #6a78c4;
}

.member-stats-meals__figure small {
  font-size: 12px;
  font-weight: 700;
  color: var(--ms-muted);
}

.member-stats-ops__grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 8px;
}

.member-stats-op {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  min-height: 108px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid transparent;
  background: #f6f8f9;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.member-stats-op:hover {
  background: #fff;
  border-color: var(--ms-line);
  box-shadow: 0 8px 20px rgba(25, 45, 55, 0.05);
}

.member-stats-op--hot {
  background: color-mix(in srgb, var(--el-color-primary) 12%, #fff);
}

.member-stats-op--hot:hover {
  border-color: color-mix(in srgb, var(--el-color-primary) 35%, #fff);
}

.member-stats-op__icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 9px;
  background: #fff;
  color: var(--ms-muted);
}

.member-stats-op--hot .member-stats-op__icon {
  color: var(--el-color-primary-dark-2);
}

.member-stats-op--rose .member-stats-op__icon,
.member-stats-op--rose .member-stats-op__count {
  color: var(--ms-rose);
}

.member-stats-op__name {
  font-size: 12px;
  color: var(--ms-muted);
  font-weight: 700;
}

.member-stats-op__count {
  margin-top: auto;
  font-size: 22px;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1180px) {
  .member-stats-top,
  .member-stats-structure,
  .member-stats-archive {
    grid-template-columns: 1fr 1fr;
  }

  .member-stats-structure__col + .member-stats-structure__col {
    border-left: 0;
    border-top: 1px solid var(--ms-line);
  }

  .member-stats-kpi {
    border-bottom: 1px solid var(--ms-line);
  }

  .member-stats-ops__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .member-stats-ops__head {
    align-items: stretch;
    flex-direction: column;
  }

  .member-stats-meals {
    min-width: 0;
  }
}

@media (max-width: 720px) {
  .member-stats-head,
  .member-stats-hero__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .member-stats-top,
  .member-stats-archive,
  .member-stats-ops__grid {
    grid-template-columns: 1fr;
  }

  .member-stats-meals {
    flex-wrap: wrap;
    row-gap: 10px;
  }

  .member-stats-hero__metric strong {
    font-size: 64px;
  }
}
</style>

