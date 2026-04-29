<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
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
const cancelBusyId = ref(null)
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
  if (Number.isNaN(n)) return String(code)
  const zh = SF_ORDER_STATUS_ZH[n]
  if (zh) return `${zh}（${n}）`
  return `未识别（${n}）`
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
    await fetchList()
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
          <el-button plain class="sf-monitor-refresh" :loading="loading" @click="fetchList">
            <span class="sf-monitor-refresh-inner">
              <RefreshCw v-if="!loading" :size="16" stroke-width="2" />
              刷新
            </span>
          </el-button>
        </div>
      </div>

      <AdminTable variant="members" :data="items" :loading="loading" row-key="id" empty-text="暂无推单记录">
        <el-table-column prop="delivery_date" label="业务日" width="118" />
        <el-table-column label="顺丰单号" min-width="120" class-name="td-mono">
          <template #default="{ row }">{{ row.sf_order_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="会员姓名" min-width="132" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberNames(row) }}</template>
        </el-table-column>
        <el-table-column label="会员手机" min-width="132" class-name="td-mono" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberPhones(row) }}</template>
        </el-table-column>
        <el-table-column label="创单状态" width="110">
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
        <el-table-column label="操作" width="118" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canCancelSfRow(row)"
              type="danger"
              plain
              size="small"
              :loading="cancelBusyId === row.id"
              :disabled="loading"
              @click="onCancelSf(row)"
            >
              取消配送
            </el-button>
            <span v-else class="sf-monitor-op-muted">—</span>
          </template>
        </el-table-column>
      </AdminTable>

      <div v-if="total > 0" class="sf-monitor-pager">
        <el-button plain size="small" :disabled="loading || page <= 1" @click="goPrev">上一页</el-button>
        <span class="sf-monitor-page-meta">{{ page }} / {{ totalPages }} · 共 {{ total }} 条</span>
        <el-button plain size="small" :disabled="loading || page >= totalPages" @click="goNext">下一页</el-button>
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
.sf-monitor-refresh-inner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
.sf-monitor-op-muted {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.42);
}
</style>
