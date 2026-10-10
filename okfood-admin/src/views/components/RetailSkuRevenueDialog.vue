<script setup>
/**
 * 财务中心：商城订单按 SKU 的实收营业额。
 * 窗口与财务卡「商城订单」一致（日 / 月 / 累计）。
 */
import { computed, ref, watch } from 'vue'
import { apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  /** day | month | cumulative */
  window: { type: String, default: 'month' },
  /** window=day 时 YYYY-MM-DD */
  calendarDate: { type: String, default: '' },
  /** window=month 时 YYYY-MM */
  calendarMonth: { type: String, default: '' },
})

const emit = defineEmits(['update:visible'])

const loading = ref(false)
/** @type {import('vue').Ref<Array<SkuRow>>} */
const rows = ref([])
const orderCount = ref(0)
const amountYuan = ref('0')
const periodLabel = ref('')

/**
 * @typedef {Object} SkuRow
 * @property {number} retail_product_id
 * @property {string} sku_name
 * @property {string | null} spu_title
 * @property {string | null} spec_label
 * @property {number} quantity
 * @property {number} order_count
 * @property {string | number} amount_yuan
 */

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const dialogTitle = computed(() => {
  const label = periodText(periodLabel.value || fallbackPeriod())
  return `商城订单 SKU 营业额 · ${label}`
})

function fallbackPeriod() {
  if (props.window === 'day') return props.calendarDate || '当日'
  if (props.window === 'month') return props.calendarMonth || '当月'
  return '累计'
}

/** 2026-09-24 / 2026-09 → 中文日期 */
function periodText(raw) {
  const day = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw || '')
  if (day) return `${day[1]}年${Number(day[2])}月${Number(day[3])}日`
  const month = /^(\d{4})-(\d{2})$/.exec(raw || '')
  if (month) return `${month[1]}年${Number(month[2])}月`
  return raw || '累计'
}

function fmtYuan(raw) {
  const n = Number(raw)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const totalAmount = computed(() => {
  return rows.value.reduce((sum, row) => sum + (Number(row.amount_yuan) || 0), 0)
})

function shareText(amount) {
  const total = totalAmount.value
  const n = Number(amount) || 0
  if (total <= 0) return '—'
  return `${((n / total) * 100).toFixed(2)}%`
}

function buildQuery() {
  const params = new URLSearchParams({ window: props.window || 'month' })
  if (props.window === 'day' && props.calendarDate) {
    params.set('calendar_date', props.calendarDate)
  }
  if (props.window === 'month' && props.calendarMonth) {
    params.set('calendar_month', props.calendarMonth)
  }
  return params.toString()
}

async function loadRows() {
  loading.value = true
  try {
    const data = await apiJson(`/api/admin/finance/retail-sku-revenue?${buildQuery()}`, {}, { auth: true })
    rows.value = Array.isArray(data?.items) ? data.items : []
    orderCount.value = Number(data?.order_count) || 0
    amountYuan.value = data?.amount_yuan ?? '0'
    periodLabel.value = String(data?.period_label || '')
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : 'SKU 营业额加载失败', 'error')
    rows.value = []
    orderCount.value = 0
    amountYuan.value = '0'
  } finally {
    loading.value = false
  }
}

function summaryMethod({ columns, data }) {
  const qty = data.reduce((sum, row) => sum + (Number(row.quantity) || 0), 0)
  const amt = data.reduce((sum, row) => sum + (Number(row.amount_yuan) || 0), 0)
  return columns.map((col, index) => {
    if (index === 0) return '合计'
    if (col.property === 'quantity') return String(qty)
    if (col.property === 'amount_yuan') return `¥${fmtYuan(amt)}`
    if (col.property === 'order_count') return `${orderCount.value} 笔订单`
    return ''
  })
}

watch(
  () => props.visible,
  (open) => {
    if (open) void loadRows()
  },
)
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="dialogTitle"
    width="760px"
    destroy-on-close
    append-to-body
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="仅统计当前仍为已支付的商城订单。用了优惠券的订单按各 SKU 券前金额比例分摊实收，各 SKU 合计等于卡片上的商城订单金额。"
      class="sku-revenue-alert"
    />
    <el-table
      v-loading="loading"
      :data="rows"
      stripe
      max-height="460"
      empty-text="该时段暂无已支付商城订单"
      show-summary
      :summary-method="summaryMethod"
    >
      <el-table-column prop="sku_name" label="SKU" min-width="220" show-overflow-tooltip />
      <el-table-column prop="spec_label" label="规格" min-width="100" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.spec_label || '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="quantity" label="销量" width="90" align="right" />
      <el-table-column prop="order_count" label="订单笔数" width="100" align="right" />
      <el-table-column label="占比" width="90" align="right">
        <template #default="{ row }">
          {{ shareText(row.amount_yuan) }}
        </template>
      </el-table-column>
      <el-table-column prop="amount_yuan" label="营业额（元）" width="140" align="right">
        <template #default="{ row }">
          ¥{{ fmtYuan(row.amount_yuan) }}
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.sku-revenue-alert {
  margin-bottom: 12px;
}
</style>
