<script setup>
import { ref, computed, onMounted } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

function todayShanghaiStr() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const y = parts.find((p) => p.type === 'year')?.value || '1970'
  const mo = parts.find((p) => p.type === 'month')?.value || '01'
  const da = parts.find((p) => p.type === 'day')?.value || '01'
  return `${y}-${mo}-${da}`
}

const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const deliveryDate = ref(todayShanghaiStr())

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)))

async function fetchList() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const q = new URLSearchParams()
    q.set('page', String(page.value))
    q.set('page_size', String(pageSize.value))
    const d = (deliveryDate.value || '').trim()
    if (d) q.set('delivery_date', d)
    const data = await apiJson(`/api/admin/delivery-sf/pushes?${q.toString()}`, {}, { auth: true })
    items.value = Array.isArray(data?.items) ? data.items : []
    total.value = Number(data?.total) || 0
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    items.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onDateChange() {
  page.value = 1
  void fetchList()
}

function goPrev() {
  if (page.value <= 1 || loading.value) return
  page.value -= 1
  void fetchList()
}

function goNext() {
  if (page.value >= totalPages.value || loading.value) return
  page.value += 1
  void fetchList()
}

function sfStatusLabel(row) {
  const code = row.error_code
  if (code === 0 || code === '0') return '创单成功'
  if (code === undefined || code === null) return '—'
  return `失败 (${code})`
}

function ellipsisMid(s, head = 6, tail = 4) {
  const x = String(s || '').trim()
  if (!x) return '—'
  if (x.length <= head + tail + 1) return x
  return `${x.slice(0, head)}…${x.slice(-tail)}`
}

onMounted(() => {
  void fetchList()
})
</script>

<template>
  <section class="tab-content animate-up sf-orders-monitor">
    <div class="table-container">
      <div class="sf-monitor-toolbar">
        <p class="sf-monitor-hint">
          顺丰侧「订单完成」回调通过后，系统将按停靠点对订阅会员<strong>标记送达并扣次数</strong>（与配送大表「标记送达」一致）；单点餐仅更新履约状态。
        </p>
        <div class="sf-monitor-filters">
          <label class="sf-monitor-field">
            <span>业务日</span>
            <el-date-picker
              v-model="deliveryDate"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="全部日期"
              :clearable="true"
              :disabled="loading"
              class="sf-monitor-date"
              @change="onDateChange"
            />
          </label>
          <button type="button" class="btn-ghost sf-monitor-refresh" :disabled="loading" @click="fetchList">
            <RefreshCw :size="16" stroke-width="2" :class="{ 'sf-spin': loading }" />
            刷新
          </button>
        </div>
      </div>

      <AdminTable variant="members" :data="items" :loading="loading" row-key="id" empty-text="暂无推单记录">
        <el-table-column prop="delivery_date" label="业务日" width="118" />
        <el-table-column label="停靠点(stop_id)" min-width="120" class-name="td-mono">
          <template #default="{ row }">
            {{ ellipsisMid(row.stop_id, 8, 6) }}
          </template>
        </el-table-column>
        <el-table-column label="商户订单号" min-width="160" class-name="td-mono">
          <template #default="{ row }">{{ row.shop_order_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="顺丰单号" min-width="120" class-name="td-mono">
          <template #default="{ row }">{{ row.sf_order_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="创单状态" width="110">
          <template #default="{ row }">{{ sfStatusLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="sf_callback_order_status" label="回调订单状态码" width="140" align="center" />
        <el-table-column prop="last_callback_kind" label="最近回调类型" width="130" />
        <el-table-column label="最近回调时间" width="168">
          <template #default="{ row }">{{ row.last_callback_at ? row.last_callback_at.replace('T', ' ').slice(0, 19) : '—' }}</template>
        </el-table-column>
        <el-table-column label="创单时间" width="168">
          <template #default="{ row }">{{ row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '—' }}</template>
        </el-table-column>
      </AdminTable>

      <div v-if="total > 0" class="sf-monitor-pager">
        <button type="button" class="btn-ghost btn-ghost--sm" :disabled="loading || page <= 1" @click="goPrev">
          上一页
        </button>
        <span class="sf-monitor-page-meta">{{ page }} / {{ totalPages }} · 共 {{ total }} 条</span>
        <button type="button" class="btn-ghost btn-ghost--sm" :disabled="loading || page >= totalPages" @click="goNext">
          下一页
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.sf-monitor-toolbar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}
.sf-monitor-hint {
  margin: 0;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.55;
}
.sf-monitor-hint code {
  font-size: 12px;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.25);
}
.sf-monitor-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}
.sf-monitor-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}
.sf-monitor-date {
  width: 160px;
}
.sf-monitor-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.sf-spin {
  animation: sf-spin 0.8s linear infinite;
}
@keyframes sf-spin {
  to {
    transform: rotate(360deg);
  }
}
.sf-monitor-pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 12px;
  padding-bottom: 8px;
  font-size: 13px;
  color: rgba(255, 255, 255, 0.72);
}
.sf-monitor-page-meta {
  min-width: 120px;
  text-align: center;
}
</style>
