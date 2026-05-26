<script setup>
defineOptions({ name: 'OrdersManageView' })
import { ref, computed, watch, onMounted } from 'vue'
import { AlertTriangle, ChevronDown, RefreshCw, Search } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import MemberDeliveryMapPicker from '../components/MemberDeliveryMapPicker.vue'
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

/**
 * 列表「配送/自提」列：仅展示详细地址；后端 address_summary 常为「片区名 + 空格 + 地图/门牌」，
 * 与 routing_area 重复前缀时去掉片区，避免与智能配送大表里「片区单独列」的阅读习惯冲突。
 * @param {Record<string, unknown>} row
 */
function singleOrderDeliveryAddressTextOnly(row) {
  if (!row || row.store_pickup) return '门店自提'
  const ra = String(row.routing_area ?? '').trim()
  const sum = String(row.address_summary ?? '').trim()
  if (!sum || sum === '—') return '—'
  if (ra && (sum === ra || sum.startsWith(`${ra} `))) {
    const rest = sum.slice(ra.length).trim()
    return rest || '—'
  }
  return sum
}

const activeTab = ref('single')
const orderDate = ref(todayShanghaiStr())
const searchQuery = ref('')
/** 单次点餐 / 商城卡包：支付状态 Tab，默认全部 */
const singlePayFilter = ref('all')
/** 单次点餐：配送维度筛选，对应接口 delivery_phase */
const singleDeliveryFilter = ref('')
const mallPayFilter = ref('all')

const dateFilterLabel = computed(() => (activeTab.value === 'single' ? '供餐日' : '下单日'))

const SINGLE_PAY_TABS = [
  { label: '全部', value: 'all' },
  { label: '已支付', value: '已支付' },
  { label: '未支付', value: '未支付' },
  { label: '已取消', value: '已取消' },
]

const MALL_PAY_TABS = [
  { label: '全部', value: 'all' },
  { label: '已支付', value: '已支付' },
  { label: '未支付', value: '未支付' },
  { label: '已取消', value: '已取消' },
]

function mallPayFilterApiValue(tabValue) {
  const v = String(tabValue ?? '').trim()
  if (v === '已支付') return '已缴'
  if (v === '未支付') return '未缴'
  if (v === '已取消') return '已退款'
  return v
}
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
/** @type {import('vue').Ref<import('vue').ComponentPublicInstance | null>} */
const singleTableRef = ref(null)
/** @type {import('vue').Ref<Array<Record<string, unknown>>>} */
const selectedSingleRows = ref([])
const batchDispatchLoading = ref(false)
const batchCancelLoading = ref(false)
const batchMarkCompleteLoading = ref(false)
const cancelLoadingId = ref(0)
const markCompleteLoadingId = ref(0)
const batchAssignMode = ref(false)
/** @type {import('vue').Ref<Array<Record<string, unknown>>>} */
const batchAssignOrders = ref([])
const editOpen = ref(false)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const editOrder = ref(null)
const editSaving = ref(false)
const editAddrLoading = ref(false)
/** @type {import('vue').Ref<Array<Record<string, unknown>>>} */
const editMemberAddresses = ref([])
/** 当前编辑的会员地址明细（与「地址管理」弹窗字段一致，绑定地图选点） */
/** @type {import('vue').Ref<null | Record<string, unknown>>} */
const editAddrDraft = ref(null)
/** 保存地址时是否同时设为该会员默认配送地址 */
const editAddrAlsoDefault = ref(false)
const editForm = ref({
  store_pickup: false,
  member_address_id: null,
})

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
  const f = String(row.fulfillment_status || '').toLowerCase()
  if (f === 'cancelled') return false
  return f === 'pending' || f === 'sf_cancelled'
}

function isSfCancelledRedispatch(row) {
  return String(row?.fulfillment_status || '').trim().toLowerCase() === 'sf_cancelled'
}

function canCancelOrder(row) {
  if (!row) return false
  const pay = String(row.pay_status || '').trim()
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  if (pay === '已退款' || f === 'delivered' || f === 'cancelled') return false
  if (pay === '未支付') return f === 'pending'
  if (pay === '已支付') return f === 'pending' || f === 'accepted' || f === 'sf_cancelled'
  return false
}

function canMarkOrderComplete(row) {
  if (!row || row.pay_status !== '已支付') return false
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  return f === 'pending' || f === 'accepted'
}

function canModifyOrder(row) {
  if (!row) return false
  const pay = String(row.pay_status || '').trim()
  const f = String(row.fulfillment_status || '').trim().toLowerCase()
  if (pay === '已退款' || f === 'cancelled' || f === 'accepted') return false
  return f === 'pending' || f === 'sf_cancelled' || f === 'delivered'
}

