<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { RefreshCw, Search } from 'lucide-vue-next'
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

/** ISO 或带 T 的 UTC 时间 → 上海本地 `MM-DD HH:mm` 展示 */
function formatOrderTime(iso) {
  if (iso == null || iso === '') return '—'
  const s = String(iso).trim()
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) {
    const x = s.replace('T', ' ')
    const m = x.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
    return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : x.slice(0, 16)
  }
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(d)
  const mo = parts.find((p) => p.type === 'month')?.value ?? ''
  const da = parts.find((p) => p.type === 'day')?.value ?? ''
  const hr = parts.find((p) => p.type === 'hour')?.value ?? ''
  const mi = parts.find((p) => p.type === 'minute')?.value ?? ''
  if (!mo || !da) return s.slice(0, 16)
  return `${mo}-${da} ${hr}:${mi}`
}

const activeTab = ref('single')
const orderDate = ref(todayShanghaiStr())
const searchQuery = ref('')
const singlePayFilter = ref('')
const mallPayFilter = ref('')
const loading = ref(false)
const singleItems = ref([])
const singleTotal = ref(0)
const mallItems = ref([])
const mallTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)

const totalPages = computed(() => {
  const t = activeTab.value === 'single' ? singleTotal.value : mallTotal.value
  return Math.max(1, Math.ceil((t || 0) / pageSize.value))
})

function singlePayClass(s) {
  if (s === '已支付') return 'member-pill member-pill--emerald'
  return 'member-pill member-pill--amber'
}

function mallPayClass(s) {
  if (s === '已缴') return 'member-pill member-pill--emerald'
  return 'member-pill member-pill--amber'
}

const FULFILLMENT_STATUS_ZH = {
  pending: '待履约',
  delivered: '已履约',
}

/** 单次点餐履约状态：接口为英文枚举，列表展示中文 */
function fulfillmentLabelZh(s) {
  if (s == null || s === '') return '—'
  const k = String(s).trim().toLowerCase()
  return FULFILLMENT_STATUS_ZH[k] ?? String(s).trim()
}

function fulfillmentClass(s) {
  const x = (s || '').toLowerCase()
  if (x === 'delivered') return 'member-pill member-pill--emerald'
  if (x === 'pending') return 'member-pill member-pill--amber'
  return 'member-pill member-pill--slate'
}

async function fetchSingleMeals() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const q = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const d = (orderDate.value || '').trim()
    if (d) q.set('order_date', d)
    const sq = searchQuery.value.trim()
    if (sq) q.set('q', sq)
    const pf = String(singlePayFilter.value ?? '').trim()
    if (pf === '未支付' || pf === '已支付') q.set('pay_status', pf)
    const data = await apiJson(`/api/admin/orders/daily/single-meals?${q.toString()}`, {}, { auth: true })
    singleItems.value = Array.isArray(data.items) ? data.items : []
    singleTotal.value = Number(data.total) || 0
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载单次订单失败', 'error')
    singleItems.value = []
    singleTotal.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchMallCardOrders() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const q = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const d = (orderDate.value || '').trim()
    if (d) q.set('order_date', d)
    const sq = searchQuery.value.trim()
    if (sq) q.set('q', sq)
    const pf = String(mallPayFilter.value ?? '').trim()
    if (pf === '未缴' || pf === '已缴') q.set('pay_status', pf)
    const data = await apiJson(`/api/admin/orders/daily/mall-card-orders?${q.toString()}`, {}, { auth: true })
    mallItems.value = Array.isArray(data.items) ? data.items : []
    mallTotal.value = Number(data.total) || 0
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载商城卡包订单失败', 'error')
    mallItems.value = []
    mallTotal.value = 0
  } finally {
    loading.value = false
  }
}

function fetchActive() {
  if (activeTab.value === 'single') return fetchSingleMeals()
  return fetchMallCardOrders()
}

function goPrev() {
  if (page.value <= 1) return
  page.value -= 1
  void fetchActive()
}

function goNext() {
  if (page.value >= totalPages.value) return
  page.value += 1
  void fetchActive()
}

let searchTimer = 0
watch(searchQuery, () => {
  if (!adminAccessToken.value) return
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    void fetchActive()
  }, 320)
})

watch([orderDate, singlePayFilter, mallPayFilter, pageSize, activeTab], () => {
  page.value = 1
  void fetchActive()
})

