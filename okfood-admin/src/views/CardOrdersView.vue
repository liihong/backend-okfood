<script setup>
defineOptions({ name: 'CardOrdersView' })
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { CreditCard, MapPin, Plus, Search, UserRound, X, Zap } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  handleAdminLogout,
  planDefaultTotal,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import MemberDeliveryMapPicker from '../components/MemberDeliveryMapPicker.vue'

const route = useRoute()

const storeId = ref(1)
/** 已开启且生效的卡包模版（新建工单卡类型下拉） */
const membershipTemplates = ref([])
const membershipTemplatesLoading = ref(false)

const list = ref([])
const loading = ref(false)
const page = ref(1)
/** 每页条数；与接口 page_size 一致；表体在 el-table 内滚动，分页条固定在卡片底部右侧（当前 15 条/页） */
const pageSize = ref(15)
const total = ref(0)

/** 包裹 el-table，用于测量可用高度（px） */
const cardOrdersTableHostRef = ref(null)
/** 表格总高度（含表头）；表体在内部滚动 */
const cardOrdersTableScrollHeight = ref(400)
/** @type {ResizeObserver | null} */
let cardOrdersTableResizeObserver = null

function updateCardOrdersTableHeight() {
  const el = cardOrdersTableHostRef.value
  if (!el) return
  const h = Math.floor(el.getBoundingClientRect().height)
  if (h >= 160) {
    cardOrdersTableScrollHeight.value = h
  }
}
const searchQuery = ref('')
/** 创建时间区间 [YYYY-MM-DD, YYYY-MM-DD]；空表示不限 */
const createdDateRange = ref(null)
const payFilter = ref('')
/** 默认 true：进入页面即查全部历史；取消勾选则仅待处理（未缴或已缴未入账） */
const includeHistory = ref(true)
const hasMore = ref(false)

function ymdInTimeZone(date, timeZone) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
  const parts = fmt.formatToParts(date)
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  return `${map.year}-${map.month}-${map.day}`
}

function todayShanghaiStr() {
  return ymdInTimeZone(new Date(), 'Asia/Shanghai')
}

function shanghaiWallClockHM() {
  const fmt = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Shanghai',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const parts = fmt.formatToParts(new Date())
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  return { hour: Number(map.hour) || 0, minute: Number(map.minute) || 0 }
}

function todayInputDate() {
  return todayShanghaiStr()
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

/** 是否可翻下一页：有 has_more 或尚未到末页 */
const canGoNext = computed(() => hasMore.value || page.value < totalPages.value)

/** 表格序号（跨页连续） */
function tableRowIndex(index) {
  return (page.value - 1) * pageSize.value + index + 1
}

function payStatusClass(s) {
  if (s === '已缴') return 'member-pill member-pill--emerald'
  return 'member-pill member-pill--amber'
}

function planTagClass(kind) {
  if (kind === '周卡') return 't-plan--week'
  if (kind === '月卡') return 't-plan--month'
  return 't-plan--count'
}

/** 工单/模版餐段展示：午餐 / 晚餐 / 午+晚 */
function mealPeriodsLabel(periods) {
  const ps = Array.isArray(periods) ? periods : ['lunch']
  const hasL = ps.includes('lunch')
  const hasD = ps.includes('dinner')
  if (hasL && hasD) return '午+晚'
  if (hasD) return '晚餐'
  return '午餐'
}

function mealPeriodBadgeClass(periods) {
  const ps = Array.isArray(periods) ? periods : ['lunch']
  const hasL = ps.includes('lunch')
  const hasD = ps.includes('dinner')
  if (hasL && hasD) return 'co-meal-period--both'
  if (hasD) return 'co-meal-period--dinner'
  return 'co-meal-period--lunch'
}

/** 卡包模版下拉文案：名称 + 种类 + 餐段 + 入账次数 */
function templateOptionLabel(t) {
  const periods = Array.isArray(t.meal_periods) ? t.meal_periods : ['lunch']
  return `${t.name}（${t.kind_label || '卡包'} · ${mealPeriodsLabel(periods)} · +${t.meals_grant} 次）`
}

/** 列表格内备注（列宽加大后以换行展示全文；空为 —） */
function remarkPreview(text) {
  const t = (text == null ? '' : String(text)).trim()
  if (!t) return '—'
  return t
}

/** 列表「实收」列：按元展示整数（不改变接口字段） */
function formatAmountYuanInteger(v) {
  if (v === null || v === undefined) return '—'
  const s = String(v).trim()
  if (!s) return '—'
  const n = Number(s)
  if (!Number.isFinite(n)) return '—'
  return String(Math.round(n))
}

/** 创建人 + 时间（可与列内换行；hover title 仍为完整串） */
function cardOrderCreatedLine(row) {
  const who = (row.created_by == null ? '' : String(row.created_by).trim())
  const iso = row.created_at
  let when = ''
  if (iso) {
    const x = String(iso).replace('T', ' ').trim()
    const m = x.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/)
    when = m ? `${m[2]}-${m[3]} ${m[4]}:${m[5]}` : x.slice(0, 16)
  }
  if (who && when) return `${who} · ${when}`
  if (who) return who
  if (when) return when
  return '—'
}

async function fetchList(extraParams = {}) {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const q = searchQuery.value.trim()
    if (q) params.set('q', q)
    const pf = String(payFilter.value ?? '').trim()
    if (pf === '未缴' || pf === '已缴') params.set('pay_status', pf)
    if (includeHistory.value) params.set('include_history', 'true')
    const dr = createdDateRange.value
    if (Array.isArray(dr) && dr.length === 2) {
      const [from, to] = dr
      if (from) params.set('date_from', String(from))
      if (to) params.set('date_to', String(to))
    }
    for (const [k, v] of Object.entries(extraParams)) {
      if (v != null && String(v).trim() !== '') params.set(k, String(v))
    }
    const data = await apiJson(`/api/admin/card-orders?${params.toString()}`, {}, { auth: true })
    list.value = Array.isArray(data.items) ? data.items : []
    if (data.total != null) {
      total.value = Number(data.total) || 0
    }
    hasMore.value = Boolean(data.has_more)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载工单失败', 'error')
  } finally {
    loading.value = false
  }
}

let searchTimer = 0
watch(searchQuery, () => {
  if (!adminAccessToken.value) return
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    page.value = 1
    void fetchList()
  }, 320)
})

watch(payFilter, () => {
  page.value = 1
  void fetchList()
})

watch(includeHistory, () => {
  page.value = 1
  void fetchList()
})

watch(createdDateRange, () => {
  page.value = 1
  void fetchList()
})

const goPrev = () => {
  if (page.value <= 1) return
  page.value -= 1
  void fetchList()
}

const goNext = () => {
  if (!canGoNext.value) return
  page.value += 1
  void fetchList()
}

/** --- 新建工单 --- */
const showCreateModal = ref(false)
const createSubmitting = ref(false)
const createForm = ref({
  open_mode: 'new_member',
  phone: '',
  name: '',
  wechat_name: '',
  delivery_start_mode: 'date',
  delivery_start_date: todayInputDate(),
  membership_template_id: null,
  pay_channel: '微信',
  pay_status: '已缴',
  amount_yuan: '',
  remark: '',
  delivery_lng: '',
  delivery_lat: '',
  map_location_text: '',
  door_detail: '',
})

/** 续卡：按手机号预查会员档案 */
const renewPreview = ref(null)
const renewPreviewLoading = ref(false)
let renewDebounce = 0

function scheduleRenewPreview() {
  window.clearTimeout(renewDebounce)
  renewDebounce = window.setTimeout(() => {
    void loadRenewPreview()
  }, 380)
}