function formatMemberAddressOption(a) {
  if (!a) return '—'
  const area = (a.area || '').trim()
  const full = (a.full_address || '').trim()
  const name = (a.contact_name || '').trim()
  const parts = [area, full].filter(Boolean)
  const line = parts.join(' ') || '—'
  return name ? `${name} · ${line}` : line
}

async function loadMemberAddressesForEdit(memberId) {
  editMemberAddresses.value = []
  if (!memberId) return
  editAddrLoading.value = true
  try {
    const list = await apiJson(`/api/admin/users/${Number(memberId)}/addresses`, {}, { auth: true })
    editMemberAddresses.value = Array.isArray(list) ? list : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载会员地址失败', 'error')
  } finally {
    editAddrLoading.value = false
  }
}

/** 从列表行填充「修改订单」右侧地址表单（与 MemberAddressesModal.pickAddrEdit 一致） */
function pickEditAddressDraft(a) {
  if (!a || a.id == null) {
    editAddrDraft.value = null
    return
  }
  const lng = a.location?.lng
  const lat = a.location?.lat
  editAddrDraft.value = {
    id: Number(a.id),
    contact_name: a.contact_name || '',
    contact_phone: a.contact_phone || '',
    map_location_text: a.map_location_text || '',
    door_detail: a.door_detail || '',
    remarks: a.remarks || '',
    lngStr: lng != null && lng !== '' ? String(lng) : '',
    latStr: lat != null && lat !== '' ? String(lat) : '',
  }
}

/** 下拉变更或地址列表加载完成后，与当前选中的 member_address_id 同步表单 */
function syncEditAddrDraftFromSelection() {
  if (!editOpen.value || editForm.value.store_pickup) {
    editAddrDraft.value = null
    return
  }
  const id = editForm.value.member_address_id
  const list = editMemberAddresses.value
  if (!id || !Array.isArray(list) || !list.length) {
    editAddrDraft.value = null
    return
  }
  const a = list.find((x) => Number(x.id) === Number(id))
  if (!a) {
    editAddrDraft.value = null
    return
  }
  pickEditAddressDraft(a)
}

const editHeadCoordDisplay = computed(() => {
  const ed = editAddrDraft.value
  if (!ed) return '—'
  const a = String(ed.lngStr ?? '').trim()
  const b = String(ed.latStr ?? '').trim()
  if (a && b) return `${a}, ${b}`
  return '未选点'
})

function onEditAddrMapWarn(msg) {
  const s = typeof msg === 'string' && msg.trim() ? msg.trim() : '地图提示'
  showToast(s, 'error')
}

watch(
  () => editForm.value.member_address_id,
  () => {
    if (editOpen.value && !editForm.value.store_pickup) syncEditAddrDraftFromSelection()
  },
)

watch(
  () => editForm.value.store_pickup,
  (pickup) => {
    if (pickup) editAddrDraft.value = null
    else if (editOpen.value) syncEditAddrDraftFromSelection()
  },
)

function openEditOrder(row) {
  if (!canModifyOrder(row)) {
    showToast('当前订单不可修改（配送中、已取消或已退款）', 'error')
    return
  }
  editOrder.value = row
  editAddrDraft.value = null
  editAddrAlsoDefault.value = false
  editForm.value = {
    store_pickup: !!row.store_pickup,
    member_address_id: row.member_address_id ? Number(row.member_address_id) : null,
  }
  editOpen.value = true
  void loadMemberAddressesForEdit(row.member_id).then(() => {
    syncEditAddrDraftFromSelection()
  })
}

