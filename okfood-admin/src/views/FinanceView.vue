<script setup>
import { computed, onMounted, ref } from 'vue'
import { Calendar, CalendarDays, DollarSign, History } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const loading = ref(false)
/** @type {import('vue').Ref<any>} */
const summary = ref(null)

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
    const data = await apiJson('/api/admin/finance/received-summary', {}, { auth: true })
    summary.value = data || null
  } catch (e) {
    showToast(e?.message || '加载失败', 'error')
    summary.value = null
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

      <div class="finance-card white finance-card--note">
        <p class="f-label-dark">口径说明</p>
        <p class="finance-remark">
          统计<span class="em">日历</span>下的「今日 / 本月」：以订单
          <span class="em">updated_at</span>（库内 UTC 时间）换算后是否落入对应日界为准。支付成功或后台改为已缴时会更新该时间。
        </p>
        <p class="finance-remark">
          开卡工单：<span class="em">已缴</span>且计入金额取工单实收；未填金额则笔数仍计、金额按 0。若已缴工单后续仅改备注等触发了更新时间，可能落入新的统计日（尚无独立「收款时间」字段）。
        </p>
        <p class="finance-remark">单次点餐：<span class="em">已支付</span>订单实付。</p>
      </div>
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
