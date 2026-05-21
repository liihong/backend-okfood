<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { AlertTriangle, RefreshCw, Search } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { parseApiDateTimeBeijing } from '../utils/beijingDateTime.js'

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

/** 展示用：将 Date 格式化为上海日历的 `MM-DD HH:mm` */
function formatShanghaiMdHm(d) {
  if (Number.isNaN(d.getTime())) return null
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
  if (!mo || !da) return null
  return `${mo}-${da} ${hr}:${mi}`
}

/** 下单时间：库内为北京时间 naive，统一解析后按上海展示为 `MM-DD HH:mm` */
function formatOrderCreatedAtMdHm(iso) {
  if (iso == null || iso === '') return '—'
  const s = String(iso).trim()
  const shown = formatShanghaiMdHm(parseApiDateTimeBeijing(s))
  if (shown) return shown
  const x = s.replace('T', ' ')
  const m = x.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
  return m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : x.slice(0, 16)
}

const activeTab = ref('single')
const orderDate = ref(todayShanghaiStr())
const searchQuery = ref('')
const singlePayFilter = ref('')
/** 单次点餐：配送维度筛选，对应接口 delivery_phase */
const singleDeliveryFilter = ref('')
const mallPayFilter = ref('')
const loading = ref(false)
const singleItems = ref([])
const singleTotal = ref(0)
const mallItems = ref([])
const mallTotal = ref(0)
const page = ref(1)
const pageSize = ref(20)

/** @type {import('vue').Ref<Array<Record<string, unknown>>>} */
const courierOptions = ref([])
const assignOpen = ref(false)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const assignOrder = ref(null)
const assignCourierId = ref('')
const dispatchLoadingId = ref(0)
const refundLoadingId = ref(0)
const refundOpen = ref(false)
/** @type {import('vue').Ref<{ kind: 'single' | 'mall'; row: Record<string, unknown> } | null>} */
const refundTarget = ref(null)
const syncDeliveryLoading = ref(false)
const syncSfLoadingId = ref(0)

const refundDialogMeta = computed(() => {
  const t = refundTarget.value
  if (!t) return null
  const row = t.row
  const amt = row.amount_yuan
  const amountStr = amt != null && amt !== '' ? String(amt) : '—'
  if (t.kind === 'single') {
    return {
      orderType: '单次点餐',
      orderId: row.id,
      amountStr,
      sub: '全额退回支付用户微信零钱',
      tip: '退款成功后订单状态将变为「已退款」，操作不可撤销。',
    }
  }
  return {
    orderType: '商城卡包',
    orderId: row.id,
    amountStr,
    sub: '全额退回支付用户微信零钱',
    tip: '退款成功后订单状态将变为「已退款」。若工单曾同步会员次数/配额，请先人工处理会员权益。',
  }
})

const totalPages = computed(() => {
  const t = activeTab.value === 'single' ? singleTotal.value : mallTotal.value
  return Math.max(1, Math.ceil((t || 0) / pageSize.value))
})

function canDispatchActions(row) {
  if (!row || row.pay_status !== '已支付') return false
  return String(row.fulfillment_status || '').toLowerCase() === 'pending'
}

async function loadCouriers() {
  if (!adminAccessToken.value) return
  try {
    const rows = await apiJson('/api/admin/couriers', {}, { auth: true })
    courierOptions.value = Array.isArray(rows) ? rows : []
  } catch {
    courierOptions.value = []
  }
}