async function submitEditOrder() {
  const row = editOrder.value
  if (!row) return
  const pickup = !!editForm.value.store_pickup
  const addrId = editForm.value.member_address_id
  if (!pickup && (!addrId || Number(addrId) <= 0)) {
    showToast('配送到家须选择收货地址', 'error')
    return
  }
  const mid = Number(row.member_id)
  if (!pickup) {
    const ed = editAddrDraft.value
    if (!ed || Number(ed.id) !== Number(addrId)) {
      showToast('地址明细未加载或与所选地址不一致，请稍候或重新打开', 'error')
      return
    }
    const cn = String(ed.contact_name ?? '').trim()
    const cp = String(ed.contact_phone ?? '').trim()
    const mt = String(ed.map_location_text ?? '').trim()
    if (!cn) {
      showToast('请填写收件人', 'error')
      return
    }
    if (cp.length < 5) {
      showToast('请填写有效联系电话（至少 5 位）', 'error')
      return
    }
    if (!mt) {
      showToast('请通过地图搜索/选点填写收货位置主文案，或直接在主文案里填写', 'error')
      return
    }
  }

  editSaving.value = true
  try {
    if (!pickup) {
      const ed = editAddrDraft.value
      const patchBody = {
        contact_name: String(ed.contact_name ?? '').trim(),
        contact_phone: String(ed.contact_phone ?? '').trim(),
        map_location_text: String(ed.map_location_text ?? '').trim(),
        door_detail: String(ed.door_detail ?? '').trim() || null,
        remarks: String(ed.remarks ?? '').trim() || null,
      }
      if (editAddrAlsoDefault.value) {
        patchBody.is_default = true
      }
      const lng = Number(String(ed.lngStr ?? '').trim())
      const lat = Number(String(ed.latStr ?? '').trim())
      if (Number.isFinite(lng) && Number.isFinite(lat)) {
        patchBody.location = { lng, lat }
      }
      await apiJson(`/api/admin/users/${mid}/addresses/${Number(addrId)}`, {
        method: 'PATCH',
        body: JSON.stringify(patchBody),
      }, { auth: true })
    }

    const body = { store_pickup: pickup }
    if (!pickup) body.member_address_id = Number(addrId)
    await apiJson(
      `/api/admin/orders/single-meals/${row.id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      { auth: true },
    )
    showToast('订单与收货信息已保存', 'success')
    editOpen.value = false
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    editSaving.value = false
  }
}

function isSingleRowSelectable(row) {
  return canDispatchActions(row) || canCancelOrder(row) || canMarkOrderComplete(row)
}

function onSingleSelectionChange(rows) {
  selectedSingleRows.value = Array.isArray(rows) ? rows : []
}

function clearSingleSelection() {
  singleTableRef.value?.clearSelection?.()
  selectedSingleRows.value = []
}

const selectedDispatchableRows = computed(() =>
  selectedSingleRows.value.filter((row) => canDispatchActions(row) && !row.store_pickup),
)

const selectedCancellableRows = computed(() =>
  selectedSingleRows.value.filter((row) => canCancelOrder(row)),
)

const selectedCompletableRows = computed(() =>
  selectedSingleRows.value.filter((row) => canMarkOrderComplete(row)),
)

const batchActionBusy = computed(
  () => batchDispatchLoading.value || batchCancelLoading.value || batchMarkCompleteLoading.value,
)

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
    showToast('仅「待发货」或「顺丰取消」且已支付订单可推送顺丰', 'error')
    return
  }
  if (row.store_pickup) {
    showToast('门店自提订单不发顺丰到家；可用「门店自配送」指派', 'error')
    return
  }
  const isRetry = isSfCancelledRedispatch(row)
  try {
    await ElMessageBox.confirm(
      isRetry
        ? '该订单此前顺丰侧已取消，将重新向顺丰创单。是否继续？'
        : '将使用门店设置中的「零售推顺丰店铺ID」向顺丰创单（与智能配送大表所用顺丰店铺编号独立）。是否继续？',
      isRetry ? '重新推送到顺丰' : '推送到顺丰',
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
    showToast('仅「待发货」或「顺丰取消」且已支付订单可操作', 'error')
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
    showToast('仅「待发货」或「顺丰取消」订单可指派门店配送员', 'error')
    return
  }
  batchAssignMode.value = false
  batchAssignOrders.value = []
  assignOrder.value = row
  assignCourierId.value = row.courier_id ? String(row.courier_id) : ''
  assignOpen.value = true
  void loadCouriers()
}

function openBatchAssignCourier() {
  const rows = selectedSingleRows.value.filter((row) => canDispatchActions(row))
  if (!rows.length) {
    showToast('请勾选可配送的订单（待发货或顺丰已取消）', 'error')
    return
  }
  batchAssignMode.value = true
  batchAssignOrders.value = rows
  assignOrder.value = null
  assignCourierId.value = ''
  assignOpen.value = true
  void loadCouriers()
}

/** 单行：配送相关请求中的 loading（下拉「更多」按钮统一展示） */
function singleRowActionLoading(row) {
  const id = Number(row?.id)
  if (!Number.isFinite(id)) return false
  return (
    dispatchLoadingId.value === id ||
    markCompleteLoadingId.value === id ||
    cancelLoadingId.value === id ||
    refundLoadingId.value === id
  )
}

/**
 * 单次点餐 · 更多菜单：将小屏上过宽的操作区收拢为单列下拉
 * @param {Record<string, unknown>} row
 * @param {string} cmd
 */
function onSingleRowMoreCommand(row, cmd) {
  if (cmd === 'modify') openEditOrder(row)
  else if (cmd === 'sf') void onPushSfRetail(row)
  else if (cmd === 'uu') void onPushUu(row)
  else if (cmd === 'courier') openAssignCourier(row)
  else if (cmd === 'complete') void onMarkOrderComplete(row)
  else if (cmd === 'cancel') void onCancelOrder(row)
  else if (cmd === 'refund') onRefundWechatSingle(row)
}

/** 商城卡包 · 更多（与单次点餐交互一致） */
function onMallRowMoreCommand(row, cmd) {
  if (cmd === 'refund') onRefundWechatMall(row)
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
  const cid = String(assignCourierId.value || '').trim()
  if (!cid) {
    showToast('请选择配送员', 'error')
    return
  }
  if (batchAssignMode.value) {
    const ids = batchAssignOrders.value.map((r) => Number(r.id)).filter((id) => id > 0)
    if (!ids.length) {
      showToast('未选择有效订单', 'error')
      return
    }
    batchDispatchLoading.value = true
    try {
      const data = await apiJson(
        '/api/admin/orders/single-meals/batch-dispatch/store-courier',
        {
          method: 'POST',
          body: JSON.stringify({ order_ids: ids, courier_id: cid }),
        },
        { auth: true },
      )
      const results = Array.isArray(data?.results) ? data.results : []
      const fail = results.filter((x) => x && !x.ok)
      if (fail.length) {
        const msg = fail.map((f) => `#${f.order_id}: ${f.message || ''}`).join('；')
        showToast(`部分失败：${msg}`, 'error')
      } else {
        showToast(`已批量指派 ${ids.length} 单`, 'success')
      }
      assignOpen.value = false
      clearSingleSelection()
      await fetchSingleMeals()
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        handleAdminLogout()
        return
      }
      showToast(e instanceof Error ? e.message : '批量指派失败', 'error')
    } finally {
      batchDispatchLoading.value = false
    }
    return
  }
  const row = assignOrder.value
  if (!row) {
    showToast('请选择订单', 'error')
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

async function onBatchPushSfRetail() {
  const rows = selectedDispatchableRows.value
  if (!rows.length) {
    showToast('请勾选可推顺丰的订单（待发货或顺丰已取消，不含门店自提）', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将为 ${rows.length} 笔订单调用顺丰创单（使用门店「零售推顺丰店铺ID」）。是否继续？`,
      '批量推送到顺丰',
      { type: 'warning', confirmButtonText: '确定推送', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  batchDispatchLoading.value = true
  try {
    const ids = rows.map((r) => Number(r.id)).filter((id) => id > 0)
    const data = await apiJson(
      '/api/admin/orders/single-meals/batch-dispatch/sf-retail',
      { method: 'POST', body: JSON.stringify({ order_ids: ids }) },
      { auth: true },
    )
    const results = Array.isArray(data?.results) ? data.results : []
    const okCount = results.filter((x) => x && x.ok).length
    const fail = results.filter((x) => x && !x.ok)
    if (fail.length) {
      const msg = fail.map((f) => `#${f.order_id}: ${f.message || ''}`).join('；')
      showToast(`成功 ${okCount} 笔，失败 ${fail.length} 笔：${msg}`, fail.length === ids.length ? 'error' : 'warning')
    } else {
      showToast(`已全部提交顺丰（${okCount} 笔）`, 'success')
    }
    clearSingleSelection()
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '批量推送失败', 'error')
  } finally {
    batchDispatchLoading.value = false
  }
}

