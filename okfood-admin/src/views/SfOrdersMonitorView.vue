<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { RefreshCw } from 'lucide-vue-next'
import { apiBlob, apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
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
const exporting = ref(false)
const cancelBusyId = ref(null)
const retryBusyId = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
/** 分页：每页条数可切换（与接口 page_size 一致） */
const pageSizeOptions = [10, 20, 50, 100]
const deliveryDate = ref(todayShanghaiStr())
/** 回调订单状态筛：空=全部；unknown=尚无回调状态；其余为顺丰 order_status 数值字符串 */
const orderStatusFilter = ref('')
/** 创单状态：空=全部；ok=成功；fail=失败 */
const createStatusFilter = ref('')
const memberPhoneFilter = ref('')
const sfOrderIdFilter = ref('')

const createStatusOptions = [
  { value: '', label: '全部创单' },
  { value: 'ok', label: '创单成功' },
  { value: 'fail', label: '创单失败' },
]

const pushStats = ref(null)
const statsLoading = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / pageSize.value)))

/** 表格序号（跨页连续） */
function tableRowIndex(index) {
  return (page.value - 1) * pageSize.value + index + 1
}

async function fetchPushStats() {
  if (!adminAccessToken.value) return
  const d = (deliveryDate.value || '').trim()
  if (!d) {
    pushStats.value = null
    return
  }
  statsLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('delivery_date', d)
    const data = await apiJson(`/api/admin/delivery-sf/pushes/stats?${q.toString()}`, {}, { auth: true })
    pushStats.value = data && typeof data === 'object' ? data : null
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    pushStats.value = null
  } finally {
    statsLoading.value = false
  }
}

async function refreshMonitor() {
  await fetchPushStats()
  await fetchList()
}

function appendMonitorListQuery(q) {
  const d = (deliveryDate.value || '').trim()
  if (d) q.set('delivery_date', d)
  const os = (orderStatusFilter.value ?? '').trim()
  if (os === 'unknown') q.set('callback_order_status_unknown', 'true')
  else if (os !== '') q.set('sf_callback_order_status', os)
  const cs = (createStatusFilter.value || '').trim()
  if (cs === 'ok' || cs === 'fail') q.set('sf_create_status', cs)
  const ph = (memberPhoneFilter.value || '').trim()
  if (ph) q.set('member_phone', ph)
  const oid = (sfOrderIdFilter.value || '').trim()
  if (oid) q.set('sf_order_id', oid)
}

async function fetchList() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const q = new URLSearchParams()
    q.set('page', String(page.value))
    q.set('page_size', String(pageSize.value))
    appendMonitorListQuery(q)
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
  void refreshMonitor()
}

function onOrderStatusChange() {
  page.value = 1
  void fetchList()
}

function onCreateStatusChange() {
  page.value = 1
  void fetchList()
}

function onTextFilterChange() {
  page.value = 1
  void fetchList()
}

function onPageSizeChange() {
  page.value = 1
  void fetchList()
}