async function onPushSfRetail(row) {
  if (!canDispatchActions(row)) {
    showToast('仅「待发货」且已支付订单可推送顺丰', 'error')
    return
  }
  if (row.store_pickup) {
    showToast('门店自提订单不发顺丰到家；可用「门店自配送」指派', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将使用门店设置中的「零售推顺丰店铺ID」向顺丰创单（与智能配送大表所用顺丰店铺编号独立）。是否继续？',
      '推送到顺丰',
      { type: 'warning', confirmButtonText: '确定推送', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  dispatchLoadingId.value = Number(row.id)
  try {
    const r = await apiJson(
      `/api/admin/orders/single-meals/${row.id}/dispatch/sf-retail`,
      { method: 'POST' },
      { auth: true },
    )
    const msg =
      r && typeof r === 'object' && typeof r.message === 'string' ? r.message : '已提交顺丰'
    showToast(msg, 'success')
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '推送失败', 'error')
  } finally {
    dispatchLoadingId.value = 0
  }
}

async function onPushUu(row) {
  if (!canDispatchActions(row)) {
    showToast('仅「待发货」且已支付订单可操作', 'error')
    return
  }
  dispatchLoadingId.value = Number(row.id)
  try {
    await apiJson(
      `/api/admin/orders/single-meals/${row.id}/dispatch/uu`,
      { method: 'POST' },
      { auth: true },
    )
    showToast('UU 已受理', 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    if (status === 501) {
      ElMessage.warning(e instanceof Error ? e.message : 'UU 跑腿尚未对接')
      return
    }
    showToast(e instanceof Error ? e.message : '请求失败', 'error')
  } finally {
    dispatchLoadingId.value = 0
  }
}

function openAssignCourier(row) {
  if (!canDispatchActions(row)) {
    showToast('仅「待发货」订单可指派门店配送员', 'error')
    return
  }
  assignOrder.value = row
  assignCourierId.value = row.courier_id ? String(row.courier_id) : ''
  assignOpen.value = true
  void loadCouriers()
}

function handleDispatchCommand(cmd, row) {
  if (cmd === 'sf') void onPushSfRetail(row)
  else if (cmd === 'uu') void onPushUu(row)
  else if (cmd === 'courier') openAssignCourier(row)
}

function canRefundWechatSingle(row) {
  if (!row || row.pay_status !== '已支付') return false
  return String(row.pay_channel || '').trim() === '微信'
}

function canRefundWechatMall(row) {
  if (!row || row.pay_status !== '已缴') return false
  if (row.applied_to_member) return false
  return String(row.pay_channel || '').trim() === '微信'
}

function openRefundWechat(row, kind) {
  if (kind === 'single') {
    if (!canRefundWechatSingle(row)) {
      showToast('仅「已支付」且微信支付的单次订单可原路退款', 'error')
      return
    }
  } else if (!canRefundWechatMall(row)) {
    showToast('仅「已缴」、微信支付且未同步入账的卡包订单可原路退款', 'error')
    return
  }
  refundTarget.value = { kind, row }
  refundOpen.value = true
}

function onRefundWechatSingle(row) {
  openRefundWechat(row, 'single')
}

function onRefundWechatMall(row) {
  openRefundWechat(row, 'mall')
}

async function submitRefundWechat() {
  const t = refundTarget.value
  if (!t) return
  const { kind, row } = t
  const id = Number(row.id)
  refundLoadingId.value = id
  const path =
    kind === 'single'
      ? `/api/admin/orders/single-meals/${id}/refund/wechat`
      : `/api/admin/orders/mall-card/${id}/refund/wechat`
  try {
    const r = await apiJson(path, { method: 'POST' }, { auth: true })
    const msg =
      r && typeof r === 'object' && typeof r.message === 'string' ? r.message : '退款已受理'
    showToast(msg, 'success')
    refundOpen.value = false
    refundTarget.value = null
    if (kind === 'single') await fetchSingleMeals()
    else await fetchMallCardOrders()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '退款失败', 'error')
  } finally {
    refundLoadingId.value = 0
  }
}

async function submitAssignCourier() {
  const row = assignOrder.value
  const cid = String(assignCourierId.value || '').trim()
  if (!row || !cid) {
    showToast('请选择配送员', 'error')
    return
  }
  try {
    await apiJson(
      `/api/admin/orders/single-meals/${row.id}/dispatch/store-courier`,
      {
        method: 'POST',
        body: JSON.stringify({ courier_id: cid }),
      },
      { auth: true },
    )
    showToast('已指派配送员', 'success')
    assignOpen.value = false
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '指派失败', 'error')
  }
}

function singlePayClass(s) {
  if (s === '已支付') return 'member-pill member-pill--emerald'
  if (s === '已退款') return 'member-pill member-pill--rose'
  return 'member-pill member-pill--amber'
}

function mallPayClass(s) {
  if (s === '已缴') return 'member-pill member-pill--emerald'
  if (s === '已退款') return 'member-pill member-pill--rose'
  return 'member-pill member-pill--amber'
}

/** 单次点餐订单状态（与接口 fulfillment_status 对应，商城常用口径） */
const SINGLE_ORDER_STATUS_ZH = {
  pending: '待发货',
  accepted: '配送中',
  delivered: '已完成',
  sf_cancelled: '顺丰取消',
}

/** 门店自提且未核销完成前：pending 展示为待自提 */
function singleOrderStatusLabelZh(row) {
  if (!row) return '—'
  const s = row.fulfillment_status
  if (s == null || s === '') return '—'
  const k = String(s).trim().toLowerCase()
  if (k === 'pending' && row.store_pickup) return '待自提'
  return SINGLE_ORDER_STATUS_ZH[k] ?? String(s).trim()
}

function singleOrderStatusClass(row) {
  const x = ((row && row.fulfillment_status) || '').toLowerCase()
  if (x === 'delivered') return 'member-pill member-pill--emerald'
  if (x === 'sf_cancelled') return 'member-pill member-pill--rose'
  if (x === 'accepted') return 'member-pill member-pill--sky'
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
    if (pf === '未支付' || pf === '已支付' || pf === '已退款') q.set('pay_status', pf)
    const ds = String(singleDeliveryFilter.value ?? '').trim()
    if (ds === 'awaiting' || ds === 'delivered') q.set('delivery_phase', ds)
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
    if (pf === '未缴' || pf === '已缴' || pf === '已退款') q.set('pay_status', pf)
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

watch([orderDate, singlePayFilter, singleDeliveryFilter, mallPayFilter, pageSize, activeTab], () => {
  page.value = 1
  void fetchActive()
})

function canSyncSfSingle(row) {
  if (!row || row.pay_status !== '已支付' || row.store_pickup) return false
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  return f === 'pending' || f === 'accepted'
}

async function onSyncSfSingle(row) {
  if (!adminAccessToken.value || !row?.id) return
  syncSfLoadingId.value = Number(row.id)
  try {
    /** @type {Record<string, unknown>} */
    const d = await apiJson(
      `/api/admin/orders/single-meals/${row.id}/sync-delivered-from-sf-monitor`,
      { method: 'POST' },
      { auth: true },
    )
    const msg = typeof d?.msg === 'string' ? d.msg : '已同步'
    showToast(msg, 'success')
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '同步失败', 'error')
  } finally {
    syncSfLoadingId.value = 0
  }
}

async function onSyncDeliveryStatus() {
  if (!adminAccessToken.value || activeTab.value !== 'single') return
  const d0 = String(orderDate.value || '').trim() || todayShanghaiStr()
  try {
    await ElMessageBox.confirm(
      `将 ${d0} 单次点餐中，顺丰监控已为「妥投」或「取消/撤单」但未回写系统的订单，同步为「已完成」或「顺丰取消」。是否继续？`,
      '同步订单状态',
      { type: 'info', confirmButtonText: '开始同步', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  syncDeliveryLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('order_date', d0)
    q.set('max_orders', '500')
    /** @type {Record<string, unknown>} */
    const d = await apiJson(
      `/api/admin/orders/daily/single-meals/sync-delivery-status?${q.toString()}`,
      { method: 'POST' },
      { auth: true },
    )
    const msg = typeof d?.summary === 'string' ? d.summary : '同步已完成'
    showToast(msg, 'success')
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '同步失败', 'error')
  } finally {
    syncDeliveryLoading.value = false
  }
}

onMounted(() => {
  void loadCouriers()
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
       <button v-if="activeTab === 'single'" type="button" class="btn-sm orders-manage-sync-delivery"
          :disabled="syncDeliveryLoading || loading" @click="onSyncDeliveryStatus">
          {{ syncDeliveryLoading ? '同步中…' : '同步订单状态' }}
        </button>
      </div>

      <el-tabs v-model="activeTab" class="orders-manage-tabs">
        <el-tab-pane label="单次点餐" name="single">
         <div class="orders-manage-tab-bar orders-manage-tab-bar--filters">
            <div class="orders-filter-el">
              <span class="orders-filter-el-label">支付</span>
              <el-select v-model="singlePayFilter" placeholder="全部" clearable class="orders-filter-el-select">
                <el-option label="全部" value="" />
                <el-option label="未支付" value="未支付" />
                <el-option label="已支付" value="已支付" />
                <el-option label="已退款" value="已退款" />
              </el-select>
            </div>
           <div class="orders-filter-el">
              <span class="orders-filter-el-label">配送</span>
              <el-select v-model="singleDeliveryFilter" placeholder="全部" clearable
                class="orders-filter-el-select orders-filter-el-select--wide">
                <el-option label="全部" value="" />
                <el-option label="待配送" value="awaiting" />
                <el-option label="已配送" value="delivered" />
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
              <template #default="{ row }">{{ formatOrderCreatedAtMdHm(row.created_at) }}</template>
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
           <el-table-column label="份数" width="80" align="center">
              <template #default="{ row }">{{ row.quantity ?? '—' }}</template>
            </el-table-column>
           <el-table-column label="供餐日" width="120" class-name="td-mono">
              <template #default="{ row }">{{ row.delivery_date || '—' }}</template>
            </el-table-column>
           <el-table-column label="金额" width="90" align="right" class-name="td-mono">
              <template #default="{ row }">{{ row.amount_yuan ?? '—' }}</template>
            </el-table-column>
           <el-table-column label="支付" width="100" class-name="co-nowrap">
              <template #default="{ row }">
                <span :class="singlePayClass(row.pay_status)">{{ row.pay_status || '—' }}</span>
              </template>
            </el-table-column>
           <el-table-column label="订单状态" width="100" class-name="co-nowrap">
              <template #default="{ row }">
               <span :class="singleOrderStatusClass(row)">{{ singleOrderStatusLabelZh(row) }}</span>
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
            <el-table-column label="操作" width="320" fixed="right" align="center">
              <template #default="{ row }">
                <div class="orders-op-btns">
                  <el-button
                    v-if="canSyncSfSingle(row)"
                    type="success"
                    size="small"
                    plain
                    :loading="syncSfLoadingId === row.id"
                    @click="onSyncSfSingle(row)"
                  >
                    同步顺丰
                  </el-button>
                  <el-dropdown trigger="click" @command="(cmd) => handleDispatchCommand(cmd, row)">
                    <el-button
                      type="primary"
                      size="small"
                      :loading="dispatchLoadingId === row.id"
                      :disabled="!canDispatchActions(row)"
                    >
                      配送操作
                    </el-button>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item command="sf" :disabled="!canDispatchActions(row) || row.store_pickup">
                          推送到顺丰
                        </el-dropdown-item>
                        <el-dropdown-item command="uu" :disabled="!canDispatchActions(row)">推送到 UU</el-dropdown-item>
                        <el-dropdown-item command="courier" :disabled="!canDispatchActions(row)">
                          门店自配送
                        </el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                  <el-button
                    type="warning"
                    size="small"
                    plain
                    :disabled="!canRefundWechatSingle(row)"
                    :loading="refundLoadingId === row.id"
                    @click="onRefundWechatSingle(row)"
                  >
                    微信退款
                  </el-button>
                </div>
              </template>
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
                <el-option label="已退款" value="已退款" />
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
              <template #default="{ row }">{{ formatOrderCreatedAtMdHm(row.created_at) }}</template>
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
            <el-table-column label="操作" width="116" fixed="right" align="center">
              <template #default="{ row }">
                <el-button
                  type="warning"
                  size="small"
                  plain
                  :disabled="!canRefundWechatMall(row)"
                  :loading="refundLoadingId === row.id"
                  @click="onRefundWechatMall(row)"
                >
                  微信退款
                </el-button>
              </template>
            </el-table-column>
            <el-table-column label="配送" width="108" align="center" class-name="co-nowrap">
              <template #default>
                <span class="orders-mall-no-dispatch">卡包无配送</span>
              </template>
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

    <el-dialog
      v-model="refundOpen"
      width="440px"
      class="orders-refund-dialog"
      destroy-on-close
      align-center
      :close-on-click-modal="!refundLoadingId"
      :close-on-press-escape="!refundLoadingId"
      @closed="refundTarget = null"
    >
      <template #header>
        <div class="orders-refund-header">
          <span class="orders-refund-header-icon" aria-hidden="true">
            <AlertTriangle :size="20" :stroke-width="2.25" />
          </span>
          <span class="orders-refund-header-title">微信原路退款</span>
        </div>
      </template>
      <div v-if="refundDialogMeta" class="orders-refund-body">
        <p class="orders-refund-lead">请确认以下退款信息后再提交</p>
        <dl class="orders-refund-card">
          <div class="orders-refund-row">
            <dt>订单类型</dt>
            <dd>{{ refundDialogMeta.orderType }}</dd>
          </div>
          <div class="orders-refund-row">
            <dt>订单编号</dt>
            <dd>#{{ refundDialogMeta.orderId }}</dd>
          </div>
          <div class="orders-refund-row orders-refund-row--amount">
            <dt>退款金额</dt>
            <dd>
              <span class="orders-refund-amount">¥ {{ refundDialogMeta.amountStr }}</span>
              <span class="orders-refund-amount-sub">{{ refundDialogMeta.sub }}</span>
            </dd>
          </div>
        </dl>
        <p class="orders-refund-tip">
          <AlertTriangle :size="14" :stroke-width="2.25" class="orders-refund-tip-icon" aria-hidden="true" />
          <span>{{ refundDialogMeta.tip }}</span>
        </p>
      </div>
      <template #footer>
        <div class="orders-refund-footer">
          <el-button :disabled="!!refundLoadingId" @click="refundOpen = false">取消</el-button>
          <el-button type="danger" :loading="!!refundLoadingId" @click="submitRefundWechat">
            确定退款
          </el-button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="assignOpen" title="门店自配送 · 指派配送员" width="420px" destroy-on-close>
      <template v-if="assignOrder">
        <p class="orders-assign-hint">
          订单 #{{ assignOrder.id }} · {{ (assignOrder.member_name || '').trim() || '—' }}
        </p>
        <el-select
          v-model="assignCourierId"
          filterable
          placeholder="选择系统内配送员"
          class="orders-assign-select"
        >
          <el-option
            v-for="c in courierOptions"
            :key="c.courier_id"
            :label="`${(c.name || '').trim() || c.courier_id}（${c.courier_id}）`"
            :value="c.courier_id"
            :disabled="c.is_active === false"
          />
        </el-select>
      </template>
      <template #footer>
        <el-button @click="assignOpen = false">取消</el-button>
        <el-button type="primary" @click="submitAssignCourier">确定</el-button>
      </template>
    </el-dialog>
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
.orders-manage-tab-bar--filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}

.orders-filter-el-select--wide {
  width: 152px;
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
.orders-assign-hint {
  margin: 0 0 0.75rem;
  font-size: 0.9rem;
  color: #334155;
}
.orders-assign-select {
  width: 100%;
}
.orders-mall-no-dispatch {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}
.orders-op-btns {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  max-width: 236px;
}

.orders-refund-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding: 1.15rem 1.35rem 0.5rem;
}
.orders-refund-dialog :deep(.el-dialog__body) {
  padding: 0.35rem 1.35rem 0.25rem;
}
.orders-refund-dialog :deep(.el-dialog__footer) {
  padding: 0.75rem 1.35rem 1.15rem;
}
.orders-refund-header {
  display: flex;
  align-items: center;
  gap: 0.65rem;
}
.orders-refund-header-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.25rem;
  height: 2.25rem;
  border-radius: 50%;
  background: #fff7ed;
  color: #ea580c;
  flex-shrink: 0;
}
.orders-refund-header-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.01em;
}
.orders-refund-body {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.orders-refund-lead {
  margin: 0;
  font-size: 0.875rem;
  color: #64748b;
  line-height: 1.5;
}
.orders-refund-card {
  margin: 0;
  padding: 0.85rem 1rem;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}
.orders-refund-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.4rem 0;
}
.orders-refund-row + .orders-refund-row {
  border-top: 1px solid #e2e8f0;
}
.orders-refund-row dt {
  margin: 0;
  font-size: 0.8125rem;
  color: #64748b;
  font-weight: 500;
  white-space: nowrap;
}
.orders-refund-row dd {
  margin: 0;
  text-align: right;
  font-size: 0.875rem;
  color: #0f172a;
  font-weight: 500;
}
.orders-refund-row--amount dd {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.2rem;
}
.orders-refund-amount {
  font-size: 1.25rem;
  font-weight: 700;
  color: #be123c;
  letter-spacing: 0.02em;
}
.orders-refund-amount-sub {
  font-size: 0.75rem;
  font-weight: 400;
  color: #94a3b8;
}
.orders-refund-tip {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  margin: 0;
  padding: 0.65rem 0.75rem;
  border-radius: 8px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  font-size: 0.8125rem;
  line-height: 1.55;
  color: #92400e;
}
.orders-refund-tip-icon {
  flex-shrink: 0;
  margin-top: 0.15rem;
  color: #d97706;
}
.orders-refund-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