async function onCancelOrder(row) {
  if (!canCancelOrder(row)) {
    showToast('当前订单不可取消', 'error')
    return
  }
  const isPaid = row.pay_status === '已支付'
  try {
    await ElMessageBox.confirm(
      isPaid
        ? `确定取消订单 #${row.id}？已支付订单取消后不退款，若已推顺丰将同步请求取消配送。`
        : `确定取消未支付订单 #${row.id}？`,
      '取消订单',
      { type: 'warning', confirmButtonText: '确定取消', cancelButtonText: '返回' },
    )
  } catch {
    return
  }
  cancelLoadingId.value = Number(row.id)
  try {
    const data = await apiJson(
      `/api/admin/orders/single-meals/${row.id}/cancel`,
      { method: 'POST', body: JSON.stringify({ cancel_sf: true }) },
      { auth: true },
    )
    const msg = typeof data?.message === 'string' ? data.message : '订单已取消'
    showToast(msg, 'success')
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '取消失败', 'error')
  } finally {
    cancelLoadingId.value = 0
  }
}

async function onMarkOrderComplete(row) {
  if (!canMarkOrderComplete(row)) {
    showToast('当前订单不可标记完成', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定将订单 #${row.id} 标记为已完成？适用于顺丰、UU 跑腿或门店自配送等已实际送达/自提的场景。`,
      '标记订单完成',
      { type: 'info', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  markCompleteLoadingId.value = Number(row.id)
  try {
    const data = await apiJson(
      `/api/admin/orders/single-meals/${row.id}/mark-delivered`,
      { method: 'POST' },
      { auth: true },
    )
    const msg = typeof data?.message === 'string' ? data.message : '已标记为已完成'
    showToast(msg, 'success')
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '标记失败', 'error')
  } finally {
    markCompleteLoadingId.value = 0
  }
}

async function onBatchMarkComplete() {
  const rows = selectedCompletableRows.value
  if (!rows.length) {
    showToast('请勾选可标记完成的已支付订单', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定将选中的 ${rows.length} 笔订单标记为已完成？`,
      '批量标记完成',
      { type: 'info', confirmButtonText: '确定', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  batchMarkCompleteLoading.value = true
  try {
    const ids = rows.map((r) => Number(r.id)).filter((id) => id > 0)
    const data = await apiJson(
      '/api/admin/orders/single-meals/batch-mark-delivered',
      { method: 'POST', body: JSON.stringify({ order_ids: ids }) },
      { auth: true },
    )
    const results = Array.isArray(data?.results) ? data.results : []
    const okCount = results.filter((x) => x && x.ok).length
    const fail = results.filter((x) => x && !x.ok)
    if (fail.length) {
      const msg = fail.map((f) => `#${f.order_id}: ${f.message || ''}`).join('；')
      showToast(`成功 ${okCount} 笔，失败 ${fail.length} 笔：${msg}`, fail.length === ids.length ? 'error' : 'warning')
    } else {
      showToast(`已标记完成 ${okCount} 笔`, 'success')
    }
    clearSingleSelection()
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '批量标记失败', 'error')
  } finally {
    batchMarkCompleteLoading.value = false
  }
}

async function onBatchCancelOrders() {
  const rows = selectedCancellableRows.value
  if (!rows.length) {
    showToast('请勾选可取消的订单', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确定取消选中的 ${rows.length} 笔订单？已支付订单取消后不退款；已推顺丰的将尝试同步取消配送。`,
      '批量取消订单',
      { type: 'warning', confirmButtonText: '确定取消', cancelButtonText: '返回' },
    )
  } catch {
    return
  }
  batchCancelLoading.value = true
  try {
    const ids = rows.map((r) => Number(r.id)).filter((id) => id > 0)
    const data = await apiJson(
      '/api/admin/orders/single-meals/batch-cancel',
      { method: 'POST', body: JSON.stringify({ order_ids: ids, cancel_sf: true }) },
      { auth: true },
    )
    const results = Array.isArray(data?.results) ? data.results : []
    const okCount = results.filter((x) => x && x.ok).length
    const fail = results.filter((x) => x && !x.ok)
    if (fail.length) {
      const msg = fail.map((f) => `#${f.order_id}: ${f.message || ''}`).join('；')
      showToast(`成功 ${okCount} 笔，失败 ${fail.length} 笔：${msg}`, fail.length === ids.length ? 'error' : 'warning')
    } else {
      showToast(`已取消 ${okCount} 笔订单`, 'success')
    }
    clearSingleSelection()
    await fetchSingleMeals()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '批量取消失败', 'error')
  } finally {
    batchCancelLoading.value = false
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
  cancelled: '已取消',
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
  if (x === 'sf_cancelled' || x === 'cancelled') return 'member-pill member-pill--rose'
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
    if (d) q.set('delivery_date', d)
    const sq = searchQuery.value.trim()
    if (sq) q.set('q', sq)
    const pf = String(singlePayFilter.value ?? '').trim()
    if (pf === '未支付' || pf === '已支付' || pf === '已取消') q.set('pay_status', pf)
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
    const pf = mallPayFilterApiValue(mallPayFilter.value)
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
  clearSingleSelection()
  void fetchActive()
})