async function loadRenewPreview() {
  if (createForm.value.open_mode !== 'renew') return
  const phone = (createForm.value.phone || '').trim()
  if (phone.length < 5) {
    renewPreview.value = null
    return
  }
  if (!adminAccessToken.value) return
  renewPreviewLoading.value = true
  try {
    const params = new URLSearchParams({ page: '1', page_size: '10', q: phone })
    const data = await apiJson(`/api/admin/users?${params}`, {}, { auth: true })
    const items = Array.isArray(data.items) ? data.items : []
    renewPreview.value = items.find((x) => String(x.phone || '') === phone) || null
  } catch {
    renewPreview.value = null
  } finally {
    renewPreviewLoading.value = false
  }
}

function onCreatePhoneInput() {
  if (createForm.value.open_mode === 'renew') scheduleRenewPreview()
}

/** 新建工单当前选中的卡包模版 */
const selectedCreateTemplate = computed(() => {
  const id = createForm.value.membership_template_id
  if (id == null) return null
  return membershipTemplates.value.find((t) => Number(t.id) === Number(id)) || null
})

async function loadMembershipTemplates() {
  if (!adminAccessToken.value) return
  membershipTemplatesLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/catalog/membership-templates?store_id=${storeId.value}&active_only=true`,
      {},
      { auth: true },
    )
    membershipTemplates.value = Array.isArray(data) ? data : []
    if (membershipTemplates.value.length > 0) {
      const cur = createForm.value.membership_template_id
      const hit = cur != null && membershipTemplates.value.some((t) => Number(t.id) === Number(cur))
      if (!hit) {
        createForm.value.membership_template_id = Number(membershipTemplates.value[0].id)
      }
    } else {
      createForm.value.membership_template_id = null
    }
  } catch (e) {
    membershipTemplates.value = []
    createForm.value.membership_template_id = null
    showToast(e instanceof Error ? e.message : '加载卡包模版失败', 'error')
  } finally {
    membershipTemplatesLoading.value = false
  }
}

/** 续卡：仍有剩余且未暂停 → 仅叠加次数，不改起送日 */
const renewStillDelivering = computed(() => {
  const p = renewPreview.value
  if (!p || createForm.value.open_mode !== 'renew') return false
  const bal = Number(p.balance) || 0
  if (bal <= 0) return false
  return !p.delivery_deferred
})

/** 续卡：档案已有起送日且未暂停 → 可选「保持当前配送安排」 */
const renewCanKeepSchedule = computed(() => {
  const p = renewPreview.value
  if (!p || createForm.value.open_mode !== 'renew') return false
  if (p.delivery_deferred) return false
  const ds = p.delivery_start_date ? String(p.delivery_start_date).slice(0, 10) : ''
  return ds.length >= 10
})

const renewActivationOptionCount = computed(() => {
  if (createForm.value.open_mode === 'renew' && renewStillDelivering.value) return 0
  if (createForm.value.open_mode === 'renew' && renewCanKeepSchedule.value) return 3
  return 2
})

/** 指定起送日为今日时的说明（仅文案，不限制可选日期） */
const activationStartDateHint = computed(() => {
  if (createForm.value.delivery_start_mode !== 'date') return ''
  if (createForm.value.open_mode === 'renew' && renewStillDelivering.value) return ''
  const d = (createForm.value.delivery_start_date || '').trim()
  if (d !== todayShanghaiStr()) return ''
  const { hour, minute } = shanghaiWallClockHM()
  if (hour > 8 || (hour === 8 && minute >= 50)) {
    return {
      type: 'info',
      text: '已过当日 08:50 备餐推单窗口。今日能否进配送大表视备餐与厨房安排而定；有加备餐需今日配送时请继续选今日，并与厨房确认。',
    }
  }
  return {
    type: 'info',
    text: '已选今日起送：入账后若当日为配送日、余额与请假规则满足，可进入当日大表。',
  }
})

function applyRenewActivationDefaults() {
  if (createForm.value.open_mode !== 'renew') return
  if (renewStillDelivering.value) {
    createForm.value.delivery_start_mode = 'keep_schedule'
    return
  }
  if (renewCanKeepSchedule.value) {
    createForm.value.delivery_start_mode = 'keep_schedule'
  } else {
    createForm.value.delivery_start_mode = 'date'
    createForm.value.delivery_start_date = todayShanghaiStr()
  }
}

/** 续卡同步入账后：剩余、总次数均 +本次卡次数 */
const renewSyncPreview = computed(() => {
  const p = renewPreview.value
  if (!p || createForm.value.open_mode !== 'renew') return null
  const bal = Number(p.balance) || 0
  const tpl = selectedCreateTemplate.value
  const add = tpl != null ? Number(tpl.meals_grant) || 0 : null
  if (add == null || add <= 0) return null
  const mqt = Number(p.meal_quota_total)
  const planBase = planDefaultTotal(p.plan_type)
  const curTotal =
    Number.isFinite(mqt) && mqt > 0
      ? mqt
      : planBase != null
        ? Math.max(planBase, bal)
        : bal
  return {
    curBal: bal,
    curTotal,
    add,
    nextBal: bal + add,
    nextTotal: curTotal + add,
  }
})

watch(
  () => createForm.value.open_mode,
  (mode) => {
    renewPreview.value = null
    if (mode === 'renew') {
      scheduleRenewPreview()
    } else {
      createForm.value.delivery_start_mode = 'date'
      createForm.value.delivery_start_date = todayShanghaiStr()
    }
  },
)

watch(renewPreview, () => {
  applyRenewActivationDefaults()
})

function onDeliveryMapWarn(msg) {
  showToast(msg || '地图提示', 'error')
}

function openCreateModal() {
  renewPreview.value = null
  createForm.value = {
    open_mode: 'new_member',
    phone: '',
    name: '',
    wechat_name: '',
    delivery_start_mode: 'date',
    delivery_start_date: todayInputDate(),
    membership_template_id: null,
    pay_channel: '微信',
    pay_status: '已缴',
    amount_yuan: '',
    remark: '',
    delivery_lng: '',
    delivery_lat: '',
    map_location_text: '',
    door_detail: '',
  }
  showCreateModal.value = true
  void loadMembershipTemplates()
}

async function submitCreate() {
  const phone = (createForm.value.phone || '').trim()
  if (!phone) {
    showToast('请填写会员手机号', 'error')
    return
  }
  const openMode = createForm.value.open_mode === 'renew' ? 'renew' : 'new_member'
  if (openMode === 'new_member') {
    const memberName = (createForm.value.name || '').trim()
    if (!memberName) {
      showToast('请填写会员姓名', 'error')
      return
    }
    const wxNick = (createForm.value.wechat_name || '').trim()
    if (!wxNick) {
      showToast('请填写微信昵称', 'error')
      return
    }
  }
  const keepSchedule =
    createForm.value.open_mode === 'renew' &&
    (renewStillDelivering.value || createForm.value.delivery_start_mode === 'keep_schedule')
  const deferStart = createForm.value.delivery_start_mode === 'defer'
  let startD = null
  if (!keepSchedule && !deferStart) {
    startD = (createForm.value.delivery_start_date || '').trim()
    if (!startD) {
      showToast('请选择开始配送日期', 'error')
      return
    }
    const today = todayShanghaiStr()
    if (startD < today) {
      showToast('起送日不能早于今日（上海业务日）', 'error')
      return
    }
  }

  const lngS = (createForm.value.delivery_lng || '').trim()
  const latS = (createForm.value.delivery_lat || '').trim()
  const mapT = (createForm.value.map_location_text || '').trim()
  const doorT = (createForm.value.door_detail || '').trim()
  const lngN = Number(lngS)
  const latN = Number(latS)
  const hasCoords = lngS !== '' && latS !== '' && Number.isFinite(lngN) && Number.isFinite(latN)
  const wantsDelivery = hasCoords || mapT !== '' || doorT !== ''
  if (wantsDelivery) {
    if (!hasCoords) {
      showToast('录入配送地址时请使用地图搜索或点击地图选点', 'error')
      return
    }
    if (!mapT) {
      showToast('请填写地图详细地址（搜索选点或点击地图后自动填入，可手动修改）', 'error')
      return
    }
  }

  const tplId = createForm.value.membership_template_id
  if (tplId == null || !Number.isFinite(Number(tplId))) {
    showToast('请选择卡类型（暂无已开启的卡包模版时，请先在会员卡管理中创建并开启）', 'error')
    return
  }

  createSubmitting.value = true
  try {
    const body = {
      phone,
      open_mode: openMode,
      delivery_start_date: keepSchedule || deferStart ? null : startD,
      defer_delivery_activation: deferStart,
      membership_template_id: Math.floor(Number(tplId)),
      pay_channel: createForm.value.pay_channel,
      pay_status: createForm.value.pay_status,
    }
    if (openMode === 'new_member') {
      body.name = (createForm.value.name || '').trim()
      body.wechat_name = (createForm.value.wechat_name || '').trim()
    }
    const ay = String(createForm.value.amount_yuan || '').trim()
    if (ay !== '') {
      const n = Number(ay)
      if (!Number.isFinite(n) || n < 0) {
        showToast('实收金额无效', 'error')
        return
      }
      body.amount_yuan = n
    }
    const rm = (createForm.value.remark || '').trim()
    if (rm) body.remark = rm
    if (wantsDelivery && hasCoords && mapT) {
      body.delivery_address = {
        lng: lngN,
        lat: latN,
        map_location_text: mapT.slice(0, 500),
        door_detail: doorT ? doorT.slice(0, 500) : null,
      }
    }
    await apiJson('/api/admin/card-orders', { method: 'POST', body: JSON.stringify(body) }, { auth: true })
    showToast('工单已创建')
    showCreateModal.value = false
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '创建失败', 'error')
  } finally {
    createSubmitting.value = false
  }
}

/** --- 更新工单 --- */
const showEditModal = ref(false)
const editSubmitting = ref(false)
const editForm = ref({
  id: 0,
  member_phone: '',
  member_name: '',
  member_wechat_name: '',
  membership_template_id: null,
  meal_periods: ['lunch'],
  template_product_label: '',
  delivery_start_mode: 'date',
  delivery_start_date: '',
  pay_channel: '微信',
  pay_status: '未缴',
  amount_yuan: '',
  remark: '',
  applied_to_member: false,
  created_by: '',
})

/** 更新工单当前选中的卡包模版 */
const selectedEditTemplate = computed(() => {
  const id = editForm.value.membership_template_id
  if (id == null) return null
  return membershipTemplates.value.find((t) => Number(t.id) === Number(id)) || null
})

/** 更新工单卡包模版展示文案（已入账只读、下拉无匹配时兜底） */
const editTemplateDisplayLabel = computed(() => {
  const productLabel = (editForm.value.template_product_label || '').trim()
  if (productLabel) return productLabel
  const tpl = selectedEditTemplate.value
  if (tpl) return templateOptionLabel(tpl)
  const id = editForm.value.membership_template_id
  if (id != null) return `模版#${id}`
  return '—'
})

