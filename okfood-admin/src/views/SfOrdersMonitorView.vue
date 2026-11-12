<script setup>
defineOptions({ name: 'SfOrdersMonitorView' })
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { RefreshCw } from 'lucide-vue-next'
import { apiBlob, apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { toastSfPushBatchOutcome, toastSfPushError } from '../utils/sfPushMessages.js'

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
const fulfillBusyId = ref(null)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
/** 分页：每页条数可切换（与接口 page_size 一致） */
const pageSizeOptions = [10, 20, 50, 100]
const deliveryDate = ref(todayShanghaiStr())
/** 回调订单状态筛：空=全部；unknown=尚无回调状态；其余为顺丰 order_status 数值字符串 */
const orderStatusFilter = ref('')
/** 创单状态：空=全部；ok=成功未取消；fail=失败；cancelled=取消订单 */
const createStatusFilter = ref('')
const memberPhoneFilter = ref('')
const sfOrderIdFilter = ref('')
/** 订单类别：空=全部；lunch/dinner=餐段；其余为 push_kind */
const pushKindFilter = ref('')

const createStatusOptions = [
  { value: '', label: '全部创单' },
  { value: 'ok', label: '创单成功（未取消）' },
  { value: 'fail', label: '创单失败' },
  { value: 'cancelled', label: '取消订单' },
]

const pushKindOptions = [
  { value: '', label: '全部类别' },
  { value: 'lunch', label: '午餐' },
  { value: 'dinner', label: '晚餐' },
  { value: 'delivery_sheet', label: '午餐大表' },
  { value: 'dinner_delivery_sheet', label: '晚餐大表' },
  { value: 'single_meal_retail', label: '单次零售' },
]

const activeCategoryLabel = computed(() => {
  const opt = pushKindOptions.find((o) => o.value === (pushKindFilter.value || ''))
  return opt?.label || '全部类别'
})

function applyCategoryFilterToQuery(q) {
  const pk = (pushKindFilter.value || '').trim()
  if (pk === 'lunch' || pk === 'dinner') {
    q.set('meal_period', pk)
  } else if (pk) {
    q.set('push_kind', pk)
  }
}

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
    applyCategoryFilterToQuery(q)
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
  if (cs === 'ok' || cs === 'fail' || cs === 'cancelled') q.set('sf_create_status', cs)
  const ph = (memberPhoneFilter.value || '').trim()
  if (ph) q.set('member_phone', ph)
  const oid = (sfOrderIdFilter.value || '').trim()
  if (oid) q.set('sf_order_id', oid)
  applyCategoryFilterToQuery(q)
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

function onPushKindChange() {
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

const meterKicker = computed(() => {
  const date = (deliveryDate.value || '').trim() || '全部日期'
  return `${activeCategoryLabel.value} · ${date}`
})

const meterStats = computed(() => {
  const s = pushStats.value
  if (!s) {
    return { total: '—', sheet: '—', retail: '—', success: '—', failed: '—', cancelled: '—' }
  }
  return {
    total: statText(s.total),
    sheet: statText(s.delivery_sheet?.total),
    retail: statText(s.single_meal_retail?.total),
    success: statText(s.success),
    failed: statText(s.failed),
    cancelled: statText(s.cancelled != null ? s.cancelled : 0),
  }
})

/** 汇总数字不含手机、运单、回调筛选；点进去时清掉这三项，列表才对得上格子里的数 */
function clearMeterTextFilters() {
  orderStatusFilter.value = ''
  memberPhoneFilter.value = ''
  sfOrderIdFilter.value = ''
}

function onMeterKind(kind) {
  if (loading.value || statsLoading.value) return
  const same = pushKindFilter.value === kind && !createStatusFilter.value
  pushKindFilter.value = same ? '' : kind
  createStatusFilter.value = ''
  clearMeterTextFilters()
  page.value = 1
  void refreshMonitor()
}

function onMeterCreate(status) {
  if (loading.value || statsLoading.value) return
  createStatusFilter.value = createStatusFilter.value === status ? '' : status
  clearMeterTextFilters()
  page.value = 1
  void refreshMonitor()
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
      a.download = `顺丰订单监控_${d}_${activeCategoryLabel.value}.xlsx`
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
  const label = row?.sf_create_status_label
  if (label) return label
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
  merchant_cancel: '商家取消配送',
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

/** 回调类型拆成中文和原始 kind，表格里分两行，避免和运单号一样被折断 */
function callbackKindParts(kind) {
  const k = String(kind || '').trim()
  if (!k) return { label: '—', code: '' }
  const zh = SF_CALLBACK_KIND_ZH[k]
  return zh ? { label: zh, code: k } : { label: k, code: '' }
}

function formatMonitorTime(raw) {
  if (!raw) return '—'
  return String(raw).replace('T', ' ').slice(0, 19)
}

/** 订单类别胶囊色：零售 / 午餐大表 / 晚餐大表 */
function pushKindTone(row) {
  const k = String(row?.push_kind || '').trim()
  if (k === 'single_meal_retail') return 'retail'
  if (k === 'dinner_delivery_sheet') return 'dinner'
  if (k === 'delivery_sheet' || k === '') return 'lunch'
  return 'muted'
}

function sfCreateTone(row) {
  const label = String(row?.sf_create_status_label || '')
  if (label.includes('取消')) return 'muted'
  const code = row?.error_code
  if (code === 0 || code === '0') return 'ok'
  if (code === undefined || code === null) return 'muted'
  return 'rose'
}

function callbackTone(code) {
  if (code === undefined || code === null || code === '') return 'muted'
  const n = Number(code)
  if (Number.isNaN(n)) return 'muted'
  if (n === 17) return 'done'
  if (n === 10 || n === 12 || n === 15) return 'go'
  if (n === 2 || n === 22 || n === 31 || n === 91) return 'rose'
  return 'muted'
}

function statText(raw) {
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  return Number.isFinite(n) ? String(n) : '—'
}

/** 监控列表：系统会员姓名 / 手机（到家已按会员拆单；历史同址合并单仍可能一人以上） */
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
  if (row?.merchant_cancel_requested_at) return false
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

/** 大表合并：创单成功且已取消，可按当前配送大表重新推单 */
function canRedispatchSfRow(row) {
  const code = row?.error_code
  if (code !== 0 && code !== '0') return false
  const kind = String(row?.push_kind || '').trim()
  if (kind && kind !== 'delivery_sheet' && kind !== 'dinner_delivery_sheet') return false
  if (row?.merchant_cancel_requested_at) return true
  const stRaw = row?.sf_callback_order_status
  if (stRaw !== undefined && stRaw !== null && stRaw !== '') {
    const stNum = Number(stRaw)
    if (!Number.isNaN(stNum) && [2, 22].includes(stNum)) return true
  }
  return false
}

/** 创单成功且顺丰回调已为妥投(17)，可补跑标记送达/扣次 */
function canApplyFulfillmentSfRow(row) {
  const code = row?.error_code
  if (code !== 0 && code !== '0') return false
  if (row?.merchant_cancel_requested_at) return false
  const stRaw = row?.sf_callback_order_status
  if (stRaw === undefined || stRaw === null || stRaw === '') return false
  const stNum = Number(stRaw)
  return !Number.isNaN(stNum) && stNum === 17
}

async function onRetrySf(row) {
  const isRedispatch = canRedispatchSfRow(row)
  try {
    await ElMessageBox.confirm(
      isRedispatch
        ? '该订单此前顺丰侧已取消，将按当前配送大表数据重新向顺丰创单。是否继续？'
        : '将按当前配送大表数据对该停靠点重新发起顺丰创单（仅适用于创单失败记录）。',
      isRedispatch ? '重新推单' : '重试推单',
      {
        confirmButtonText: isRedispatch ? '确认重新推单' : '确认重试',
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
      toastSfPushError(res.message || '重试未成功', showToast)
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
    toastSfPushError(e instanceof Error ? e.message : '重试失败', showToast)
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

async function onApplyFulfillmentSf(row) {
  try {
    await ElMessageBox.confirm(
      '将按该停靠点对订阅会员标记送达并扣次数（与配送大表一致）；已扣次会员不会重复扣减。',
      '补标送达',
      {
        confirmButtonText: '确认',
        cancelButtonText: '关闭',
        type: 'info',
        distinguishCancelAndClose: true,
      },
    )
  } catch {
    return
  }
  fulfillBusyId.value = row.id
  try {
    const res = await apiJson(
      `/api/admin/delivery-sf/pushes/${row.id}/apply-fulfillment`,
      { method: 'POST', body: JSON.stringify({}) },
      { auth: true },
    )
    showToast((res && res.summary) || '已处理', 'success')
    await refreshMonitor()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '补标失败', 'error')
  } finally {
    fulfillBusyId.value = null
  }
}

const route = useRoute()

/** 包裹表格，用来量剩余高度；只让表体滚，表头和底部分页留在视口里 */
const sfTableHostRef = ref(null)
const sfTableScrollHeight = ref(400)
/** @type {ResizeObserver | null} */
let sfTableResizeObserver = null

function updateSfTableHeight() {
  const el = sfTableHostRef.value
  if (!el) return
  const h = Math.floor(el.getBoundingClientRect().height)
  if (h >= 160) sfTableScrollHeight.value = h
}

onMounted(() => {
  const qDate = String(route.query.delivery_date || '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(qDate)) {
    deliveryDate.value = qDate
  }
  const qCreate = String(route.query.sf_create_status || '').trim().toLowerCase()
  if (qCreate === 'fail' || qCreate === 'failed') {
    createStatusFilter.value = 'fail'
  }
  void refreshMonitor()
  void nextTick(() => {
    updateSfTableHeight()
    sfTableResizeObserver = new ResizeObserver(() => {
      updateSfTableHeight()
    })
    if (sfTableHostRef.value) sfTableResizeObserver.observe(sfTableHostRef.value)
  })
})

onUnmounted(() => {
  sfTableResizeObserver?.disconnect()
  sfTableResizeObserver = null
})
</script>

<template>
  <section class="tab-content animate-up sf-orders-monitor page-content-shell members-view-fill">
    <header class="sf-head">
      <div>
        <p class="sf-crumb">配送管理 / <b>顺丰订单监控</b></p>
        <h2 class="sf-head__title">顺丰订单监控</h2>
        <p class="sf-head__sub">
          顺丰「订单完成」或妥投完单（17）通过后，按停靠点给订阅会员标记送达并扣次数；单次零售只更新履约状态。
        </p>
      </div>
      <div class="sf-head__actions">
        <button type="button" class="sf-refresh" :disabled="loading || statsLoading" @click="refreshMonitor">
          <RefreshCw :size="15" stroke-width="2" :class="{ 'sf-refresh__spin': loading || statsLoading }" />
          刷新
        </button>
        <button
          type="button"
          class="sf-export"
          :disabled="exporting || loading || !(deliveryDate || '').trim()"
          @click="exportExcel"
        >
          {{ exporting ? '导出中…' : '导出 Excel' }}
        </button>
      </div>
    </header>

    <section class="sf-meter" aria-label="业务日汇总">
      <div class="sf-meter__main">
        <span>{{ meterKicker }}</span>
        <strong>{{ meterStats.total }}<em> 单</em></strong>
      </div>
      <button
        type="button"
        class="sf-cell"
        :class="{ 'is-on': pushKindFilter === 'delivery_sheet' && !createStatusFilter }"
        :disabled="loading || statsLoading"
        @click="onMeterKind('delivery_sheet')"
      >
        <small>大表</small>
        <b>{{ meterStats.sheet }}</b>
      </button>
      <button
        type="button"
        class="sf-cell"
        :class="{ 'is-on': pushKindFilter === 'single_meal_retail' && !createStatusFilter }"
        :disabled="loading || statsLoading"
        @click="onMeterKind('single_meal_retail')"
      >
        <small>单次零售</small>
        <b>{{ meterStats.retail }}</b>
      </button>
      <button
        type="button"
        class="sf-cell sf-cell--ok"
        :class="{ 'is-on': createStatusFilter === 'ok' }"
        :disabled="loading || statsLoading"
        @click="onMeterCreate('ok')"
      >
        <small>创单成功</small>
        <b>{{ meterStats.success }}</b>
      </button>
      <button
        type="button"
        class="sf-cell sf-cell--rose"
        :class="{ 'is-on': createStatusFilter === 'fail' }"
        :disabled="loading || statsLoading"
        @click="onMeterCreate('fail')"
      >
        <small>创单失败</small>
        <b>{{ meterStats.failed }}</b>
      </button>
      <button
        type="button"
        class="sf-cell"
        :class="{ 'is-on': createStatusFilter === 'cancelled' }"
        :disabled="loading || statsLoading"
        @click="onMeterCreate('cancelled')"
      >
        <small>已取消</small>
        <b>{{ meterStats.cancelled }}</b>
      </button>
    </section>

    <section class="sf-card table-container table-container--members-fill" aria-label="推单列表">
      <div class="sf-filters">
        <label class="sf-field sf-field--date">
          <span>业务日</span>
          <el-date-picker
            v-model="deliveryDate"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="全部日期"
            :clearable="true"
            :disabled="loading"
            @change="onDateChange"
          />
        </label>
        <label class="sf-field sf-field--cat">
          <span>订单类别</span>
          <el-select
            v-model="pushKindFilter"
            placeholder="全部类别"
            :disabled="loading"
            clearable
            @change="onPushKindChange"
          >
            <el-option
              v-for="opt in pushKindOptions"
              :key="opt.value === '' ? '_pk_all' : opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </label>
        <label class="sf-field sf-field--create">
          <span>创单状态</span>
          <el-select
            v-model="createStatusFilter"
            placeholder="全部创单"
            :disabled="loading"
            clearable
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
        <label class="sf-field sf-field--phone">
          <span>会员手机</span>
          <el-input
            v-model="memberPhoneFilter"
            clearable
            placeholder="后几位或完整号"
            :disabled="loading"
            @change="onTextFilterChange"
          />
        </label>
        <label class="sf-field sf-field--sf">
          <span>顺丰单号</span>
          <el-input
            v-model="sfOrderIdFilter"
            clearable
            placeholder="运单号包含"
            :disabled="loading"
            @change="onTextFilterChange"
          />
        </label>
        <label class="sf-field sf-field--cb">
          <span>回调订单状态</span>
          <el-select
            v-model="orderStatusFilter"
            placeholder="全部回调状态"
            :disabled="loading"
            clearable
            filterable
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
      </div>

      <div ref="sfTableHostRef" class="members-table-host sf-table-host">
      <AdminTable
        class="sf-table members-el-table-body-scroll"
        variant="default"
        :stripe="false"
        :border="false"
        :height="sfTableScrollHeight"
        :data="items"
        :loading="loading"
        row-key="id"
        empty-text="暂无推单记录"
      >
        <el-table-column type="index" :index="tableRowIndex" label="序号" width="64" align="center" class-name="sf-num" />
        <el-table-column prop="delivery_date" label="业务日" width="118" class-name="sf-day" />
        <el-table-column label="订单类别" width="108">
          <template #default="{ row }">
            <span class="sf-cat" :class="`sf-cat--${pushKindTone(row)}`">{{ row.push_kind_label || row.push_kind || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="顺丰单号" min-width="156" class-name="sf-mono">
          <template #default="{ row }">{{ row.sf_order_id || '—' }}</template>
        </el-table-column>
        <el-table-column label="会员姓名" min-width="96" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberNames(row) }}</template>
        </el-table-column>
        <el-table-column label="会员手机" min-width="132" class-name="sf-mono" show-overflow-tooltip>
          <template #default="{ row }">{{ formatMemberPhones(row) }}</template>
        </el-table-column>
        <el-table-column label="创单状态" width="112">
          <template #default="{ row }">
            <span class="sf-dot" :class="`sf-dot--${sfCreateTone(row)}`"><i></i>{{ sfStatusLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="回调订单状态" min-width="188">
          <template #default="{ row }">
            <span class="sf-st" :class="`sf-st--${callbackTone(row.sf_callback_order_status)}`">{{ sfOrderStatusLabel(row.sf_callback_order_status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近回调类型" min-width="148">
          <template #default="{ row }">
            <span class="sf-kind">
              <span>{{ callbackKindParts(row.last_callback_kind).label }}</span>
              <code v-if="callbackKindParts(row.last_callback_kind).code">{{ callbackKindParts(row.last_callback_kind).code }}</code>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近回调时间" width="168" class-name="sf-mono">
          <template #default="{ row }">{{ formatMonitorTime(row.last_callback_at) }}</template>
        </el-table-column>
        <el-table-column label="创单时间" width="168" class-name="sf-mono">
          <template #default="{ row }">{{ formatMonitorTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" class-name="sf-ops-col">
          <template #default="{ row }">
            <div class="sf-ops">
              <el-button
                v-if="canApplyFulfillmentSfRow(row)"
                class="sf-act sf-act--ok"
                size="small"
                :loading="fulfillBusyId === row.id"
                :disabled="loading"
                @click="onApplyFulfillmentSf(row)"
              >
                补标送达
              </el-button>
              <el-button
                v-if="canRedispatchSfRow(row)"
                class="sf-act sf-act--retry"
                size="small"
                :loading="retryBusyId === row.id"
                :disabled="loading"
                @click="onRetrySf(row)"
              >
                重新推单
              </el-button>
              <el-button
                v-else-if="canRetrySfRow(row)"
                class="sf-act sf-act--retry"
                size="small"
                :loading="retryBusyId === row.id"
                :disabled="loading"
                @click="onRetrySf(row)"
              >
                重试推单
              </el-button>
              <el-button
                v-if="canCancelSfRow(row)"
                class="sf-act sf-act--stop"
                size="small"
                :loading="cancelBusyId === row.id"
                :disabled="loading"
                @click="onCancelSf(row)"
              >
                取消配送
              </el-button>
              <span
                v-if="!canApplyFulfillmentSfRow(row) && !canRetrySfRow(row) && !canRedispatchSfRow(row) && !canCancelSfRow(row)"
                class="sf-op-muted"
              >—</span>
            </div>
          </template>
        </el-table-column>
      </AdminTable>
      </div>

      <div v-if="adminAccessToken" class="members-pagination members-pagination--float">
        <button type="button" class="btn-sm" :disabled="loading || page <= 1 || total <= 0" @click="goPrev">
          上一页
        </button>
        <span class="members-page-meta">
          <label class="sf-pager__size">
            每页
            <el-select v-model="pageSize" :disabled="loading" aria-label="每页条数" @change="onPageSizeChange">
              <el-option v-for="n in pageSizeOptions" :key="n" :label="`${n} 条`" :value="n" />
            </el-select>
          </label>
          第 {{ page }} / {{ totalPages }} 页 · 本页 {{ items.length }} 条 · 共 {{ total }} 条
        </span>
        <button type="button" class="btn-sm" :disabled="loading || page >= totalPages || total <= 0" @click="goNext">
          下一页
        </button>
      </div>
    </section>
  </section>
</template>

<style scoped>
.sf-orders-monitor.page-content-shell {
  /* 吃满主视区，页本身不滚；只滚表体 */
  padding-bottom: 0;
  overflow: hidden;
}

.sf-orders-monitor {
  --sf-ink: #1d1f21;
  --sf-muted: #5c6670;
  --sf-faint: #8b949e;
  --sf-line: rgba(15, 23, 42, 0.06);
  --sf-ok: #1f8a5b;
  --sf-rose: #c45c66;
  --sf-rose-ink: #a33b45;
  --sf-go: #9a6232;
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
  min-width: 0;
  min-height: 0;
  color: var(--sf-ink);
}

.sf-head,
.sf-meter,
.sf-filters {
  flex-shrink: 0;
}

.sf-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 2px 0;
}

@media (max-width: 900px) {
  .sf-crumb {
    display: none;
  }
}

.sf-crumb {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--sf-faint);
}

.sf-crumb b {
  color: var(--el-color-primary-dark-2);
  font-weight: 700;
}

.sf-head__title {
  margin: 0;
  font-size: 28px;
  line-height: 1.15;
  letter-spacing: -0.03em;
  font-weight: 700;
}

.sf-head__sub {
  margin: 6px 0 0;
  max-width: 44rem;
  color: var(--sf-muted);
  font-size: 13px;
  line-height: 1.5;
}

.sf-head__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.sf-refresh,
.sf-export,
.sf-cell {
  font: inherit;
  cursor: pointer;
}

.sf-refresh,
.sf-export {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
}

.sf-refresh {
  border: 1px solid var(--sf-line);
  background: rgba(255, 255, 255, 0.9);
  color: var(--sf-ink);
}

.sf-refresh:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--el-color-primary) 45%, #fff);
  color: var(--el-color-primary-dark-2);
}

.sf-refresh:disabled,
.sf-export:disabled,
.sf-cell:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.sf-refresh__spin {
  animation: sf-spin 0.8s linear infinite;
}

@keyframes sf-spin {
  to { transform: rotate(-360deg); }
}

.sf-export {
  border: 0;
  color: #fff;
  background: var(--el-color-primary);
  box-shadow: 0 8px 18px color-mix(in srgb, var(--el-color-primary) 32%, transparent);
}

.sf-export:hover:not(:disabled) {
  background: var(--el-color-primary-dark-2);
}

.sf-meter {
  display: grid;
  grid-template-columns: 220px repeat(5, minmax(0, 1fr));
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
  overflow: hidden;
}

.sf-meter__main {
  padding: 16px 18px 14px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.55), color-mix(in srgb, var(--el-color-primary) 16%, #fff));
}

.sf-meter__main span,
.sf-cell small {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--sf-muted);
}

.sf-meter__main strong {
  display: block;
  margin-top: 4px;
  font-size: 40px;
  line-height: 0.95;
  letter-spacing: -0.045em;
  font-weight: 680;
  font-variant-numeric: tabular-nums;
}

.sf-meter__main em {
  font-style: normal;
  font-size: 13px;
  font-weight: 650;
  color: var(--sf-muted);
}

.sf-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 16px 14px 14px;
  border: 0;
  border-left: 1px solid var(--sf-line);
  background: transparent;
  text-align: left;
  color: inherit;
}

.sf-cell:hover:not(:disabled) {
  background: color-mix(in srgb, var(--el-color-primary) 7%, #fff);
}

.sf-cell.is-on {
  background: color-mix(in srgb, var(--el-color-primary) 12%, #fff);
}

.sf-cell b {
  font-size: 26px;
  letter-spacing: -0.04em;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  line-height: 1;
}

.sf-cell--ok b { color: var(--sf-ok); }
.sf-cell--rose b { color: var(--sf-rose); }

.sf-card.table-container.table-container--members-fill {
  background: #fff;
  border: 1px solid rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  box-shadow: 0 10px 30px rgba(25, 45, 55, 0.05);
}

.sf-table-host {
  min-height: 0;
}

.sf-card.table-container--members-fill > .members-pagination.members-pagination--float {
  border-radius: 0 0 24px 24px;
}

.sf-card .members-page-meta {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.sf-pager__size {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
  font-weight: 650;
  color: var(--sf-ink);
}

.sf-pager__size :deep(.el-select) {
  width: 88px;
}

.sf-pager__size :deep(.el-select__wrapper) {
  min-height: 28px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08) inset;
}

.sf-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--sf-line);
}

.sf-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.sf-field > span {
  font-size: 12px;
  font-weight: 700;
  color: var(--sf-muted);
}

.sf-field--date { width: 158px; }
.sf-field--cat { width: 140px; }
.sf-field--create { width: 176px; }
.sf-field--phone,
.sf-field--sf { width: 168px; }
.sf-field--cb { width: 220px; }

.sf-field :deep(.el-date-editor),
.sf-field :deep(.el-select),
.sf-field :deep(.el-input) {
  width: 100%;
}

.sf-field :deep(.el-input__wrapper),
.sf-field :deep(.el-select__wrapper) {
  min-height: 36px;
  border-radius: 12px;
  background: #fbfcfd;
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.08) inset;
}

.sf-field :deep(.el-input__inner),
.sf-field :deep(.el-select__placeholder),
.sf-field :deep(.el-select__selected-item) {
  color: var(--sf-ink);
  font-size: 13px;
}

/* 全站表头是主色实底白字；这一页按讨论稿改回浅底，方便对单 */
.sf-orders-monitor :deep(.sf-table.el-table) {
  --el-table-border-color: transparent;
  --el-table-header-bg-color: #f6f8f9;
  --el-table-tr-bg-color: #fff;
  --el-table-row-hover-bg-color: #fbfcfd;
  background: #fff;
}

.sf-orders-monitor :deep(.sf-table.el-table thead th.el-table__cell),
.sf-orders-monitor :deep(.sf-table.el-table .el-table__header-wrapper th.el-table__cell),
.sf-orders-monitor :deep(.sf-table.el-table .el-table__fixed-header-wrapper th.el-table__cell) {
  background: #f6f8f9 !important;
  color: var(--sf-muted) !important;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: none;
  border-bottom-color: var(--sf-line) !important;
}

.sf-orders-monitor :deep(.sf-table.el-table .el-table__header-wrapper th.el-table__cell:hover),
.sf-orders-monitor :deep(.sf-table.el-table .el-table__fixed-header-wrapper th.el-table__cell:hover) {
  background: #f6f8f9 !important;
}

.sf-orders-monitor :deep(.sf-table.admin-table--default.el-table .el-table__header th.el-table__cell),
.sf-orders-monitor :deep(.sf-table.admin-table--default.el-table .el-table__body td.el-table__cell) {
  padding: 10px 0;
}

.sf-orders-monitor :deep(.sf-table .el-table__body td.el-table__cell) {
  border-bottom: 1px solid #f1f4f6;
  vertical-align: middle;
}

.sf-orders-monitor :deep(.sf-table .el-table__body tr:hover > td.el-table__cell) {
  background: #fbfcfd !important;
}

.sf-orders-monitor :deep(.sf-table .cell) {
  line-height: 1.35;
  white-space: nowrap;
}

.sf-orders-monitor :deep(.sf-table .sf-num) {
  color: var(--sf-faint);
  font-variant-numeric: tabular-nums;
}

.sf-orders-monitor :deep(.sf-table .sf-day) {
  color: var(--sf-muted);
}

.sf-orders-monitor :deep(.sf-table .sf-mono) {
  font-family: "SF Mono", "JetBrains Mono", ui-monospace, Menlo, monospace;
  font-size: 12px;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.sf-orders-monitor :deep(.sf-table td.sf-ops-col),
.sf-orders-monitor :deep(.sf-table th.sf-ops-col) {
  background: #fff;
}

.sf-orders-monitor :deep(.sf-table .el-table__body tr:hover > td.sf-ops-col) {
  background: #fbfcfd !important;
}

.sf-cat,
.sf-st,
.sf-dot {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.sf-cat--retail { color: var(--el-color-primary-dark-2); background: color-mix(in srgb, var(--el-color-primary) 16%, #fff); }
.sf-cat--lunch { color: #1f7a4d; background: #e7f6ee; }
.sf-cat--dinner { color: #5346a0; background: #f1eef8; }
.sf-cat--muted { color: var(--sf-muted); background: #f4f6f8; }

.sf-dot {
  padding: 0;
  background: transparent;
  font-weight: 650;
  gap: 6px;
}

.sf-dot i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--sf-faint);
}

.sf-dot--ok i {
  background: var(--sf-ok);
  box-shadow: 0 0 0 3px rgba(31, 138, 91, 0.12);
}

.sf-dot--rose { color: var(--sf-rose-ink); }
.sf-dot--rose i { background: var(--sf-rose); }
.sf-dot--muted { color: var(--sf-muted); }

.sf-st--done { color: var(--sf-ok); background: #eef8f3; }
.sf-st--go { color: var(--sf-go); background: #fbf3ea; }
.sf-st--rose { color: var(--sf-rose-ink); background: #fdf2f3; }
.sf-st--muted { color: var(--sf-muted); background: #f4f6f8; }

.sf-kind {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.25;
  white-space: normal;
}

.sf-kind code {
  font-family: "SF Mono", ui-monospace, Menlo, monospace;
  font-size: 11px;
  color: var(--sf-faint);
}

.sf-ops {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}

.sf-orders-monitor :deep(.sf-act.el-button) {
  height: 28px;
  margin: 0;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.sf-orders-monitor :deep(.sf-act--ok.el-button) {
  color: #1f7a4d;
  background: #eef8f3;
  border-color: #d7efe4;
}

.sf-orders-monitor :deep(.sf-act--ok.el-button:hover) {
  color: #1f7a4d;
  background: #e3f5eb;
  border-color: #d7efe4;
}

.sf-orders-monitor :deep(.sf-act--stop.el-button) {
  color: var(--sf-rose-ink);
  background: #fdf2f3;
  border-color: #f3d5d8;
}

.sf-orders-monitor :deep(.sf-act--stop.el-button:hover) {
  color: var(--sf-rose-ink);
  background: #fbe6e8;
  border-color: #f3d5d8;
}

.sf-orders-monitor :deep(.sf-act--retry.el-button) {
  color: var(--el-color-primary-dark-2);
  background: color-mix(in srgb, var(--el-color-primary) 14%, #fff);
  border-color: color-mix(in srgb, var(--el-color-primary) 28%, #fff);
}

.sf-op-muted {
  font-size: 13px;
  color: var(--sf-faint);
}

@media (max-width: 1100px) {
  .sf-meter { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .sf-meter__main { grid-column: 1 / -1; }
  .sf-cell { border-top: 1px solid var(--sf-line); }
}

@media (max-width: 720px) {
  .sf-head { flex-direction: column; align-items: flex-start; }
  .sf-meter { grid-template-columns: 1fr 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .sf-refresh__spin { animation: none; }
}
</style>