async function onSyncDeliveryStatus() {
  if (!adminAccessToken.value || activeTab.value !== 'single') return
  const d0 = String(orderDate.value || '').trim() || todayShanghaiStr()
  try {
    await ElMessageBox.confirm(
      `将 ${d0} 供餐日单次点餐中，顺丰监控已为「妥投」或「取消/撤单」但未回写系统的订单，同步为「已完成」或「顺丰取消」。是否继续？`,
      '同步订单状态',
      { type: 'info', confirmButtonText: '开始同步', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  syncDeliveryLoading.value = true
  try {
    const q = new URLSearchParams()
    q.set('delivery_date', d0)
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
          <span class="orders-manage-date-label">{{ dateFilterLabel }}</span>
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
           <el-tabs v-model="singlePayFilter" class="orders-pay-tabs">
             <el-tab-pane
               v-for="tab in SINGLE_PAY_TABS"
               :key="tab.value"
               :label="tab.label"
               :name="tab.value"
             />
           </el-tabs>
           <div class="orders-manage-tab-bar__row">
             <div class="orders-manage-tab-bar__filters">
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
             <div class="orders-batch-bar__actions">
              <span v-if="selectedSingleRows.length" class="orders-batch-bar__count">
                已选 {{ selectedSingleRows.length }} 笔
              </span>
              <el-button type="primary" size="small" :loading="batchDispatchLoading"
                :disabled="!selectedDispatchableRows.length || batchActionBusy" @click="onBatchPushSfRetail">
                推送顺丰
              </el-button>
              <el-button type="primary" size="small" plain :loading="batchDispatchLoading"
                :disabled="!selectedSingleRows.some((r) => canDispatchActions(r)) || batchActionBusy"
                @click="openBatchAssignCourier">
                门店配送
              </el-button>
              <el-button type="success" size="small" plain :loading="batchMarkCompleteLoading"
                :disabled="!selectedCompletableRows.length || batchActionBusy" @click="onBatchMarkComplete">
                批量完成
              </el-button>
              <el-button type="danger" size="small" plain :loading="batchCancelLoading"
                :disabled="!selectedCancellableRows.length || batchActionBusy" @click="onBatchCancelOrders">
                批量取消
              </el-button>
              <el-button size="small" :disabled="!selectedSingleRows.length || batchActionBusy"
                @click="clearSingleSelection">
                清空选择
              </el-button>
            </div>
           </div>
          </div>
          <AdminTable
ref="singleTableRef"
            variant="members"
            size="small"
            :data="singleItems"
            :loading="loading && activeTab === 'single'"
            row-key="id"
            empty-text="该供餐日暂无单次点餐订单"
           @selection-change="onSingleSelectionChange"
          >
           <el-table-column type="selection" width="42" :selectable="isSingleRowSelectable" />
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
           <el-table-column label="订单状态" width="120" class-name="co-nowrap">
              <template #default="{ row }">
               <span :class="singleOrderStatusClass(row)">{{ singleOrderStatusLabelZh(row) }}</span>
              </template>
            </el-table-column>
            <el-table-column
              label="配送/自提"
              header-align="left"
              align="left"
              min-width="480"
              :show-overflow-tooltip="false"
              class-name="orders-single-addr-col"
            >
              <template #default="{ row }">
                <div class="orders-addr-text">
                  <template v-if="row.store_pickup">门店自提</template>
                  <template v-else>{{ singleOrderDeliveryAddressTextOnly(row) }}</template>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="单号" width="120" class-name="td-mono" show-overflow-tooltip>
              <template #default="{ row }">{{ row.out_trade_no || '—' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="92" fixed="right" align="center" class-name="orders-col-more">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => onSingleRowMoreCommand(row, cmd)">
                  <el-button
                    type="primary"
                    size="small"
                    plain
                    class="orders-more-trigger"
                    :loading="singleRowActionLoading(row)"
                    aria-label="更多操作"
                  >
                    更多
                    <ChevronDown :size="14" class="orders-more-chevron" aria-hidden="true" stroke-width="2.25" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu class="orders-more-menu">
                      <el-dropdown-item command="modify" :disabled="!canModifyOrder(row)">
                        修改
                      </el-dropdown-item>
                      <el-dropdown-item
                        command="sf"
                        divided
                        :disabled="!canDispatchActions(row) || row.store_pickup"
                      >
                        {{ isSfCancelledRedispatch(row) ? '重新推送到顺丰' : '推送到顺丰' }}
                      </el-dropdown-item>
                      <el-dropdown-item command="uu" :disabled="!canDispatchActions(row)">
                        推送到 UU
                      </el-dropdown-item>
                      <el-dropdown-item command="courier" :disabled="!canDispatchActions(row)">
                        门店自配送
                      </el-dropdown-item>
                      <el-dropdown-item command="complete" divided :disabled="!canMarkOrderComplete(row)">
                        完成
                      </el-dropdown-item>
                      <el-dropdown-item command="cancel" :disabled="!canCancelOrder(row)">
                        取消
                      </el-dropdown-item>
                      <el-dropdown-item command="refund" divided :disabled="!canRefundWechatSingle(row)">
                        退款
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </AdminTable>
        </el-tab-pane>

        <el-tab-pane label="商城卡包" name="mall">
          <div class="orders-manage-tab-bar">
            <el-tabs v-model="mallPayFilter" class="orders-pay-tabs">
              <el-tab-pane
                v-for="tab in MALL_PAY_TABS"
                :key="tab.value"
                :label="tab.label"
                :name="tab.value"
              />
            </el-tabs>
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
            <el-table-column label="操作" width="92" fixed="right" align="center" class-name="orders-col-more">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd) => onMallRowMoreCommand(row, cmd)">
                  <el-button
                    type="primary"
                    size="small"
                    plain
                    class="orders-more-trigger"
                    :loading="refundLoadingId === row.id"
                    aria-label="更多操作"
                  >
                    更多
                    <ChevronDown :size="14" class="orders-more-chevron" aria-hidden="true" stroke-width="2.25" />
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu class="orders-more-menu">
                      <el-dropdown-item command="refund" :disabled="!canRefundWechatMall(row)">
                        微信退款
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
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

  <el-dialog v-model="assignOpen" :title="batchAssignMode ? '批量门店自配送 · 指派配送员' : '门店自配送 · 指派配送员'" width="420px"
      destroy-on-close @closed="batchAssignMode = false; batchAssignOrders = []">
      <template v-if="batchAssignMode">
        <p class="orders-assign-hint">
          已选 {{ batchAssignOrders.length }} 笔待发货订单，将统一指派给所选配送员。
        </p>
      </template>
      <template v-else-if="assignOrder">
        <p class="orders-assign-hint">
          订单 #{{ assignOrder.id }} · {{ (assignOrder.member_name || '').trim() || '—' }}
        </p>
     </template>
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
      <template #footer>
        <el-button @click="assignOpen = false">取消</el-button>
       <el-button type="primary" :loading="batchDispatchLoading" @click="submitAssignCourier">
          {{ batchAssignMode ? '批量确定' : '确定' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editOpen"
      title="修改订单 · 配送/自提与收货地址"
      width="920px"
      class="orders-edit-order-dialog"
      destroy-on-close
      align-center
      :close-on-click-modal="!editSaving"
      :close-on-press-escape="!editSaving"
      @closed="editOrder = null; editMemberAddresses = []; editAddrDraft = null; editAddrAlsoDefault = false"
    >
      <template v-if="editOrder">
        <p class="orders-edit-hint">
          订单 #{{ editOrder.id }} · {{ (editOrder.member_name || '').trim() || '—' }}
          {{ (editOrder.member_phone || '').trim() }}
        </p>
        <div class="orders-edit-field">
          <span class="orders-edit-label">履约方式</span>
          <el-radio-group v-model="editForm.store_pickup">
            <el-radio :value="false">配送到家</el-radio>
            <el-radio :value="true">门店自提</el-radio>
          </el-radio-group>
        </div>
        <div v-if="!editForm.store_pickup" class="orders-edit-field">
          <span class="orders-edit-label">收货地址</span>
          <el-select
            v-model="editForm.member_address_id"
            filterable
            placeholder="选择会员配送地址（可切换该会员名下其它地址）"
            class="orders-edit-select"
            :loading="editAddrLoading"
          >
            <el-option
              v-for="a in editMemberAddresses"
              :key="a.id"
              :label="formatMemberAddressOption(a)"
              :value="Number(a.id)"
            />
          </el-select>
          <p v-if="!editAddrLoading && !editMemberAddresses.length" class="orders-edit-tip">
            该会员暂无配送地址，请先在会员档案「地址」中新建后再来绑定订单。
          </p>
        </div>

        <template v-if="!editForm.store_pickup && editAddrDraft">
          <div class="orders-edit-addr-sep" />
          <p class="orders-edit-subhint">
            以下与「会员档案 · 地址管理」一致：可修正收件人、电话、地图选点与门牌；
            <strong>保存时先写入会员地址</strong>（全店订单凡引用本条地址一并更新），再更新本订单绑定与配送摘要。
          </p>
          <div class="orders-edit-first-row">
            <el-space wrap :size="8" alignment="center">
              <span class="orders-edit-k">会员</span>
              <el-text truncated class="orders-edit-inline-name">{{ (editOrder.member_name || '—').trim() }}</el-text>
              <el-text type="info" truncated>{{ (editOrder.member_phone || '').trim() }}</el-text>
              <el-divider direction="vertical" />
              <span class="orders-edit-k">经纬度 GCJ-02</span>
              <el-tag size="small" type="info" effect="plain">{{ editHeadCoordDisplay }}</el-tag>
            </el-space>
          </div>
          <el-form label-position="top" size="small" class="orders-edit-addr-form">
            <el-row :gutter="12">
              <el-col :xs="24" :sm="12">
                <el-form-item label="收件人">
                  <el-input
                    v-model="editAddrDraft.contact_name"
                    maxlength="100"
                    clearable
                    placeholder="收件人姓名"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="12">
                <el-form-item label="联系电话">
                  <el-input v-model="editAddrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="地图选点（GCJ-02）">
              <div class="orders-edit-map-wrap">
                <MemberDeliveryMapPicker
                  :key="'orders-edit-ma-' + editAddrDraft.id"
                  v-model:lng-str="editAddrDraft.lngStr"
                  v-model:lat-str="editAddrDraft.latStr"
                  v-model:map-location-text="editAddrDraft.map_location_text"
                  :search-input-id="'orders-edit-amap-' + editAddrDraft.id"
                  @warn="onEditAddrMapWarn"
                />
              </div>
            </el-form-item>
            <el-row :gutter="12">
              <el-col :xs="24" :sm="14">
                <el-form-item label="收货位置主文案（map_location_text）">
                  <el-input
                    v-model="editAddrDraft.map_location_text"
                    type="textarea"
                    readonly
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    maxlength="500"
                    show-word-limit
                    placeholder="地图选点后自动填入，可与门牌拼成完整地址"
                  />
                </el-form-item>
              </el-col>
              <el-col :xs="24" :sm="10">
                <el-form-item label="门牌（楼栋 / 单元 / 室号）">
                  <el-input
                    v-model="editAddrDraft.door_detail"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 3 }"
                    maxlength="500"
                    placeholder="例如：3 号楼 1202"
                  />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="地址备注">
              <el-input
                v-model="editAddrDraft.remarks"
                type="textarea"
                :autosize="{ minRows: 1, maxRows: 3 }"
                maxlength="500"
                placeholder="忌口等，可留空"
              />
            </el-form-item>
            <el-form-item>
              <el-checkbox v-model="editAddrAlsoDefault">同时将本条设为该会员默认配送地址</el-checkbox>
            </el-form-item>
          </el-form>
        </template>

        <p v-else-if="editForm.store_pickup" class="orders-edit-tip orders-edit-tip--muted">
          门店自提无需维护收货地址。
        </p>
      </template>
      <template #footer>
        <el-button :disabled="editSaving" @click="editOpen = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="submitEditOrder">保存</el-button>
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
  flex-direction: column;
  align-items: stretch;
  gap: 0.65rem;
}
.orders-pay-tabs {
  width: 100%;
}
.orders-pay-tabs :deep(.el-tabs__header) {
  margin: 0;
}
.orders-pay-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: #e2e8f0;
}
.orders-pay-tabs :deep(.el-tabs__item) {
  height: 36px;
  line-height: 36px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  padding: 0 16px;
}
.orders-pay-tabs :deep(.el-tabs__item.is-active) {
  color: #0e5a44;
}
.orders-pay-tabs :deep(.el-tabs__active-bar) {
  background-color: #0e5a44;
}
.orders-manage-tab-bar--filters .orders-manage-tab-bar__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1.25rem;
}
.orders-manage-tab-bar--filters .orders-manage-tab-bar__filters {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem 1.25rem;
}
.orders-manage-tab-bar__filters {
    display: inline-flex;
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
.orders-edit-hint {
  margin: 0 0 1rem;
  font-size: 0.9rem;
  color: #334155;
}
.orders-edit-field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
}
.orders-edit-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: #64748b;
}
.orders-edit-select {
  width: 100%;
}
.orders-edit-tip {
  margin: 0;
  font-size: 0.8125rem;
  line-height: 1.5;
  color: #b45309;
}
.orders-edit-tip--muted {
  color: #64748b;
}
.orders-edit-subhint {
  margin: 0 0 0.75rem;
  font-size: 0.8125rem;
  line-height: 1.55;
  color: #64748b;
}
.orders-edit-addr-sep {
  margin: 0.85rem 0 0.65rem;
  border-top: 1px dashed #e2e8f0;
}
.orders-edit-first-row {
  margin-bottom: 0.65rem;
}
.orders-edit-k {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
}
.orders-edit-inline-name {
  max-width: 140px;
  font-weight: 600;
}
.orders-edit-map-wrap {
  width: 100%;
  min-height: 244px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}
.orders-edit-order-dialog :deep(.el-dialog__body) {
  padding-top: 0.5rem;
  max-height: min(78vh, 720px);
  overflow-y: auto;
}

.orders-mall-no-dispatch {
  font-size: 12px;
  color: var(--text-muted, #94a3b8);
}
/* 订单列表：配送地址列完整展示（覆盖 Element Plus 表格 .cell 默认单行省略） */
.orders-manage-page :deep(.admin-table--members.el-table td.orders-single-addr-col.el-table__cell) {
  vertical-align: top;
}
.orders-manage-page :deep(.admin-table--members.el-table td.orders-single-addr-col .cell) {
  white-space: normal !important;
  word-break: break-word;
  overflow-wrap: anywhere;
  overflow: visible !important;
  text-overflow: clip !important;
  line-height: 1.5;
  text-align: left;
  hyphens: auto;
}
.orders-addr-text {
  font-size: 12px;
  color: #334155;
  display: block;
  width: 100%;
  white-space: normal;
  overflow: visible;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.orders-more-chevron {
  display: inline-block;
  vertical-align: -0.125em;
  margin-left: 0.15rem;
  opacity: 0.85;
}
.orders-more-trigger {
  padding-left: 0.55rem;
  padding-right: 0.45rem;
}
.orders-manage-page :deep(.orders-more-menu.el-dropdown-menu) {
  min-width: 9.5rem;
}
.orders-manage-page :deep(td.orders-col-more .cell) {
  overflow: visible;
}

.orders-batch-bar__count {
  font-size: 0.8125rem;
  color: rgba(255, 255, 255, 0.62);
  white-space: nowrap;
  margin-right: 0.15rem;
}

.orders-batch-bar__actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0.4rem;
  margin-left: auto;
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