/** 确保当前工单绑定的卡包在下拉选项中（含已下架/未开启，避免 el-select 只显示 id） */
function ensureEditTemplateOptionVisible() {
  const cur = editForm.value.membership_template_id
  if (cur == null) return
  if (membershipTemplates.value.some((t) => Number(t.id) === Number(cur))) return
  membershipTemplates.value = [
    {
      id: cur,
      name: editForm.value.template_product_label || `模版#${cur}`,
      kind_label: '',
      meals_grant: 0,
      meal_periods: editForm.value.meal_periods,
      is_active: false,
    },
    ...membershipTemplates.value,
  ]
}

function openEditModal(row) {
  const ds = row.delivery_start_date ? String(row.delivery_start_date).slice(0, 10) : ''
  editForm.value = {
    id: row.id,
    member_phone: row.member_phone || '',
    member_name: row.member_name || '',
    member_wechat_name: row.member_wechat_name || '',
    membership_template_id:
      row.membership_template_id != null ? Number(row.membership_template_id) : null,
    meal_periods: Array.isArray(row.meal_periods) ? [...row.meal_periods] : ['lunch'],
    template_product_label: row.template_product_label || '',
    delivery_start_mode: ds ? 'date' : 'defer',
    delivery_start_date: ds || todayInputDate(),
    pay_channel: row.pay_channel || '微信',
    pay_status: row.pay_status || '未缴',
    amount_yuan: row.amount_yuan != null && row.amount_yuan !== '' ? String(row.amount_yuan) : '',
    remark: row.remark || '',
    applied_to_member: !!row.applied_to_member,
    created_by: row.created_by || '',
  }
  ensureEditTemplateOptionVisible()
  showEditModal.value = true
  void loadMembershipTemplatesForEdit()
}

