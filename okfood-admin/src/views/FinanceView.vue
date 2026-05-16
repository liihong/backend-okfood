<script setup>
import { computed, onMounted, ref } from 'vue'
import { Calendar, CalendarDays, CreditCard, DollarSign, History } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const loading = ref(false)
/** @type {import('vue').Ref<any>} */
const summary = ref(null)
/** @type {import('vue').Ref<Array<{ order_id: number; time_hm: string; card_kind: string; amount_yuan: string | number }>>} */
const todayPaidCardItems = ref([])

function fmtYuan(raw) {
  if (raw === null || raw === undefined) return '—'
  const n = Number(raw)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const todayLabel = computed(() => {
  const t = summary.value?.shanghai_today
  if (!t) return ''
  return String(t)
})

const monthLabel = computed(() => {
  const m = summary.value?.shanghai_calendar_month
  if (!m) return ''
  const [y, mo] = m.split('-')
  if (!y || !mo) return m
  return `${y}年${mo.replace(/^0/, '')}月`
})

const periodRows = computed(() => {
  const s = summary.value
  if (!s) return []
  const mk = (id, period, w) => ({
    id,
    period,
    total: w?.total_amount_yuan,
    count: w?.total_count ?? 0,
    cardCount: w?.card_orders?.count ?? 0,
    cardAmt: w?.card_orders?.amount_yuan,
    smCount: w?.single_meal_orders?.count ?? 0,
    smAmt: w?.single_meal_orders?.amount_yuan,
  })
  return [
    mk('today', `今日（ ${todayLabel.value || '—'}）`, s.today),
    mk('month', `本月（ ${monthLabel.value || s.shanghai_calendar_month || '—'}）`, s.this_month),
    mk('cumulative', '累计（全部已标记已收）', s.cumulative),
  ]
})

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

onMounted(loadSummary)
</script>

<template>
  <section class="tab-content animate-up">
    <div class="finance-grid finance-grid--triple">
      <div class="finance-card primary">
        <Calendar class="bg-icon" :size="72" />
        <p class="f-label">今日收入 / TODAY (SH)</p>
        <div class="f-main">
          <span class="f-val f-val--panel">¥ {{ summary ? fmtYuan(summary.today?.total_amount_yuan) : loading ? '…' : '—' }}</span>
        </div>
        <p class="f-sub" v-if="summary">共 {{ summary.today?.total_count ?? 0 }} 笔</p>
      </div>
      <div class="finance-card white">
        <CalendarDays class="bg-icon bg-icon--muted" :size="72" />
        <p class="f-label-dark">本月收入 / MONTH (SH)</p>
        <p class="f-val--panel" style="margin-top: 0.75rem">
          ¥ {{ summary ? fmtYuan(summary.this_month?.total_amount_yuan) : loading ? '…' : '—' }}
        </p>
        <p class="finance-remark" style="margin-top: 0.75rem">
          {{ monthLabel || '—' }} · 共 {{ summary ? summary.this_month?.total_count ?? 0 : loading ? '…' : '—' }} 笔
        </p>
      </div>
      <div class="finance-card white">
        <DollarSign class="bg-icon bg-icon--muted" :size="72" />
        <p class="f-label-dark">累计已收 / ALL TIME</p>
        <p class="f-val--panel" style="margin-top: 0.75rem">
          ¥ {{ summary ? fmtYuan(summary.cumulative?.total_amount_yuan) : loading ? '…' : '—' }}
        </p>
        <p class="finance-remark" style="margin-top: 0.75rem">共 {{ summary ? summary.cumulative?.total_count ?? 0 : loading ? '…' : '—' }} 笔</p>
      </div>
    </div>

  <div class="table-container table-container-finance finance-today-cards">
      <div class="table-header">
        <div class="finance-section-head">
          <CreditCard :size="20" /> 今日开卡收款明细
          <span v-if="todayLabel" class="finance-today-cards__date">（{{ todayLabel }}）</span>
        </div>
        <p class="finance-remark finance-today-cards__hint">
          已缴工单按上海时间列出；时刻与卡型对应单笔收入。口径与上方「今日收入」中的开卡统计一致（工单
          <span class="em">updated_at</span> 落入当日）。
       </p>
      </div>
     <AdminTable variant="default" :data="todayPaidCardItems" :loading="loading" row-key="order_id"
        empty-text="今日暂无已缴开卡记录">
        <el-table-column prop="time_hm" label="时间" min-width="88" />
        <el-table-column prop="card_kind" label="卡型" min-width="100" />
        <el-table-column label="实收（元）" min-width="120" align="right" class-name="td-paid">
          <template #default="{ row: r }">
            <span class="font-black">¥ {{ fmtYuan(r.amount_yuan) }}</span>
          </template>
        </el-table-column>
      </AdminTable>
   </div>
    <div class="table-container table-container-finance">
      <div class="table-header">
        <div class="finance-section-head">
          <History :size="20" /> 按区间分项（开卡工单 / 单次点餐）
        </div>
      </div>
      <AdminTable variant="default" :data="periodRows" :loading="loading" row-key="id" empty-text="暂无数据">
        <el-table-column prop="period" label="统计区间" min-width="200" />
        <el-table-column label="实收合计" min-width="120" align="right" class-name="td-paid">
          <template #default="{ row: r }">
            <span class="font-black">¥ {{ fmtYuan(r.total) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="总笔数" min-width="88" align="right">
          <template #default="{ row: r }">{{ r.count }}</template>
        </el-table-column>
        <el-table-column label="开卡工单" min-width="168" class-name="t-sub">
          <template #default="{ row: r }"> {{ r.cardCount }} 笔 · ¥ {{ fmtYuan(r.cardAmt) }} </template>
        </el-table-column>
        <el-table-column label="单次点餐" min-width="168" class-name="t-sub">
          <template #default="{ row: r }"> {{ r.smCount }} 笔 · ¥ {{ fmtYuan(r.smAmt) }} </template>
        </el-table-column>
      </AdminTable>
    </div>
  </section>
</template>

<style scoped>
.finance-today-cards__date {
  margin-left: 0.35rem;
  font-size: 0.95rem;
  font-weight: 600;
  color: #64748b;
}

.finance-today-cards__hint {
  margin: 0.5rem 0 0;
  max-width: 52rem;
}
</style>