onMounted(() => {
  void fetchActive()
})
</script>

<template>
  <section class="tab-content animate-up orders-manage-page">
    <div class="table-container">
      <div class="table-header table-header--members table-header--couriers-row orders-manage-toolbar">
        <label class="orders-manage-date">
          <span class="orders-manage-date-label">下单日</span>
          <el-date-picker
            v-model="orderDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
            teleported
          />
        </label>
        <div class="search-box search-box--flex orders-manage-search">
          <Search :size="18" />
          <el-input
            v-model="searchQuery"
            clearable
            placeholder="手机前缀或会员姓名…"
            class="orders-manage-search-input"
          />
        </div>
        <button type="button" class="btn-sm orders-manage-refresh" @click="fetchActive">
          <RefreshCw :size="16" stroke-width="2" />
          刷新
        </button>
      </div>

      <el-tabs v-model="activeTab" class="orders-manage-tabs">
        <el-tab-pane label="单次点餐" name="single">
          <div class="orders-manage-tab-bar">
            <div class="orders-filter-el">
              <span class="orders-filter-el-label">支付</span>
              <el-select v-model="singlePayFilter" placeholder="全部" clearable class="orders-filter-el-select">
                <el-option label="全部" value="" />
                <el-option label="未支付" value="未支付" />
                <el-option label="已支付" value="已支付" />
              </el-select>
            </div>
          </div>
          <AdminTable
            variant="members"
            size="small"
            :data="singleItems"
            :loading="loading && activeTab === 'single'"
            row-key="id"
            empty-text="当日暂无单次点餐订单"
          >
            <el-table-column label="#" width="56" class-name="td-mono">
              <template #default="{ row }">{{ row.id }}</template>
            </el-table-column>
            <el-table-column label="下单时间" width="108" class-name="td-mono co-nowrap">
              <template #default="{ row }">{{ formatOrderTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="会员" min-width="120">
              <template #default="{ row }">
                <div class="orders-m-cell">
                  <span class="orders-m-name" :title="row.member_name || ''">{{
                    (row.member_name || '').trim() || '—'
                  }}</span>
                  <span class="orders-m-phone td-mono" :title="row.member_phone || ''">{{
                    (row.member_phone || '').trim() || ''
                  }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="餐品" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ row.dish_title || '—' }}</template>
            </el-table-column>
            <el-table-column label="份数" width="56" align="center">
              <template #default="{ row }">{{ row.quantity ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="供餐日" width="100" class-name="td-mono">
              <template #default="{ row }">{{ row.delivery_date || '—' }}</template>
            </el-table-column>
            <el-table-column label="金额" width="72" align="right" class-name="td-mono">
              <template #default="{ row }">{{ row.amount_yuan ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="支付" width="76" class-name="co-nowrap">
              <template #default="{ row }">
                <span :class="singlePayClass(row.pay_status)">{{ row.pay_status || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="履约" width="88" class-name="co-nowrap">
              <template #default="{ row }">
                <span :class="fulfillmentClass(row.fulfillment_status)">{{
                  fulfillmentLabelZh(row.fulfillment_status)
                }}</span>
              </template>
            </el-table-column>
            <el-table-column label="配送/自提" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                {{ row.store_pickup ? '门店自提' : (row.address_summary || '—') }}
              </template>
            </el-table-column>
            <el-table-column label="单号" width="120" class-name="td-mono" show-overflow-tooltip>
              <template #default="{ row }">{{ row.out_trade_no || '—' }}</template>
            </el-table-column>
          </AdminTable>
        </el-tab-pane>

        <el-tab-pane label="商城卡包" name="mall">
          <div class="orders-manage-tab-bar">
            <div class="orders-filter-el">
              <span class="orders-filter-el-label">缴费</span>
              <el-select v-model="mallPayFilter" placeholder="全部" clearable class="orders-filter-el-select">
                <el-option label="全部" value="" />
                <el-option label="未缴" value="未缴" />
                <el-option label="已缴" value="已缴" />
              </el-select>
            </div>
          </div>
          <AdminTable
            variant="members"
            size="small"
            :data="mallItems"
            :loading="loading && activeTab === 'mall'"
            row-key="id"
            empty-text="当日暂无商城卡包订单"
          >
            <el-table-column label="#" width="56" class-name="td-mono">
              <template #default="{ row }">{{ row.id }}</template>
            </el-table-column>
            <el-table-column label="下单时间" width="108" class-name="td-mono co-nowrap">
              <template #default="{ row }">{{ formatOrderTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="会员" min-width="120">
              <template #default="{ row }">
                <div class="orders-m-cell">
                  <span class="orders-m-name" :title="row.member_name || ''">{{
                    (row.member_name || '').trim() || '—'
                  }}</span>
                  <span class="orders-m-phone td-mono" :title="row.member_phone || ''">{{
                    (row.member_phone || '').trim() || ''
                  }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="商品" min-width="180" show-overflow-tooltip>
              <template #default="{ row }">{{ row.template_product_label || '—' }}</template>
            </el-table-column>
            <el-table-column label="卡型" width="72" align="center">
              <template #default="{ row }">{{ row.card_kind || '—' }}</template>
            </el-table-column>
            <el-table-column label="金额" width="72" align="right" class-name="td-mono">
              <template #default="{ row }">{{ row.amount_yuan ?? '—' }}</template>
            </el-table-column>
            <el-table-column label="渠道" width="72">
              <template #default="{ row }">{{ row.pay_channel || '—' }}</template>
            </el-table-column>
            <el-table-column label="缴费" width="76" align="center" class-name="co-nowrap">
              <template #default="{ row }">
                <span :class="mallPayClass(row.pay_status)">{{ row.pay_status || '—' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="入账" width="76" align="center" class-name="co-nowrap">
              <template #default="{ row }">
                <span
                  class="member-pill"
                  :class="row.applied_to_member ? 'member-pill--emerald' : 'member-pill--slate'"
                >
                  {{ row.applied_to_member ? '已同步' : '未同步' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备注" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">{{
                (row.remark || '').trim() ? row.remark : '—'
              }}</template>
            </el-table-column>
          </AdminTable>
        </el-tab-pane>
      </el-tabs>

      <div v-if="adminAccessToken" class="members-pagination">
        <div class="orders-page-size">
          <span>每页</span>
          <el-select v-model="pageSize" class="orders-page-size-select">
            <el-option :value="10" label="10" />
            <el-option :value="20" label="20" />
            <el-option :value="50" label="50" />
          </el-select>
          <span>条</span>
        </div>
        <button type="button" class="btn-sm" :disabled="page <= 1" @click="goPrev">上一页</button>
        <span class="members-page-meta">第 {{ page }} / {{ totalPages }} 页 · 共 {{ activeTab === 'single' ? singleTotal : mallTotal }} 条</span>
        <button type="button" class="btn-sm" :disabled="page >= totalPages" @click="goNext">
          下一页
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.orders-manage-hint {
  margin: 0 0 1rem;
  font-size: 0.875rem;
  color: rgba(255, 255, 255, 0.68);
  line-height: 1.55;
  max-width: 960px;
}
.orders-manage-hint code {
  font-size: 0.8em;
  padding: 0 0.25rem;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.25);
}
.orders-manage-toolbar {
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: center;
}
.orders-manage-date {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.orders-manage-date-label {
  font-size: 0.8rem;
  color: rgba(255, 255, 255, 0.55);
  white-space: nowrap;
}
.orders-manage-search {
  min-width: 220px;
  flex: 1;
}
.orders-manage-search-input {
  flex: 1;
  min-width: 0;
}
.orders-manage-search :deep(.el-input__wrapper) {
  border-radius: 0.65rem;
}
.orders-filter-el {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.orders-filter-el-label {
  font-size: 13px;
  color: var(--text-muted, #64748b);
  white-space: nowrap;
}
.orders-filter-el-select {
  width: 140px;
}
.orders-page-size-select {
  width: 88px;
}
.orders-manage-refresh {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.orders-manage-tabs {
  margin-top: 0.5rem;
}
.orders-manage-tab-bar {
  margin-bottom: 0.65rem;
}
.orders-m-cell {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  line-height: 1.25;
}
.orders-m-name {
  font-weight: 600;
}
.orders-m-phone {
  font-size: 0.8rem;
  opacity: 0.85;
}
.orders-page-size {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: rgba(255, 255, 255, 0.72);
  margin-right: 0.75rem;
}
</style>