async function exportExcel() {
  if (!adminAccessToken.value) return
  const d = (deliveryDate.value || '').trim()
  if (!d) {
    showToast('请先选择业务日', 'error')
    return
  }
  exporting.value = true
  try {
    const q = new URLSearchParams()
    q.set('delivery_date', d)
    appendMonitorListQuery(q)
    const { blob } = await apiBlob(`/api/admin/delivery-sf/pushes/export.xlsx?${q.toString()}`, {}, { auth: true })
    const href = URL.createObjectURL(blob)
    try {
      const a = document.createElement('a')
      a.href = href
      a.download = `顺丰订单监控_${d}.xlsx`
      a.rel = 'noopener'
      document.body.appendChild(a)
      a.click()
      a.remove()
    } finally {
      URL.revokeObjectURL(href)
    }
    showToast('已开始下载', 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '导出失败', 'error')
  } finally {
    exporting.value = false
  }
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

/** 顺丰开放平台 order_status（与接口文档枚举一致） */
const SF_ORDER_STATUS_ZH = {
  1: '订单创建',
  2: '订单取消',
  10: '配送员接单/配送员改派',
  12: '配送员到店',
  15: '配送员配送中（已取货）',
  17: '配送员妥投完单',
  22: '配送员撤单',
  31: '取消中',
  91: '骑士上报异常',
}

const orderStatusOptions = computed(() => {
  const opts = [
    { value: '', label: '全部回调状态' },
    { value: 'unknown', label: '暂无回调状态' },
  ]
  const nums = Object.keys(SF_ORDER_STATUS_ZH)
    .map((k) => Number(k))
    .filter((n) => !Number.isNaN(n))
    .sort((a, b) => a - b)
  for (const n of nums) {
    const zh = SF_ORDER_STATUS_ZH[n]
    opts.push({ value: String(n), label: zh })
  }
  return opts
})

/** 回调路由 kind（落库 last_callback_kind） */
const SF_CALLBACK_KIND_ZH = {
  delivery_status: '配送状态变更',
  order_complete: '订单完成',
  cancel_by_sf: '顺丰取消',
  delivery_exception: '配送异常',
  rider_cancel: '骑士取消',
  auto_shop: '自动店铺',
  oauth_callback: 'OAuth 授权',
  oauth_revoke: 'OAuth 撤销',
}

function sfOrderStatusLabel(code) {
  if (code === undefined || code === null || code === '') return '—'
  const n = Number(code)
  if (Number.isNaN(n)) return '未识别'
  const zh = SF_ORDER_STATUS_ZH[n]
  if (zh) return zh
  return '未识别'
}

function sfCallbackKindLabel(kind) {
  const k = String(kind || '').trim()
  if (!k) return '—'
  const zh = SF_CALLBACK_KIND_ZH[k]
  return zh ? `${zh}（${k}）` : k
}

/** 监控列表：系统会员姓名 / 手机（同一停靠点可能多人合并一单） */
function formatMemberNames(row) {
  const list = row?.members
  if (!Array.isArray(list) || !list.length) return '—'
  return list.map((m) => String(m?.name ?? '').trim() || '—').join('；')
}

function formatMemberPhones(row) {
  const list = row?.members
  if (!Array.isArray(list) || !list.length) return '—'
  return list.map((m) => String(m?.phone ?? '').trim() || '—').join('；')
}

/** 是否可向顺丰发起 cancelorder（创单成功且非已取消/妥投/取消中等终态） */
function canCancelSfRow(row) {
  const code = row?.error_code
  if (code !== 0 && code !== '0') return false
  const stRaw = row?.sf_callback_order_status
  if (stRaw !== undefined && stRaw !== null && stRaw !== '') {
    const stNum = Number(stRaw)
    if (!Number.isNaN(stNum)) {
      // 2 订单取消 · 17 妥投 · 22 骑手撤单 · 31 取消中（不再展示）
      if ([2, 17, 22, 31].includes(stNum)) return false
    }
  }
  const kind = String(row?.last_callback_kind || '').trim()
  if (kind === 'cancel_by_sf' || kind === 'rider_cancel') return false
  return !!(row?.sf_order_id || row?.shop_order_id)
}

function canRetrySfRow(row) {
  const code = row?.error_code
  if (code === 0 || code === '0') return false
  return true
}

async function onRetrySf(row) {
  try {
    await ElMessageBox.confirm(
      '将按当前配送大表数据对该停靠点重新发起顺丰创单（仅适用于创单失败记录）。',
      '重试推单',
      {
        confirmButtonText: '确认重试',
        cancelButtonText: '关闭',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }
  retryBusyId.value = row.id
  try {
    const res = await apiJson(
      `/api/admin/delivery-sf/pushes/${row.id}/retry`,
      { method: 'POST', body: JSON.stringify({}) },
      { auth: true },
    )
    if (res && res.ok === false) {
      showToast(res.message || '重试未成功', 'warning')
    } else {
      showToast('已提交重试', 'success')
    }
    await refreshMonitor()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '重试失败', 'error')
  } finally {
    retryBusyId.value = null
  }
}

async function onCancelSf(row) {
  const sid = row.sf_order_id || row.shop_order_id || '—'
  try {
    await ElMessageBox.confirm(
      `将向顺丰开放平台发起取消配送。\n单号：${sid}`,
      '取消配送',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '关闭',
        type: 'warning',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }
  cancelBusyId.value = row.id
  try {
    await apiJson(
      `/api/admin/delivery-sf/pushes/${row.id}/cancel`,
      { method: 'POST', body: JSON.stringify({}) },
      { auth: true },
    )
    showToast('已向顺丰提交取消', 'success')
    await refreshMonitor()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '取消失败', 'error')
  } finally {
    cancelBusyId.value = null
  }
}

onMounted(() => {
  void refreshMonitor()
})
</script>

<template>
  <section class="tab-content animate-up sf-orders-monitor">
    <div class="table-container">
      <div class="sf-monitor-toolbar">
        <p class="sf-monitor-hint">
          顺丰侧「订单完成」回调或配送状态中<strong>妥投完单 (17)</strong>通过后，系统将按停靠点对订阅会员<strong>标记送达并扣次数</strong>（与配送大表「标记送达」一致）；单点餐仅更新履约状态。
        </p>
        <p v-if="pushStats" class="sf-monitor-stats">
          <strong>业务日 {{ pushStats.delivery_date }}</strong>：共 {{ pushStats.total }} 单 · 成功
          {{ pushStats.success }} · 失败 {{ pushStats.failed }}
          <span class="sf-monitor-stats-sub">（按配送业务日统计，与下方列表「业务日」一致；夜间推送记在该配送日）</span>
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
          <label class="sf-monitor-field">
            <span>创单状态</span>
            <el-select
              v-model="createStatusFilter"
              placeholder="全部创单"
              :disabled="loading"
              clearable
              class="sf-monitor-select-narrow"
              @change="onCreateStatusChange"
            >
              <el-option
                v-for="opt in createStatusOptions"
                :key="opt.value === '' ? '_c_all' : opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </label>
          <label class="sf-monitor-field">
            <span>会员手机</span>
            <el-input
              v-model="memberPhoneFilter"
              clearable
              placeholder="后几位或完整号"
              :disabled="loading"
              class="sf-monitor-input-phone"
              @change="onTextFilterChange"
            />
          </label>
          <label class="sf-monitor-field">
            <span>顺丰单号</span>
            <el-input
              v-model="sfOrderIdFilter"
              clearable
              placeholder="运单号包含"
              :disabled="loading"
              class="sf-monitor-input-sf"
              @change="onTextFilterChange"
            />
          </label>
          <label class="sf-monitor-field">
            <span>回调订单状态</span>
            <el-select
              v-model="orderStatusFilter"
              placeholder="全部回调"
              :disabled="loading"
              clearable
              filterable
              class="sf-monitor-status"
              @change="onOrderStatusChange"
            >
              <el-option
                v-for="opt in orderStatusOptions"
                :key="opt.value === '' ? '_all' : opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </label>
          <el-button plain class="sf-monitor-refresh" :loading="loading" @click="refreshMonitor">
            <span class="sf-monitor-refresh-inner">
              <RefreshCw v-if="!loading" :size="16" stroke-width="2" />
              刷新
            </span>
          </el-button>
          <el-button
            type="primary"
            plain
            :loading="exporting"
            :disabled="loading || !(deliveryDate || '').trim()"
            @click="exportExcel"
          >
            导出 Excel
          </el-button>
        </div>
      </div>

      <AdminTable variant="members" :data="items" :loading="loading" row-key="id" empty-text="暂无推单记录">
        <el-table-column type="index" :index="tableRowIndex" label="序号" width="100" align="center" />
        <el-table-column prop="delivery_date" label="业务日" width="150" />
        <el-table-column label="顺丰单号" min-width="120" class-name="td-mono">
          <template #default="{ row }">{{ row.sf_order_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="会员姓名" min-width="132" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberNames(row) }}</template>
        </el-table-column>
        <el-table-column label="会员手机" min-width="132" class-name="td-mono" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberPhones(row) }}</template>
        </el-table-column>
        <el-table-column label="创单状态" width="120">
          <template #default="{ row }">{{ sfStatusLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="回调订单状态" min-width="200">
          <template #default="{ row }">{{ sfOrderStatusLabel(row.sf_callback_order_status) }}</template>
        </el-table-column>
        <el-table-column label="最近回调类型" min-width="200">
          <template #default="{ row }">{{ sfCallbackKindLabel(row.last_callback_kind) }}</template>
        </el-table-column>
        <el-table-column label="最近回调时间" width="168">
          <template #default="{ row }">{{ row.last_callback_at ? row.last_callback_at.replace('T', ' ').slice(0, 19) : '—' }}</template>
        </el-table-column>
        <el-table-column label="创单时间" width="168">
          <template #default="{ row }">{{ row.created_at ? row.created_at.replace('T', ' ').slice(0, 19) : '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="sf-monitor-ops">
              <el-button v-if="canRetrySfRow(row)" type="primary" plain size="small" :loading="retryBusyId === row.id"
                :disabled="loading" @click="onRetrySf(row)">
                重试推单
              </el-button>
              <el-button v-if="canCancelSfRow(row)" type="danger" plain size="small" :loading="cancelBusyId === row.id"
                :disabled="loading" @click="onCancelSf(row)">
                取消配送
              </el-button>
              <span v-if="!canRetrySfRow(row) && !canCancelSfRow(row)" class="sf-monitor-op-muted">—</span>
            </div>
          </template>
        </el-table-column>
      </AdminTable>

      <div class="sf-monitor-pager">
        <el-button plain size="small" :disabled="loading || page <= 1 || total <= 0" @click="goPrev">
          上一页
        </el-button>
        <span class="sf-monitor-page-meta">
          <label class="sf-pager-pagesize-field">
            <span class="sf-pager-pagesize-label">每页</span>
            <el-select
              v-model="pageSize"
              class="sf-pager-size-select"
              :disabled="loading"
              @change="onPageSizeChange"
            >
              <el-option v-for="n in pageSizeOptions" :key="n" :label="`${n} 条`" :value="n" />
            </el-select>
          </label>
          <span class="sf-pager-sep">·</span>
          <span>第 <strong class="sf-pager-em">{{ page }}</strong> / {{ totalPages }} 页</span>
          <span class="sf-pager-sep">·</span>
          <span>本页 <strong class="sf-pager-em">{{ items.length }}</strong> 条</span>
          <span class="sf-pager-sep">·</span>
          <span class="sf-pager-total">合计 <strong class="sf-pager-em">{{ total }}</strong> 条</span>
        </span>
        <el-button plain size="small" :disabled="loading || page >= totalPages || total <= 0" @click="goNext">
          下一页
        </el-button>
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
.sf-monitor-stats {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #0f172a;
  padding: 10px 14px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.sf-monitor-stats :deep(strong) {
  color: #0f172a;
  font-weight: 600;
}

.sf-monitor-stats-sub {
  margin-left: 6px;
  font-size: 12px;
  color: #475569;
}
.sf-monitor-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  /* 浅色工具条：标签与控件文字对比度 */
  --sf-filter-fg: #0f172a;
  --sf-filter-muted: #64748b;
  --sf-filter-border: #cbd5e1;
  --sf-filter-bg: #ffffff;
}
.sf-monitor-field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.sf-monitor-field > span:first-of-type {
  flex-shrink: 0;
  color: #334155;
  font-weight: 500;
}
.sf-monitor-filters :deep(.el-input__wrapper),
.sf-monitor-filters :deep(.el-select__wrapper) {
  background-color: var(--sf-filter-bg);
  box-shadow: 0 0 0 1px var(--sf-filter-border) inset;
}
.sf-monitor-filters :deep(.el-input__inner),
.sf-monitor-filters :deep(.el-select__selected-item),
.sf-monitor-filters :deep(.el-select__input),
.sf-monitor-filters :deep(.el-select__placeholder) {
  color: var(--sf-filter-fg);
}
.sf-monitor-filters :deep(.el-input__inner::placeholder),
.sf-monitor-filters :deep(.el-select__placeholder.is-transparent) {
  color: var(--sf-filter-muted);
}
.sf-monitor-select-narrow {
  width: 132px;
}
.sf-monitor-input-phone {
  width: 168px;
}
.sf-monitor-input-sf {
  width: 148px;
}
.sf-monitor-date {
  width: 160px;
}
.sf-monitor-status {
  width: 240px;
}
.sf-monitor-refresh-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.sf-monitor-pager {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 10px 14px;
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.5;
  color: #334155;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.sf-monitor-pager :deep(strong) {
  color: #0f172a;
}
.sf-monitor-page-meta {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 4px 10px;
  text-align: right;
  flex: 1 1 280px;
  min-width: min(100%, 360px);
}
.sf-pager-pagesize-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  cursor: pointer;
}
.sf-pager-pagesize-label {
  flex-shrink: 0;
  font-weight: 600;
  color: #0f172a;
  font-size: 13px;
}
.sf-pager-size-select {
  width: 108px;
}
.sf-monitor-pager :deep(.sf-pager-size-select .el-select__wrapper),
.sf-monitor-pager :deep(.sf-pager-size-select .el-input__wrapper) {
  background-color: #ffffff;
  box-shadow: 0 0 0 1px #cbd5e1 inset;
}
.sf-monitor-pager :deep(.sf-pager-size-select .el-select__selected-item),
.sf-monitor-pager :deep(.sf-pager-size-select .el-select__placeholder) {
  color: #0f172a;
  font-weight: 500;
}
.sf-pager-em {
  font-weight: 700;
  color: #0f172a;
}
.sf-pager-sep {
  opacity: 0.55;
  user-select: none;
  color: #94a3b8;
}
.sf-pager-total {
  font-weight: 600;
  color: #0f172a;
}
.sf-monitor-op-muted {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.42);
}
.sf-monitor-ops {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
</style>
