import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { toastSfPushBatchOutcome, toastSfPushError } from '../../../utils/sfPushMessages.js'
import { todayShanghaiStr } from '../utils/orderFormatters.js'
import { mallPayFilterApiValue, resolveSingleOrderMemberDisplayName } from '../utils/orderDisplay.js'
import {
  canAcceptRetailOrder,
  canDispatchActions,
  canCancelOrder,
  canMarkOrderComplete,
  canModifyOrder,
  isSfCancelledRedispatch,
  canRefundWechatSingle,
  canRefundWechatMall,
  canRefundWechatRetail,
} from '../utils/orderPermissions.js'

/**
 * 订单管理页核心业务逻辑（零售订单 / 商城订单 / 卡包订单）
 * @param {'single' | 'retail' | 'mall'} orderKind 各独立页面固定传入的订单类型
 */
export function useOrdersManage(orderKind = 'single') {
  const activeTab = ref(orderKind)
  const orderDate = ref(todayShanghaiStr())
  const route = useRoute()
  const searchQuery = ref('')
  const singlePayFilter = ref('all')
  const singleDeliveryFilter = ref('')
  const mallPayFilter = ref('all')
  const retailDeliveryFilter = ref('awaiting_accept')

  const dateFilterLabel = computed(() => (orderKind === 'single' ? '供餐日' : '下单日'))

  const loading = ref(false)
  const singleItems = ref([])
  const singleTotal = ref(0)
  /** @type {import('vue').Ref<null | { paid: number; unpaid: number; cancelled: number; pending_ship: number }>} */
  const singleOrderBucketSummary = ref(null)
  const mallItems = ref([])
  const mallTotal = ref(0)
  const retailItems = ref([])
  const retailTotal = ref(0)
  const page = ref(1)
  const pageSize = ref(20)

  /** @type {import('vue').Ref<Array<Record<string, unknown>>>} */
  const courierOptions = ref([])
  const assignOpen = ref(false)
  /** @type {'single' | 'retail'} */
  const assignKind = ref('single')
  /** @type {import('vue').Ref<Record<string, unknown> | null>} */
  const assignOrder = ref(null)
  const assignCourierId = ref('')
  const dispatchLoadingId = ref(0)
  const refundLoadingId = ref(0)
  const refundOpen = ref(false)
  /** @type {import('vue').Ref<{ kind: 'single' | 'mall' | 'retail'; row: Record<string, unknown> } | null>} */
  const refundTarget = ref(null)
  const retailRemarkOpen = ref(false)
  /** @type {import('vue').Ref<Record<string, unknown> | null>} */
  const retailRemarkTarget = ref(null)
  const retailRemarkDraft = ref('')
  const retailRemarkSaving = ref(false)
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
  /** @type {import('vue').Ref<null | Record<string, unknown>>} */
  const editAddrDraft = ref(null)
  const editAddrAlsoDefault = ref(false)
  const editForm = ref({
    store_pickup: false,
    member_address_id: null,
  })

  const editDialogMemberDisplayName = computed(() =>
    resolveSingleOrderMemberDisplayName(editOrder.value, editAddrDraft.value),
  )

  const refundDialogMeta = computed(() => {
    const t = refundTarget.value
    if (!t) return null
    const row = t.row
    const amt = row.amount_yuan
    const amountStr = amt != null && amt !== '' ? String(amt) : '—'
    if (t.kind === 'single') {
      return {
        orderType: '零售订单',
        orderId: row.id,
        amountStr,
        sub: '全额退回支付用户微信零钱',
        tip: '退款成功后订单状态将变为「已退款」，操作不可撤销。',
      }
    }
    if (t.kind === 'retail') {
      return {
        orderType: '商城订单',
        orderId: row.id,
        amountStr,
        sub: '全额退回支付用户微信零钱',
        tip: '退款成功后订单状态将变为「已退款」，操作不可撤销。',
      }
    }
    return {
      orderType: '卡包订单',
      orderId: row.id,
      amountStr,
      sub: '全额退回支付用户微信零钱',
      tip: row.applied_to_member
        ? '该单已同步入账：退款时将先扣回对应餐次再发起微信原路退款，请确认会员剩余次数足够。'
        : '退款成功后订单状态将变为「已退款」，操作不可撤销。',
    }
  })

  const totalPages = computed(() => {
    const t =
      activeTab.value === 'single'
        ? singleTotal.value
        : activeTab.value === 'retail'
          ? retailTotal.value
          : mallTotal.value
    return Math.max(1, Math.ceil((t || 0) / pageSize.value))
  })

  const activeTabTotal = computed(() => {
    if (activeTab.value === 'single') return singleTotal.value
    if (activeTab.value === 'retail') return retailTotal.value
    return mallTotal.value
  })

  const editHeadCoordDisplay = computed(() => {
    const ed = editAddrDraft.value
    if (!ed) return '—'
    const a = String(ed.lngStr ?? '').trim()
    const b = String(ed.latStr ?? '').trim()
    if (a && b) return `${a}, ${b}`
    return '未选点'
  })

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

  function onEditDialogClosed() {
    editOrder.value = null
    editMemberAddresses.value = []
    editAddrDraft.value = null
    editAddrAlsoDefault.value = false
  }

  function onAssignDialogClosed() {
    batchAssignMode.value = false
    batchAssignOrders.value = []
  }

  function onRefundDialogClosed() {
    refundTarget.value = null
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
      toastSfPushError(e instanceof Error ? e.message : '推送失败', showToast)
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
    assignKind.value = 'single'
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

  function onSingleRowMoreCommand(row, cmd) {
    if (cmd === 'modify') openEditOrder(row)
    else if (cmd === 'sf') void onPushSfRetail(row)
    else if (cmd === 'uu') void onPushUu(row)
    else if (cmd === 'courier') openAssignCourier(row)
    else if (cmd === 'complete') void onMarkOrderComplete(row)
    else if (cmd === 'cancel') void onCancelOrder(row)
    else if (cmd === 'refund') onRefundWechatSingle(row)
  }

  function onMallRowMoreCommand(row, cmd) {
    if (cmd === 'refund') onRefundWechatMall(row)
  }

  function onRetailRowMoreCommand(row, cmd) {
    if (cmd === 'accept') void onAcceptRetailOrder(row)
    else if (cmd === 'sf') void onPushSfRetailOrder(row)
    else if (cmd === 'courier') openAssignCourierRetail(row)
    else if (cmd === 'complete') void onMarkRetailOrderComplete(row)
    else if (cmd === 'cancel') void onCancelRetailOrder(row)
    else if (cmd === 'refund') onRefundWechatRetail(row)
    else if (cmd === 'remark') openRetailRemarkDialog(row)
  }

  function openRetailRemarkDialog(row) {
    retailRemarkTarget.value = row
    retailRemarkDraft.value = String(row.remark || '')
    retailRemarkOpen.value = true
  }

  function onRetailRemarkDialogClosed() {
    retailRemarkTarget.value = null
    retailRemarkDraft.value = ''
    retailRemarkSaving.value = false
  }

  async function submitRetailRemark() {
    const row = retailRemarkTarget.value
    if (!row) return
    retailRemarkSaving.value = true
    try {
      const remark = String(retailRemarkDraft.value || '').trim() || null
      await apiJson(
        `/api/admin/orders/retail-orders/${row.id}/remark`,
        { method: 'PATCH', body: JSON.stringify({ remark }) },
        { auth: true },
      )
      showToast('备注已保存', 'success')
      retailRemarkOpen.value = false
      await fetchRetailOrders()
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        showToast('登录已过期，请重新登录', 'error')
        return
      }
      showToast(e?.message || '保存备注失败', 'error')
    } finally {
      retailRemarkSaving.value = false
    }
  }

  async function onAcceptRetailOrder(row) {
    if (!canAcceptRetailOrder(row)) {
      showToast('仅「待接单」且已支付订单可接单', 'error')
      return
    }
    try {
      await ElMessageBox.confirm('确认接单后订单将进入「待发货」，可安排备货与配送。', '确认接单', {
        confirmButtonText: '接单',
        cancelButtonText: '取消',
        type: 'info',
      })
    } catch {
      return
    }
    dispatchLoadingId.value = Number(row.id)
    try {
      await apiJson(
        `/api/admin/orders/retail-orders/${row.id}/accept`,
        { method: 'POST' },
        { auth: true },
      )
      showToast('已接单，订单进入待发货', 'success')
      await fetchRetailOrders()
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        handleAdminLogout()
        return
      }
      showToast(e instanceof Error ? e.message : '接单失败', 'error')
    } finally {
      dispatchLoadingId.value = 0
    }
  }

  async function onPushSfRetailOrder(row) {
    if (!canDispatchActions(row)) {
      showToast('仅「待发货」或「顺丰取消」且已支付订单可推送顺丰', 'error')
      return
    }
    if (row.store_pickup) {
      showToast('门店自提订单不发顺丰', 'error')
      return
    }
    dispatchLoadingId.value = Number(row.id)
    try {
      const r = await apiJson(
        `/api/admin/orders/retail-orders/${row.id}/dispatch/sf-retail`,
        { method: 'POST' },
        { auth: true },
      )
      showToast(r?.message || r?.data?.message || '已推送顺丰', 'success')
      await fetchRetailOrders()
    } catch (e) {
      toastSfPushError(e)
    } finally {
      dispatchLoadingId.value = 0
    }
  }

  function openAssignCourierRetail(row) {
    if (!canDispatchActions(row)) {
      showToast('仅「待发货」或「顺丰取消」订单可指派门店配送员', 'error')
      return
    }
    assignKind.value = 'retail'
    assignOrder.value = row
    assignCourierId.value = row.courier_id ? String(row.courier_id) : ''
    batchAssignMode.value = false
    batchAssignOrders.value = []
    assignOpen.value = true
    void loadCouriers()
  }

  async function onMarkRetailOrderComplete(row) {
    if (!canMarkOrderComplete(row)) {
      showToast('当前订单不可标记完成', 'error')
      return
    }
    markCompleteLoadingId.value = Number(row.id)
    try {
      const data = await apiJson(
        `/api/admin/orders/retail-orders/${row.id}/mark-delivered`,
        { method: 'POST' },
        { auth: true },
      )
      showToast(data?.msg || '已标记完成', 'success')
      await fetchRetailOrders()
    } catch (e) {
      showToast(e instanceof Error ? e.message : '操作失败', 'error')
    } finally {
      markCompleteLoadingId.value = 0
    }
  }

  async function onCancelRetailOrder(row) {
    if (!canCancelOrder(row)) {
      showToast('当前订单不可取消', 'error')
      return
    }
    cancelLoadingId.value = Number(row.id)
    try {
      const data = await apiJson(
        `/api/admin/orders/retail-orders/${row.id}/cancel`,
        { method: 'POST', body: { cancel_sf: true } },
        { auth: true },
      )
      showToast(data?.msg || '已取消', 'success')
      await fetchRetailOrders()
    } catch (e) {
      showToast(e instanceof Error ? e.message : '取消失败', 'error')
    } finally {
      cancelLoadingId.value = 0
    }
  }

  function onRefundWechatRetail(row) {
    if (!canRefundWechatRetail(row)) {
      showToast('仅「已支付」且微信支付的商城订单可原路退款', 'error')
      return
    }
    refundTarget.value = { kind: 'retail', row }
    refundOpen.value = true
  }

  function openRefundWechat(row, kind) {
    if (kind === 'single') {
      if (!canRefundWechatSingle(row)) {
        showToast('仅「已支付」且微信支付的单次订单可原路退款', 'error')
        return
      }
    } else if (!canRefundWechatMall(row)) {
      showToast('仅「已缴」且微信支付的商城卡包订单可原路退款', 'error')
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
        : kind === 'retail'
          ? `/api/admin/orders/retail-orders/${id}/refund/wechat`
          : `/api/admin/orders/mall-card/${id}/refund/wechat`
    try {
      const r = await apiJson(path, { method: 'POST' }, { auth: true })
      const msg =
        r && typeof r === 'object' && typeof r.message === 'string' ? r.message : '退款已受理'
      showToast(msg, 'success')
      refundOpen.value = false
      refundTarget.value = null
      if (kind === 'single') await fetchSingleMeals()
      else if (kind === 'retail') await fetchRetailOrders()
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
    const isRetail = assignKind.value === 'retail'
    const courierPath = isRetail
      ? `/api/admin/orders/retail-orders/${row.id}/dispatch/store-courier`
      : `/api/admin/orders/single-meals/${row.id}/dispatch/store-courier`
    try {
      await apiJson(
        courierPath,
        {
          method: 'POST',
          body: JSON.stringify({ courier_id: cid }),
        },
        { auth: true },
      )
      showToast('已指派配送员', 'success')
      assignOpen.value = false
      if (isRetail) await fetchRetailOrders()
      else await fetchSingleMeals()
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
      toastSfPushBatchOutcome(data, showToast, {
        successText: `已全部提交顺丰（${okCount} 笔）`,
        formatFailLine: (f) => `#${f.order_id}: ${f.message || ''}`,
      })
      clearSingleSelection()
      await fetchSingleMeals()
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        handleAdminLogout()
        return
      }
      toastSfPushError(e instanceof Error ? e.message : '批量推送失败', showToast)
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

  async function fetchSingleMeals(options = {}) {
    const includeSummary = options.includeSummary !== false
    if (!adminAccessToken.value) return
    loading.value = true
    try {
      const q = new URLSearchParams({
        page: String(page.value),
        page_size: String(pageSize.value),
      })
      if (!includeSummary) q.set('include_summary', 'false')
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
      const sm = data && typeof data === 'object' ? data.summary : null
      if (sm && typeof sm === 'object') {
        singleOrderBucketSummary.value = {
          paid: Number(sm.paid) || 0,
          unpaid: Number(sm.unpaid) || 0,
          cancelled: Number(sm.cancelled) || 0,
          pending_ship: Number(sm.pending_ship) || 0,
          retail_inventory_portions: Number(sm.retail_inventory_portions) || 0,
          paid_portions: Number(sm.paid_portions) || 0,
          pending_unpaid_portions: Number(sm.pending_unpaid_portions) || 0,
        }
      } else if (includeSummary) {
        singleOrderBucketSummary.value = null
      }
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        handleAdminLogout()
        return
      }
      showToast(e instanceof Error ? e.message : '加载单次订单失败', 'error')
      singleItems.value = []
      singleTotal.value = 0
      singleOrderBucketSummary.value = null
    } finally {
      loading.value = false
    }
  }

  async function fetchRetailOrders() {
    if (!adminAccessToken.value) return
    loading.value = true
    try {
      const q = new URLSearchParams({
        page: String(page.value),
        page_size: String(pageSize.value),
      })
      const sq = searchQuery.value.trim()
      if (sq) q.set('q', sq)
      const fp = String(retailDeliveryFilter.value || '').trim()
      if (
        fp === 'awaiting_accept' ||
        fp === 'pending_ship' ||
        fp === 'in_delivery' ||
        fp === 'delivered' ||
        fp === 'after_sale'
      ) {
        q.set('fulfillment_phase', fp)
      }
      const data = await apiJson(`/api/admin/orders/daily/retail-orders?${q.toString()}`, {}, { auth: true })
      retailItems.value = Array.isArray(data.items) ? data.items : []
      retailTotal.value = Number(data.total) || 0
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        handleAdminLogout()
        return
      }
      showToast(e instanceof Error ? e.message : '加载商城订单失败', 'error')
      retailItems.value = []
      retailTotal.value = 0
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
      showToast(e instanceof Error ? e.message : '加载卡包订单失败', 'error')
      mallItems.value = []
      mallTotal.value = 0
    } finally {
      loading.value = false
    }
  }

  function fetchActive() {
    if (activeTab.value === 'single') return fetchSingleMeals()
    if (activeTab.value === 'retail') return fetchRetailOrders()
    return fetchMallCardOrders()
  }

  function goPrev() {
    if (page.value <= 1) return
    page.value -= 1
    if (activeTab.value === 'single') {
      void fetchSingleMeals({ includeSummary: false })
      return
    }
    void fetchActive()
  }

  function goNext() {
    if (page.value >= totalPages.value) return
    page.value += 1
    if (activeTab.value === 'single') {
      void fetchSingleMeals({ includeSummary: false })
      return
    }
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

  /** 商城订单不按下单日过滤，切换日期不触发零售列表刷新 */
  const listFilterDeps = computed(() => {
    if (orderKind === 'single') {
      return [orderDate.value, singlePayFilter.value, singleDeliveryFilter.value, pageSize.value]
    }
    if (orderKind === 'retail') {
      return [retailDeliveryFilter.value, pageSize.value]
    }
    return [orderDate.value, mallPayFilter.value, pageSize.value]
  })

  watch(listFilterDeps, () => {
    page.value = 1
    if (orderKind === 'single') clearSingleSelection()
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

  function applyOrdersRouteQuery() {
    const qDate = String(route.query.delivery_date || '').trim()
    if (/^\d{4}-\d{2}-\d{2}$/.test(qDate)) {
      orderDate.value = qDate
    }
  }

  watch(
    () => route.query.delivery_date,
    () => {
      applyOrdersRouteQuery()
    },
  )

  onMounted(() => {
    applyOrdersRouteQuery()
    void loadCouriers()
    void fetchActive()
  })

  return {
    activeTab,
    orderDate,
    searchQuery,
    singlePayFilter,
    singleDeliveryFilter,
    mallPayFilter,
    retailDeliveryFilter,
    dateFilterLabel,
    loading,
    singleItems,
    singleTotal,
    singleOrderBucketSummary,
    mallItems,
    mallTotal,
    retailItems,
    retailTotal,
    page,
    pageSize,
    courierOptions,
    assignOpen,
    assignKind,
    assignOrder,
    assignCourierId,
    dispatchLoadingId,
    refundLoadingId,
    refundOpen,
    refundTarget,
    retailRemarkOpen,
    retailRemarkTarget,
    retailRemarkDraft,
    retailRemarkSaving,
    syncDeliveryLoading,
    singleTableRef,
    selectedSingleRows,
    batchDispatchLoading,
    batchCancelLoading,
    batchMarkCompleteLoading,
    cancelLoadingId,
    markCompleteLoadingId,
    batchAssignMode,
    batchAssignOrders,
    editOpen,
    editOrder,
    editSaving,
    editAddrLoading,
    editMemberAddresses,
    editAddrDraft,
    editAddrAlsoDefault,
    editForm,
    editDialogMemberDisplayName,
    refundDialogMeta,
    totalPages,
    activeTabTotal,
    editHeadCoordDisplay,
    selectedDispatchableRows,
    selectedCancellableRows,
    selectedCompletableRows,
    batchActionBusy,
    onSingleSelectionChange,
    clearSingleSelection,
    singleRowActionLoading,
    onSingleRowMoreCommand,
    onMallRowMoreCommand,
    onRetailRowMoreCommand,
    openRetailRemarkDialog,
    submitRetailRemark,
    onRetailRemarkDialogClosed,
    onBatchPushSfRetail,
    openBatchAssignCourier,
    onBatchMarkComplete,
    onBatchCancelOrders,
    submitRefundWechat,
    submitAssignCourier,
    submitEditOrder,
    onEditAddrMapWarn,
    onEditDialogClosed,
    onAssignDialogClosed,
    onRefundDialogClosed,
    fetchActive,
    goPrev,
    goNext,
    onSyncDeliveryStatus,
    adminAccessToken,
  }
}