async function loadMembershipTemplatesForEdit() {
  if (!adminAccessToken.value) return
  membershipTemplatesLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/catalog/membership-templates?store_id=${storeId.value}&active_only=true`,
      {},
      { auth: true },
    )
    membershipTemplates.value = Array.isArray(data) ? data : []
    // 已入账或模版已下架：保留当前绑定 id，避免下拉只显示数字
    ensureEditTemplateOptionVisible()
  } catch (e) {
    membershipTemplates.value = []
    showToast(e instanceof Error ? e.message : '加载卡包模版失败', 'error')
  } finally {
    membershipTemplatesLoading.value = false
  }
}

async function tryOpenOrderFromRouteQuery() {
  const raw = route.query?.order_id ?? route.query?.orderId
  const oid = parseInt(String(raw || ''), 10)
  if (!Number.isFinite(oid) || oid <= 0) return
  await fetchList({ order_id: String(oid) })
  const row = list.value.find((r) => Number(r.id) === oid)
  if (row) openEditModal(row)
}

const deletingId = ref(0)

async function deleteCardOrder(row) {
  if (!row || !row.id) return
  const phone = (row.member_phone || '').trim()
  const label = `#${row.id} ${phone ? phone : '会员'}`
  try {
    await ElMessageBox.confirm(
      `${label}\n\n删除后不可恢复。若工单已缴或已同步入账，系统可能拒绝删除（以提示为准）。`,
      '确定删除该开卡工单？',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  deletingId.value = row.id
  try {
    await apiJson(`/api/admin/card-orders/${row.id}`, { method: 'DELETE' }, { auth: true })
    showToast('工单已删除')
    await fetchList()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  } finally {
    deletingId.value = 0
  }
}

async function submitEdit(syncMember = false) {
  if (!editForm.value.id) return
  const deferEdit = editForm.value.delivery_start_mode === 'defer'
  let editStartD = null
  if (!deferEdit) {
    editStartD = (editForm.value.delivery_start_date || '').trim()
    if (!editStartD) {
      showToast('请选择开始配送日', 'error')
      return
    }
  }
  if (syncMember) {
    if (editForm.value.pay_status !== '已缴') {
      showToast('仅「已缴」工单可确认入账', 'error')
      return
    }
    if (editForm.value.applied_to_member) {
      showToast('该工单已入账', 'error')
      return
    }
    if (deferEdit) {
      showToast('确认入账前请指定起送日', 'error')
      return
    }
    const phone = (editForm.value.member_phone || '').trim()
    const label = `#${editForm.value.id} ${phone || '会员'}`
    try {
      await ElMessageBox.confirm(
        '将写入会员剩余次数与套餐，并按起送日激活（若已指定）。',
        `确认将工单 ${label} 同步入账？`,
        { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' },
      )
    } catch {
      return
    }
  }
  editSubmitting.value = true
  try {
    const body = {
      delivery_start_date: deferEdit ? null : editStartD,
      pay_channel: editForm.value.pay_channel,
      pay_status: editForm.value.pay_status,
      sync_member: syncMember,
    }
    if (!editForm.value.applied_to_member) {
      const tplId = editForm.value.membership_template_id
      if (tplId == null || !Number.isFinite(Number(tplId))) {
        showToast('请选择卡包模版（暂无已开启模版时请先在会员卡管理中创建并开启）', 'error')
        return
      }
      body.membership_template_id = Math.floor(Number(tplId))
    }
    const ay = String(editForm.value.amount_yuan || '').trim()
    if (ay !== '') {
      const n = Number(ay)
      if (!Number.isFinite(n) || n < 0) {
        showToast('实收金额无效', 'error')
        return
      }
      body.amount_yuan = n
    } else {
      body.amount_yuan = null
    }
    const rm = (editForm.value.remark || '').trim()
    body.remark = rm || null
    await apiJson(
      `/api/admin/card-orders/${editForm.value.id}`,
      { method: 'PATCH', body: JSON.stringify(body) },
      { auth: true },
    )
    showToast(syncMember ? '已同步入账' : '工单已更新')
    showEditModal.value = false
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    editSubmitting.value = false
  }
}

onMounted(async () => {
  await fetchList()
  await tryOpenOrderFromRouteQuery()
  void nextTick(() => {
    updateCardOrdersTableHeight()
    cardOrdersTableResizeObserver = new ResizeObserver(() => {
      updateCardOrdersTableHeight()
    })
    if (cardOrdersTableHostRef.value) {
      cardOrdersTableResizeObserver.observe(cardOrdersTableHostRef.value)
    }
  })
})

onUnmounted(() => {
  cardOrdersTableResizeObserver?.disconnect()
  cardOrdersTableResizeObserver = null
})
</script>

<template>
 <section class="tab-content animate-up card-orders-page card-orders-view-fill">
    <div class="table-container table-container--card-orders-fill">
      <div class="table-header table-header--members table-header--couriers-row">
        <div class="search-box search-box--flex">
          <Search :size="18" />
          <el-input v-model="searchQuery" clearable placeholder="搜索手机、姓名或微信昵称…" />
        </div>
        <div class="card-orders-filter-label card-orders-filter-el card-orders-created-range">
          <span class="card-orders-filter-el-text">创建</span>
          <el-date-picker
            v-model="createdDateRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            clearable
            teleported
            class="card-orders-created-picker"
          />
        </div>
        <div class="card-orders-filters">
         <div class="card-orders-filter-label card-orders-filter-label--check">
            <el-checkbox v-model="includeHistory" class="card-orders-history-el-checkbox">
              查看历史开卡记录
            </el-checkbox>
            <span v-if="!includeHistory" class="card-orders-pending-hint">当前：待审批工单</span>
          </div>
          <div class="card-orders-filter-label card-orders-filter-el">
            <span class="card-orders-filter-el-text">缴费</span>
            <el-select v-model="payFilter" placeholder="全部" clearable class="card-orders-pay-select">
              <el-option label="全部" value="" />
              <el-option label="未缴" value="未缴" />
              <el-option label="已缴" value="已缴" />
            </el-select>
          </div>
          <button type="button" class="btn-primary btn-primary--sm" @click="openCreateModal">
            <Plus :size="18" /> 新建开卡工单
          </button>
        </div>
      </div>

      <div ref="cardOrdersTableHostRef" class="members-table-host">
        <AdminTable
          class="card-orders-table"
          variant="members"
          size="small"
          :data="list"
          :loading="loading"
          row-key="id"
          empty-text="暂无工单"
          :height="cardOrdersTableScrollHeight"
        >
       <el-table-column label="序号" width="72" align="center" class-name="td-mono td-co-idx">
          <template #default="{ $index }">
            <span class="co-cell-pill co-cell-pill--idx">{{ tableRowIndex($index) }}</span>
          </template>
        </el-table-column>
       <el-table-column label="单号" width="80" class-name="td-mono td-co-id">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
       <el-table-column label="会员信息" min-width="120" class-name="td-co-name">
          <template #default="{ row }">
            <div class="co-member-info">
              <div class="co-member-name" :title="row.member_name || ''">{{
                row.member_name || '—'
              }}</div>
              <div v-if="(row.member_wechat_name || '').trim()" class="t-sub t-wechat">
                微信 {{ (row.member_wechat_name || '').trim() }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="卡状态"
          width="76"
          min-width="68"
          align="center"
          class-name="co-nowrap td-co-card-kind"
        >
          <template #default="{ row }">
            <span v-if="row.card_kind" class="t-plan co-plan-tag" :class="planTagClass(row.card_kind)">{{
              row.card_kind
            }}</span>
            <span v-else class="co-card-kind-empty">—</span>
          </template>
        </el-table-column>
        <el-table-column
          label="餐段"
          width="76"
          min-width="68"
          align="center"
          class-name="co-nowrap td-co-meal-period"
        >
          <template #default="{ row }">
            <span
              class="co-meal-period-badge"
              :class="mealPeriodBadgeClass(row.meal_periods)"
              :title="mealPeriodsLabel(row.meal_periods)"
            >
              {{ mealPeriodsLabel(row.meal_periods) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="电话" width="118" min-width="108" class-name="td-mono co-nowrap td-co-phone-col">
          <template #default="{ row }">
            <span :title="(row.member_phone || '').trim() || undefined">{{
              (row.member_phone || '').trim() || '—'
            }}</span>
          </template>
        </el-table-column>
       <el-table-column
          label="起送日"
          width="118"
          min-width="112"
          class-name="td-mono co-nowrap td-co-start-date"
        >
          <template #default="{ row }">{{ row.delivery_start_date || '—' }}</template>
        </el-table-column>
       <el-table-column prop="pay_channel" label="渠道" width="72" min-width="68" class-name="co-nowrap td-co-channel" />
        <el-table-column label="状态" width="76" min-width="70" class-name="co-nowrap td-co-pay-status">
          <template #default="{ row }">
            <span :class="payStatusClass(row.pay_status)">{{ row.pay_status }}</span>
          </template>
        </el-table-column>
       <el-table-column
          label="实收"
          align="right"
          width="88"
          min-width="80"
          class-name="td-mono co-nowrap td-co-amt-col"
        >
          <template #default="{ row }">
           <span class="co-cell-pill co-cell-pill--amount">
              {{ formatAmountYuanInteger(row.amount_yuan) }}
            </span>
          </template>
        </el-table-column>
       <el-table-column label="入账" width="92" min-width="86" align="center" class-name="co-nowrap td-co-sync">
          <template #default="{ row }">
            <span
class="member-pill"
              :class="row.applied_to_member ? 'member-pill--emerald' : 'member-pill--slate'"
            >
              {{ row.applied_to_member ? '已同步' : '未同步' }}
            </span>
          </template>
        </el-table-column>
       <el-table-column label="备注" min-width="268" class-name="td-co-remark">
          <template #default="{ row }">
            <span class="co-remark-text" :title="(row.remark || '').trim() || undefined">{{
              remarkPreview(row.remark)
            }}</span>
          </template>
        </el-table-column>
       <el-table-column label="创建" min-width="228" class-name="td-co-created">
          <template #default="{ row }">
           <span class="co-created-line" :title="`${row.created_by || ''} ${row.created_at || ''}`">{{
              cardOrderCreatedLine(row)
            }}</span>
          </template>
        </el-table-column>
       <el-table-column label="操作" align="right" width="152" fixed="right" class-name="td-co-actions">
          <template #default="{ row }">
            <span class="co-row-actions">
              <button type="button" class="btn-sm" @click="openEditModal(row)">更新</button>
              <button
                type="button"
                class="btn-sm danger"
                :disabled="deletingId === row.id"
                @click="deleteCardOrder(row)"
              >
                {{ deletingId === row.id ? '…' : '删除' }}
              </button>
            </span>
          </template>
        </el-table-column>
        </AdminTable>
      </div>
      <div v-if="adminAccessToken" class="members-pagination">
        <button type="button" class="btn-sm" :disabled="page <= 1" @click="goPrev">上一页</button>
        <span class="members-page-meta">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
        <button type="button" class="btn-sm" :disabled="!canGoNext" @click="goNext">
          下一页
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div
        v-if="showCreateModal"
        class="modal-overlay"
        v-esc-close="() => (showCreateModal = false)"
        @click.self="showCreateModal = false"
      >
        <div class="modal-card modal-card--card-order-create">
        <div class="modal-header">
          <div class="header-info">
            <h3>新建开卡工单</h3>
            <p>MEMBER CARD ORDER</p>
          </div>
          <button type="button" class="close-btn" @click="showCreateModal = false">
            <X :size="20" />
          </button>
        </div>
        <form
          class="modal-form modal-form--card-order modal-form--co-create-split"
          @submit.prevent="submitCreate"
        >
          <!-- 左侧：会员资料 + 卡项费用 + 激活 -->
          <div class="co-create-split-main">
            <div class="co-create-panel">
              <div class="co-create-panel-title co-create-panel-title--with-icon">
                <UserRound class="co-create-panel-title-icon" :size="18" :stroke-width="2.25" aria-hidden="true" />
                会员基本资料
              </div>
              <div class="form-group open-mode-group">
                <label>办理类型</label>
                <el-radio-group v-model="createForm.open_mode" class="co-open-mode-radio-group">
                  <div class="open-mode-options">
                    <el-radio value="new_member" border class="co-open-mode-radio-item">
                      <div class="co-open-mode-radio-body">
                        <span class="radio-tile-title">新会员开卡</span>
                        <span class="radio-tile-sub">填写姓名、微信昵称并写入档案</span>
                      </div>
                    </el-radio>
                    <el-radio value="renew" border class="co-open-mode-radio-item">
                      <div class="co-open-mode-radio-body">
                        <span class="radio-tile-title">老会员续卡</span>
                        <span class="radio-tile-sub">仅核对手机号；入账叠加剩余与总次数</span>
                      </div>
                    </el-radio>
                  </div>
                </el-radio-group>
              </div>
              <div
                class="co-create-member-fields"
                :class="
                  createForm.open_mode === 'renew'
                    ? 'co-create-renew-phone-row'
                    : 'co-create-member-grid'
                "
              >
                <div class="form-group">
                  <label>会员手机号</label>
                  <el-input
                    v-model="createForm.phone"
                    maxlength="20"
                    clearable
                    :placeholder="
                      createForm.open_mode === 'new_member' ? '请输入11位手机号' : '已注册会员的手机号'
                    "
                    @input="onCreatePhoneInput"
                  />
                </div>
                <template v-if="createForm.open_mode === 'new_member'">
                  <div class="form-group">
                    <label>会员姓名</label>
                    <el-input v-model="createForm.name" maxlength="100" placeholder="写入档案 name" clearable />
                  </div>
                  <div class="form-group">
                    <label>微信昵称</label>
                    <el-input
                      v-model="createForm.wechat_name"
                      maxlength="100"
                      placeholder="写入档案 wechat_name"
                      clearable
                    />
                  </div>
                </template>
                <div v-else class="form-group co-create-renew-match-col">
                  <label class="co-create-renew-match-label">档案匹配</label>
                  <div class="renew-preview-box renew-preview-box--aside">
                    <p v-if="renewPreviewLoading" class="modal-hint">正在查询该手机号会员…</p>
                    <template v-else-if="renewPreview">
                      <p class="modal-hint">
                        已匹配：<strong>{{ renewPreview.name || '—' }}</strong>
                        · 套餐 {{ renewPreview.plan_type || '—' }}
                        · 当前剩余 <strong>{{ Number(renewPreview.balance) || 0 }}</strong>
                        次
                        <template v-if="renewPreview.delivery_start_date">
                          · 起送日 {{ String(renewPreview.delivery_start_date).slice(0, 10) }}
                        </template>
                        <template v-if="renewPreview.delivery_deferred"> · 已暂停配送</template>
                      </p>
                      <p v-if="renewStillDelivering" class="modal-hint modal-hint--accent">
                        仍在履约中，续卡仅叠加次数，不修改起送日与配送安排。
                      </p>
                      <p v-else-if="renewSyncPreview" class="modal-hint modal-hint--accent">
                        同步入账后约：<strong>剩余 {{ renewSyncPreview.nextBal }}</strong> /
                        <strong>总 {{ renewSyncPreview.nextTotal }}</strong>
                        （本次 +{{ renewSyncPreview.add }}）
                      </p>
                    </template>
                    <p
                      v-else-if="(createForm.phone || '').trim().length >= 5"
                      class="modal-hint modal-hint--warn"
                    >
                      未找到该手机号会员，请确认已注册或改用「新会员开卡」。
                    </p>
                    <p v-else class="modal-hint co-create-renew-match-placeholder">
                      请在左侧输入手机号后将自动检索档案。
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div class="co-create-panel">
              <div class="co-create-panel-title co-create-panel-title--with-icon">
                <CreditCard class="co-create-panel-title-icon" :size="18" :stroke-width="2.25" aria-hidden="true" />
                卡项与费用配置
              </div>
              <div class="co-create-fees-row3">
                <div class="form-group">
                  <label>卡类型</label>
                  <el-select
                    v-model="createForm.membership_template_id"
                    class="co-create-fees-select"
                    :loading="membershipTemplatesLoading"
                    :disabled="!membershipTemplates.length"
                    placeholder="请选择已开启的卡包"
                  >
                    <el-option
                      v-for="t in membershipTemplates"
                      :key="t.id"
                      :value="Number(t.id)"
                      :label="templateOptionLabel(t)"
                    />
                  </el-select>
                  <p
                    v-if="!membershipTemplatesLoading && !membershipTemplates.length"
                    class="modal-hint modal-hint--warn"
                  >
                    暂无已开启的卡包模版，请先在「会员卡管理」中创建并开启。
                  </p>
                </div>
                <div class="form-group">
                  <label>缴费渠道</label>
                  <el-select v-model="createForm.pay_channel" class="co-create-fees-select">
                    <el-option label="微信" value="微信" />
                    <el-option label="支付宝" value="支付宝" />
                    <el-option label="线下" value="线下" />
                  </el-select>
                </div>
                <div class="form-group">
                  <label>缴费状态</label>
                  <el-select
                    v-model="createForm.pay_status"
                    class="co-create-fees-select co-create-pay-status-select"
                    :class="{ 'co-create-pay-status-select--paid': createForm.pay_status === '已缴' }"
                  >
                    <el-option label="未缴" value="未缴" />
                    <el-option label="已缴" value="已缴" />
                  </el-select>
                </div>
              </div>
              <div class="co-create-fees-row2">
                <div class="form-group">
                  <label>实收金额</label>
                  <el-input v-model="createForm.amount_yuan" placeholder="留空表示未填" clearable />
                </div>
                <div class="form-group co-create-remark-field">
                  <label>备注</label>
                  <el-input v-model="createForm.remark" type="textarea" :rows="2" maxlength="500" placeholder="可选" />
                </div>
              </div>
            </div>

            <div class="co-create-panel co-create-panel--activation">
              <div class="co-create-panel-title co-create-panel-title--with-icon">
                <Zap class="co-create-panel-title-icon" :size="18" :stroke-width="2.25" aria-hidden="true" />
                激活设置
              </div>
              <div class="co-create-activation-row">
                <el-alert
                  v-if="createForm.open_mode === 'renew' && renewStillDelivering"
                  type="success"
                  :closable="false"
                  show-icon
                  class="co-renew-activation-alert"
                  title="保持当前配送安排"
                  description="该会员仍有剩余次数且未暂停，续卡仅叠加次数，不会修改档案中的起送日。"
                />
                <template v-else>
                  <el-radio-group v-model="createForm.delivery_start_mode" class="co-activation-radio-group">
                    <div
                      class="open-mode-options open-mode-options--activation"
                      :class="{
                        'open-mode-options--activation-3': renewActivationOptionCount === 3,
                      }"
                    >
                      <el-radio
                        v-if="createForm.open_mode === 'renew' && renewCanKeepSchedule"
                        value="keep_schedule"
                        border
                        class="co-activation-radio-item"
                      >
                        <div class="co-open-mode-radio-body">
                          <span class="radio-tile-title">保持当前配送安排</span>
                          <span class="radio-tile-sub">不修改档案起送日，续卡后按原节奏进配送大表</span>
                        </div>
                      </el-radio>
                      <el-radio value="date" border class="co-activation-radio-item">
                        <div class="co-open-mode-radio-body">
                          <span class="radio-tile-title">指定起送日</span>
                          <span class="radio-tile-sub">选择具体业务日起参与配送大表</span>
                        </div>
                      </el-radio>
                      <el-radio value="defer" border class="co-activation-radio-item">
                        <div class="co-open-mode-radio-body">
                          <span class="radio-tile-title">暂不开卡</span>
                          <span class="radio-tile-sub">已缴仍入次数与套餐；暂不写入起送日，可日后在「更新」中补日期</span>
                        </div>
                      </el-radio>
                    </div>
                  </el-radio-group>
                  <div
                    v-if="createForm.delivery_start_mode === 'date'"
                    class="card-order-delivery-block co-create-activation-date"
                  >
                    <el-date-picker
                      v-model="createForm.delivery_start_date"
                      type="date"
                      value-format="YYYY-MM-DD"
                      format="YYYY-MM-DD"
                      placeholder="选择开始配送日"
                      class="card-order-date-picker"
                      :clearable="false"
                    />
                    <el-alert
                      v-if="activationStartDateHint"
                      :type="activationStartDateHint.type"
                      :closable="false"
                      show-icon
                      class="co-activation-date-hint"
                      :title="activationStartDateHint.text"
                    />
                  </div>
                </template>
              </div>
            </div>
          </div>

          <!-- 右侧：配送位置 + 提交 -->
          <div class="co-create-split-side">
            <div class="co-create-panel co-create-panel--side">
              <div class="co-create-panel-head-row">
                <div class="co-create-panel-title co-create-panel-title--plain co-create-panel-title--with-icon">
                  <MapPin class="co-create-panel-title-icon" :size="18" :stroke-width="2.25" aria-hidden="true" />
                  配送位置
                </div>
                <!-- <span class="co-create-optional-pill">OPTIONAL</span> -->
              </div>
              <!-- <p class="modal-hint card-order-map-hint">
                与小程序一致：地图搜索或点选后填入详细地址（坐标后台保存）。
              </p> -->
              <MemberDeliveryMapPicker
                class="co-create-map-picker-root"
                v-model:lng-str="createForm.delivery_lng"
                v-model:lat-str="createForm.delivery_lat"
                v-model:map-location-text="createForm.map_location_text"
                @warn="onDeliveryMapWarn"
              />
              <div class="form-group">
                <label>地图详细地址（只读）</label>
                <el-input
                  v-model="createForm.map_location_text"
                  type="textarea"
                  :rows="2"
                  maxlength="500"
                  readonly
                  placeholder="选取地图坐标后自动填充"
                />
              </div>
              <div class="form-group">
                <label>门牌号 / 单元楼层</label>
                <el-input v-model="createForm.door_detail" maxlength="500" placeholder="如：3 号楼 1202" clearable />
              </div>
            </div>
            <div class="co-create-side-footer">
              <!-- <p class="modal-hint co-create-submit-hint">
                缴费状态为「已缴」时，创建后将自动同步剩余次数（周卡 +{{ planDefaultTotal('周卡') }} / 月卡
                +{{ planDefaultTotal('月卡') }} / 次卡 +{{ planDefaultTotal('次卡') }}）与套餐；仅在选择「指定起送日」时同时写入起送日并激活。选「未缴」则不入账。
              </p> -->
              <button type="submit" class="btn-submit-order co-create-submit-wide" :disabled="createSubmitting">
                {{ createSubmitting ? '提交中…' : '创建开卡工单' }}
              </button>
            </div>
          </div>
        </form>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="showEditModal"
        class="modal-overlay"
        v-esc-close="() => (showEditModal = false)"
        @click.self="showEditModal = false"
      >
        <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>更新工单 · #{{ editForm.id }}</h3>
            <p>UPDATE CARD ORDER</p>
          </div>
          <button type="button" class="close-btn" @click="showEditModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form modal-form--card-order" @submit.prevent="() => submitEdit(false)">
          <div class="form-group">
            <label>会员</label>
            <el-input
              :model-value="`${editForm.member_name || '—'}${editForm.member_wechat_name ? ' / 微信 ' + editForm.member_wechat_name : ''}（${editForm.member_phone}）`"
              type="text"
              disabled
              class="input-disabled"
            />
          </div>
          <div class="form-group">
            <label>卡包模版</label>
            <el-input
              v-if="editForm.applied_to_member"
              :model-value="editTemplateDisplayLabel"
              type="text"
              disabled
              class="input-disabled input-delivery-area co-edit-card-kind-select"
            />
            <el-select
              v-else
              v-model="editForm.membership_template_id"
              class="input-delivery-area co-edit-card-kind-select"
              :loading="membershipTemplatesLoading"
              :disabled="!membershipTemplates.length"
              placeholder="请选择已开启的卡包"
            >
              <el-option
                v-for="t in membershipTemplates"
                :key="t.id"
                :value="Number(t.id)"
                :label="templateOptionLabel(t)"
              />
            </el-select>
            <p v-if="editForm.applied_to_member" class="modal-hint">
              已入账工单不可改卡包模版；餐段为
              <strong>{{ mealPeriodsLabel(editForm.meal_periods) }}</strong>
              <template v-if="editForm.template_product_label">
                （{{ editForm.template_product_label }}）
              </template>
              。若档案有误请在「会员管理」中修正。
            </p>
            <p
              v-else-if="!membershipTemplatesLoading && !membershipTemplates.length"
              class="modal-hint modal-hint--warn"
            >
              暂无已开启的卡包模版，请先在「会员卡管理」中创建并开启。
            </p>
            <p v-else-if="selectedEditTemplate" class="modal-hint">
              所选餐段：<strong>{{ mealPeriodsLabel(selectedEditTemplate.meal_periods) }}</strong>
              · 同步入账 +{{ selectedEditTemplate.meals_grant }} 次
            </p>
          </div>
          <div class="form-group open-mode-group">
            <label>开始配送日</label>
            <el-radio-group v-model="editForm.delivery_start_mode" class="co-open-mode-radio-group">
              <div class="open-mode-options">
                <el-radio value="date" border class="co-open-mode-radio-item">
                  <div class="co-open-mode-radio-body">
                    <span class="radio-tile-title">指定起送日</span>
                    <span class="radio-tile-sub">写入或修改具体业务日</span>
                  </div>
                </el-radio>
                <el-radio value="defer" border class="co-open-mode-radio-item">
                  <div class="co-open-mode-radio-body">
                    <span class="radio-tile-title">暂不开卡</span>
                    <span class="radio-tile-sub">工单上不保存起送日；已入账的会员起送日以档案为准</span>
                  </div>
                </el-radio>
              </div>
            </el-radio-group>
            <div
              v-if="editForm.delivery_start_mode === 'date'"
              class="card-order-delivery-block"
            >
              <el-date-picker
                v-model="editForm.delivery_start_date"
                type="date"
                value-format="YYYY-MM-DD"
                format="YYYY-MM-DD"
                placeholder="选择开始配送日"
                class="card-order-date-picker"
                :clearable="false"
              />
              <p v-if="editForm.applied_to_member" class="modal-hint card-order-delivery-hint">
                已同步的工单修改起送日会同步更新会员档案。
              </p>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>缴费渠道</label>
              <el-select v-model="editForm.pay_channel" class="co-edit-row-select">
                <el-option label="微信" value="微信" />
                <el-option label="支付宝" value="支付宝" />
                <el-option label="线下" value="线下" />
              </el-select>
            </div>
            <div class="form-group">
              <label>缴费状态</label>
              <el-select v-model="editForm.pay_status" class="co-edit-row-select" :disabled="editForm.applied_to_member">
                <el-option label="未缴" value="未缴" />
                <el-option label="已缴" value="已缴" />
              </el-select>
            </div>
          </div>
          <p v-if="editForm.applied_to_member" class="modal-hint">已入账的工单不可改回「未缴」。</p>
          <div class="form-group">
            <label>实收金额</label>
            <el-input v-model="editForm.amount_yuan" placeholder="留空可清空金额" clearable />
          </div>
          <div class="form-group">
            <label>备注</label>
            <el-input v-model="editForm.remark" type="textarea" :rows="3" maxlength="500" />
          </div>
          <p v-if="!editForm.applied_to_member" class="modal-hint">
            「保存」仅更新工单字段；「确认入账」在核对起送日与缴费信息后将次数写入会员并激活。
          </p>
          <p
            v-if="
              !editForm.applied_to_member &&
              editForm.created_by === 'miniprogram' &&
              editForm.pay_status === '已缴'
            "
            class="modal-hint card-order-pending-approval-hint"
          >
            小程序自助购卡：须手动「确认入账」后才会写入会员次数并参与配送派单。
          </p>
          <div class="card-order-edit-actions">
            <button type="submit" class="btn-submit-order" :disabled="editSubmitting">
              {{ editSubmitting ? '保存中…' : '保存' }}
            </button>
            <button
              v-if="editForm.pay_status === '已缴' && !editForm.applied_to_member"
              type="button"
              class="btn-submit-order btn-submit-order--sync"
              :disabled="editSubmitting"
              @click.prevent="submitEdit(true)"
            >
              {{ editSubmitting ? '处理中…' : '确认入账' }}
            </button>
          </div>
        </form>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.search-box--flex {
  flex: 1;
  min-width: 220px;
  max-width: 420px;
}
.card-orders-filters {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.card-orders-filter-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted, #64748b);
}
.card-orders-filter-label--check {
  user-select: none;
  cursor: pointer;
}

.card-orders-pending-hint {
  font-size: 12px;
  font-weight: 600;
  color: #b45309;
}

.card-order-pending-approval-hint {
  color: #b45309;
  font-weight: 600;
}

/* 查看历史记录：Element Plus Checkbox，默认 v-model=true */
.card-orders-history-el-checkbox.el-checkbox {
  margin-right: 0;
  height: auto;
}

.card-orders-history-el-checkbox.el-checkbox :deep(.el-checkbox__label) {
  padding-left: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted, #64748b);
}
.card-orders-select {
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid var(--border, #e2e8f0);
  background: var(--surface, #fff);
}
.card-orders-intro {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0 0 16px;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-muted, #64748b);
  background: var(--surface-2, #f8fafc);
  border-radius: 10px;
  border: 1px solid var(--border, #e2e8f0);
}
.card-orders-intro-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.modal-form--card-order {
  padding-bottom: 2.85rem;
  scroll-padding-bottom: 1.5rem;
}

/* 隐藏金额等 number 控件自带的上下箭头（Chrome / Safari / Firefox） */
.modal-form input[type='number']::-webkit-outer-spin-button,
.modal-form input[type='number']::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.modal-form input[type='number'] {
  appearance: textfield;
  -moz-appearance: textfield;
}

.modal-card.modal-card--card-order-create {
  width: 100%;
  max-width: min(1200px, calc(100vw - 2rem));
}

/** 新建工单：左主表单（约 2/3）+ 右配送与提交（约 1/3） */
.modal-form.modal-form--co-create-split {
  padding: 1.5rem;
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(280px, 400px);
  gap: 0.5rem;
  align-items: stretch;
}

/* 新建工单：输入框 / 下拉 / 文本区内边距（控制纵向高度观感） */
.modal-form.modal-form--co-create-split .form-group input:not([type='radio']),
.modal-form.modal-form--co-create-split .form-group select,
.modal-form.modal-form--co-create-split .form-group textarea {
  padding: 0.8rem;
}

.co-create-split-main,
.co-create-split-side {
  min-width: 0;
}

.co-create-split-main {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.co-create-split-side {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.co-create-panel {
  background: var(--surface, #fff);
  border-radius: 14px;
  border: 1px solid var(--border, #e8eef3);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
  padding: 1.15rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.co-create-panel--side {
  flex: 1 1 auto;
}

/* 「激活设置」底部含日期控件，加长底部留白，避免贴底与焦点边框观感溢出 */
.co-create-panel--activation {
  padding-bottom: 1.85rem;
}

.co-create-panel-title {
  font-size: 14px;
  font-weight: 800;
  color: #1e293b;
}

.co-create-panel-title--plain {
  margin: 0;
}

/* 分组标题前缀图标：与顶部品牌色呼应，避免与右侧 OPTIONAL 挤叠 */
.co-create-panel-title--with-icon {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
}

.co-create-panel-head-row .co-create-panel-title--with-icon {
  flex: 1;
  min-width: 0;
}

.co-create-panel-title-icon {
  flex-shrink: 0;
  color: #0e5a44;
}

.co-create-panel-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.co-create-optional-pill {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #64748b;
  background: #f1f5f9;
  padding: 4px 9px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.co-create-member-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.co-create-renew-phone-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(240px, 1.55fr);
  gap: 1rem;
  align-items: start;
}

.co-create-renew-match-col {
  min-width: 0;
}

.co-create-renew-match-label {
  font-size: 12px;
  font-weight: 900;
  color: #94a3b8;
  text-transform: uppercase;
  padding-left: 0.5rem;
}

.co-create-renew-match-placeholder {
  opacity: 0.85;
}

.renew-preview-box--aside {
  margin-bottom: 0;
  min-height: 3.25rem;
}

.co-create-fees-row3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.co-create-fees-row2 {
  display: grid;
  grid-template-columns: minmax(140px, 220px) minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

/* 备注默认一行高度与左侧实收金额输入框一致（同 padding + 单行字高），仍可通过右下角纵向拉伸 */
.co-create-fees-row2 .form-group input[type='number'],
.co-create-fees-row2 .co-create-remark-field textarea {
  min-height: calc(1.35em + 1.6rem);
  box-sizing: border-box;
}

.co-create-activation-row {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
}

.open-mode-options--activation {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 14px;
  align-items: stretch;
}

.open-mode-options--activation-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.co-renew-activation-alert {
  width: 100%;
}

.co-activation-date-hint {
  width: 100%;
}

.co-activation-date-hint :deep(.el-alert__title) {
  font-size: 12px;
  line-height: 1.55;
  font-weight: 500;
}

.co-create-activation-date {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  /* Element Plus：date-editor 默认用 --el-date-editor-width 固定像素，改为拉满整行 */
  --el-date-editor-width: 100%;
}

.co-create-activation-date :deep(.el-date-editor.el-input__wrapper) {
  width: 100% !important;
  max-width: 100% !important;
}

.co-create-pay-status-select--paid {
  background: rgba(16, 185, 129, 0.14) !important;
  color: #047857 !important;
  font-weight: 800;
}

.co-create-side-footer {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: auto;
}

.co-create-submit-hint {
  margin: 0;
  text-align: center;
  font-size: 11px;
  line-height: 1.55;
}

.co-create-submit-wide {
  width: 100%;
  margin-top: 0 !important;
}

.radio-tile--compact {
  padding: 10px 12px;
  gap: 4px;
}

.radio-tile--compact .radio-tile-sub {
  font-size: 11px;
  line-height: 1.4;
}

.co-create-map-picker-root :deep(.mdmp-map) {
  min-height: 220px;
  height: min(260px, 38vh);
}

@media (max-width: 960px) {
  .modal-form.modal-form--co-create-split {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 820px) {
  .co-create-member-grid,
  .co-create-renew-phone-row,
  .co-create-fees-row3 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .co-create-fees-row2 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .open-mode-options--activation-3 {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .open-mode-options--activation {
    grid-template-columns: 1fr;
  }
}

.open-mode-group .open-mode-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 14px;
  align-items: stretch;
}
@media (max-width: 560px) {
  .open-mode-group .open-mode-options {
    grid-template-columns: 1fr;
  }
}
.radio-tile {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--border, #e2e8f0);
  background: var(--surface, #fff);
  cursor: pointer;
}
.radio-tile:has(input:checked) {
  border-color: var(--primary, #3b82f6);
  background: rgba(59, 130, 246, 0.06);
}
.radio-tile-head {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  width: 100%;
  min-width: 0;
}
.radio-tile-head input[type='radio'] {
  margin: 0.15rem 0 0;
  flex-shrink: 0;
}
.radio-tile-title {
  font-weight: 600;
  font-size: 14px;
  line-height: 1.35;
  min-width: 0;
  word-break: break-word;
}
.radio-tile-sub {
  font-size: 12px;
  color: var(--text-muted, #64748b);
  line-height: 1.45;
  min-width: 0;
  word-break: break-word;
  overflow-wrap: break-word;
}
.card-order-delivery-address-block {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px dashed var(--border, #e2e8f0);
  background: var(--surface-2, #fafafa);
}
.card-order-map-hint {
  margin: 0 0 10px;
}
.card-order-delivery-block {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
  min-width: 0;
  width: 100%;
  margin-top: 0.15rem;
  overflow: visible;
}
.card-order-delivery-hint {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  min-width: 0;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: break-word;
  line-height: 1.6;
}
.renew-preview-box {
  /* margin-bottom: 4px; */
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--surface-2, #f8fafc);
  border: 1px dashed var(--border, #e2e8f0);
}
.modal-hint--accent {
  color: var(--primary, #2563eb);
}
.modal-hint--warn {
  color: #b45309;
}
.card-orders-page .co-row-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.35rem;
}
/* Element Plus 日期选择：与弹窗内原生输入框的圆角、背景一致 */
.form-group :deep(.card-order-date-picker),
.co-create-activation-date :deep(.card-order-date-picker) {
  display: block;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
.form-group :deep(.card-order-delivery-block .el-date-editor),
.co-create-activation-date :deep(.card-order-delivery-block .el-date-editor),
.co-create-activation-date :deep(.el-date-editor) {
  width: 100% !important;
  max-width: 100%;
  box-sizing: border-box;
}
.form-group :deep(.card-order-date-picker .el-input__wrapper),
.co-create-activation-date :deep(.card-order-date-picker .el-input__wrapper) {
  width: 100%;
  min-height: 3.1rem;
  background: #f8fafc;
  border: 2px solid transparent;
  border-radius: 1.25rem;
  box-shadow: none;
}
.form-group :deep(.card-order-date-picker .el-input__wrapper.is-focus),
.co-create-activation-date :deep(.card-order-date-picker .el-input__wrapper.is-focus) {
  border-color: #0e5a44;
  background: #fff;
}

/* 新建工单：起送日期选择与上方控件统一为 0.8rem 内边距 */
.modal-form.modal-form--co-create-split :deep(.card-order-date-picker .el-input__wrapper) {
  min-height: auto;
  padding: 0.8rem;
}
/* 开卡工单列表：表头/行高沿用 admin-table--members；备注/创建列允许换行展示全文 */
.co-member-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  min-width: 0;
  max-width: 100%;
}

.co-member-name {
  display: block;
  font-weight: 900;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  max-width: 100%;
}

.co-plan-tag {
  flex-shrink: 0;
  margin-left: 0;
}

.co-card-kind-empty {
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
}

.co-meal-period-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  white-space: nowrap;
}

.co-meal-period--lunch {
  color: #0369a1;
  background: #e0f2fe;
  border: 1px solid #bae6fd;
}

.co-meal-period--dinner {
  color: #9a3412;
  background: #ffedd5;
  border: 1px solid #fed7aa;
}

.co-meal-period--both {
  color: #6d28d9;
  background: #ede9fe;
  border: 1px solid #ddd6fe;
}

.card-orders-page :deep(.co-nowrap .cell) {
  white-space: nowrap;
}

/* 起送日 / 渠道 / 入账 / 电话：避免表头与内容被截成「…」 */
.card-orders-page :deep(.td-co-idx .cell) {
  overflow: visible;
  white-space: nowrap;
  text-overflow: clip;
}

.card-orders-page :deep(.td-co-name .cell) {
  overflow: visible;
  text-overflow: clip;
}

.card-orders-page :deep(.td-co-start-date .cell),
.card-orders-page :deep(.td-co-channel .cell),
.card-orders-page :deep(.td-co-sync .cell),
.card-orders-page :deep(.td-co-phone-col .cell),
.card-orders-page :deep(.td-co-card-kind .cell),
.card-orders-page :deep(.td-co-meal-period .cell),
.card-orders-page :deep(.td-co-pay-status .cell),
.card-orders-page :deep(.td-co-amt-col .cell) {
  overflow: visible;
  text-overflow: clip;
}

.co-amt-num {
  font-weight: 900;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

/* 列表序号 / 实收：pill 底色（与订单管理列表同风格） */
.co-cell-pill {
  display: inline-block;
  max-width: 100%;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  box-sizing: border-box;
  vertical-align: middle;
}

.co-cell-pill--idx {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  min-width: 2.25em;
  max-width: none;
  text-align: center;
  color: #475569;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

.co-cell-pill--amount {
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: #be123c;
  background: #fff1f2;
  border: 1px solid #fecdd3;
}

.co-remark-text {
  display: block;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.35;
  color: #475569;
  max-width: 100%;
}

.co-created-line {
  display: block;
  white-space: normal;
  word-break: break-all;
  overflow-wrap: anywhere;
  line-height: 1.35;
  color: #64748b;
  max-width: 100%;
}

.card-orders-page .co-row-actions .btn-sm {
  margin-left: 0;
}

.card-orders-filter-el {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.card-orders-filter-el-text {
  font-size: 13px;
  color: var(--text-muted, #64748b);
}
.card-orders-pay-select {
  width: 120px;
}
.card-orders-created-range {
  flex-shrink: 0;
}
.card-orders-created-picker {
  width: 240px;
}
.card-orders-created-picker :deep(.el-range-input) {
  font-size: 13px;
}
.co-create-fees-select,
.co-edit-row-select,
.co-edit-card-kind-select {
  width: 100%;
}
.co-open-mode-radio-group,
.co-activation-radio-group {
  width: 100%;
}
.co-open-mode-radio-group :deep(.el-radio),
.co-activation-radio-group :deep(.el-radio) {
  width: 100%;
  margin-right: 0;
  height: auto;
  align-items: flex-start;
  padding: 10px 12px;
  white-space: normal;
}
.co-open-mode-radio-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  line-height: 1.35;
  padding-left: 4px;
}
.open-mode-options--activation {
  display: flex;
  flex-direction: column;
  width: 100%;
  gap: 8px;
}

.card-order-edit-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 0.5rem;
}

.card-order-edit-actions .btn-submit-order {
  margin-top: 0;
  width: 100%;
}

.card-order-edit-actions .btn-submit-order--sync {
  background: #1d4ed8;
  box-shadow: 0 15px 30px rgba(29, 78, 216, 0.2);
}
</style>
