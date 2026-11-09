<script setup>
defineOptions({ name: 'MembersView' })
import { ref, watch, computed, onMounted, onActivated, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { Search, Download, Upload, Ticket, ChevronDown } from 'lucide-vue-next'
import * as XLSX from 'xlsx'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
  membershipTemplatePlanLabel,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { confirmForceReinstateDelivery } from '../composables/confirmForceReinstateDelivery.js'
import { parseApiDateTimeBeijing } from '../utils/beijingDateTime.js'
import MemberEditModal from './components/MemberEditModal.vue'
import MemberBalanceEditModal from './components/MemberBalanceEditModal.vue'
import MemberImportModal from './components/MemberImportModal.vue'
import MemberAddressesModal from './components/MemberAddressesModal.vue'
import MemberMealCompensationModal from './components/MemberMealCompensationModal.vue'
import MembersMoreDropdownMenu from './components/MembersMoreDropdownMenu.vue'
import OkfoodAdminDialogShell from '../components/OkfoodAdminDialogShell.vue'
import MemberOperationContext from '../components/MemberOperationContext.vue'

const MOBILE_MEDIA = '(max-width: 768px)'

/**
 * 「更多」下拉 Popper：fixed + 视口内约束，菜单自身滚动，避免撑开 .main-body__router-host 导致整页上移
 */
const membersMoreDropdownPopperOptions = {
  strategy: 'fixed',
  modifiers: [
    { name: 'offset', options: { offset: [0, 6] } },
    {
      name: 'flip',
      options: {
        fallbackPlacements: ['top-end', 'bottom-end', 'top-start', 'bottom-start'],
        padding: 10,
      },
    },
    {
      name: 'preventOverflow',
      options: {
        padding: 10,
        altAxis: true,
        tether: false,
        rootBoundary: 'viewport',
      },
    },
  ],
}

/** 窄屏（手机）使用卡片列表，桌面保留表格 */
const isNarrowScreen = ref(
  typeof window !== 'undefined' && window.matchMedia(MOBILE_MEDIA).matches,
)
/** 手机筛选默认收起，只留搜索框 */
const mobileFiltersOpen = ref(false)

/** @type {MediaQueryList | null} */
let mobileMediaQuery = null

function syncNarrowScreen() {
  if (!mobileMediaQuery) return
  isNarrowScreen.value = mobileMediaQuery.matches
  if (!isNarrowScreen.value) {
    void nextTick(() => updateMembersTableHeight())
  }
}

/** 本页表格数据（本地 ref；同步写入 memberList 供登出清空等兼容） */
const membersRows = ref([])

/** 每页条数（与接口 page_size，当前 15）；表格纵向高度随视口铺满，ResizeObserver 写入 membersTableScrollHeight（el-table height + 表体滚动） */
const MEMBERS_TABLE_PAGE_SIZE = 15

const membersPage = ref(1)
const membersPageSize = ref(MEMBERS_TABLE_PAGE_SIZE)

/** 包裹 el-table，用于测量可用高度（px） */
const membersTableHostRef = ref(null)
/** 表格总高度（含表头）；表体在内部滚动 */
const membersTableScrollHeight = ref(400)
/** @type {ResizeObserver | null} */
let membersTableResizeObserver = null

function updateMembersTableHeight() {
  const el = membersTableHostRef.value
  if (!el) return
  const h = Math.floor(el.getBoundingClientRect().height)
  if (h >= 160) {
    membersTableScrollHeight.value = h
  }
}
const membersTotal = ref(0)
const membersLoading = ref(false)
const searchQuery = ref('')
/** 状态：'' 全部 | active 生效中 | expired 已过期 | refunded 已退款（默认全部） */
const membersValidityFilter = ref('')
/** 套餐：'' 全部 | 租户卡包模版 id | 无卡包时兜底「周卡」「月卡」 */
const membersPlanFilter = ref('')
/** 片区：'' | 'unassigned' | 区域 id 字符串 */
const membersRegionFilter = ref('')
/** 会员卡状态：'' 全部 | delivering 正常配送中 | inactive 未开卡 | awaiting_setup 待完善履约 | paused 暂停配送 | leave 请假中 | renew_pending 待续费 */
const membersStatusSegment = ref('')
const regionFilterOptions = ref([])
/** 本店会员卡套餐筛选项（按种类+餐段去重） */
const membershipPlanFilterOptions = ref([])

const route = useRoute()
const router = useRouter()

/** 当前是否为待续费筛选（客服续卡提醒场景） */
const isRenewPendingFilter = computed(() => membersStatusSegment.value === 'renew_pending')
/** 当前是否为待完善履约筛选（抖音/小程序新购卡人工复核） */
const isAwaitingSetupFilter = computed(() => membersStatusSegment.value === 'awaiting_setup')
/** 当前是否为暂停配送筛选 */
const isPausedFilter = computed(() => membersStatusSegment.value === 'paused')
/** 当前是否为正常配送中筛选 */
const isDeliveringFilter = computed(() => membersStatusSegment.value === 'delivering')

/** 从路由 query 恢复筛选（会员统计页跳转带参） */
function applyMembersRouteQueryFilters() {
  const q = route.query
  const validity = String(q.validity ?? '').trim()
  if (['active', 'expired', 'refunded'].includes(validity)) {
    membersValidityFilter.value = validity
  }
  const segment = String(q.segment ?? '').trim()
  if (['delivering', 'inactive', 'awaiting_setup', 'paused', 'leave', 'renew_pending'].includes(segment)) {
    membersStatusSegment.value = segment
  }
  const region = String(q.region ?? '').trim()
  if (region === 'unassigned') {
    membersRegionFilter.value = 'unassigned'
  }
}

const membersTotalPages = computed(() =>
  Math.max(1, Math.ceil(membersTotal.value / membersPageSize.value)),
)

/** 表格序号（跨页连续） */
function tableRowIndex(index) {
  return (membersPage.value - 1) * membersPageSize.value + index + 1
}

/** el-table 行主键：组合 id+phone，避免 bigint/重复 id 导致 Diff 落在已销毁的 DOM 上 */
function memberRowKey(row) {
  return `${String(row?.id ?? '')}__${String(row?.phone ?? '')}`
}

function validityQuery() {
  const v = String(membersValidityFilter.value ?? '').trim()
  if (v === 'expired') return 'expired'
  if (v === 'refunded') return 'refunded'
  if (v === 'active') return 'active'
  return ''
}

async function loadRegionFilterOptions() {
  try {
    const data = await apiJson('/api/admin/delivery-regions', {}, { auth: true })
    const list = Array.isArray(data) ? data : []
    regionFilterOptions.value = list
      .filter((r) => r && (r.is_active === true || r.is_active === 1))
      .map((r) => ({ id: r.id, name: typeof r.name === 'string' ? r.name : '' }))
      .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
  } catch {
    regionFilterOptions.value = []
  }
}

/** 套餐下拉：本店会员卡模版（含已下架，便于筛历史套餐）；无模版时仍可用周卡/月卡 */
async function loadMembershipPlanFilterOptions() {
  try {
    const data = await apiJson('/api/admin/catalog/membership-templates', {}, { auth: true })
    const list = Array.isArray(data) ? data : []
    const seen = new Set()
    const opts = []
    for (const t of list) {
      const id = Number(t?.id)
      if (!Number.isFinite(id) || id <= 0) continue
      const label = membershipTemplatePlanLabel(t)
      if (seen.has(label)) continue
      seen.add(label)
      opts.push({ id, label })
    }
    membershipPlanFilterOptions.value = opts
    const cur = String(membersPlanFilter.value ?? '').trim()
    if (!cur) return
    const known = opts.some((o) => String(o.id) === cur)
    if (!known && cur !== '周卡' && cur !== '月卡') {
      membersPlanFilter.value = ''
    }
  } catch {
    membershipPlanFilterOptions.value = []
  }
}

function onCardStatusFilterChange() {
  membersPage.value = 1
  void fetchMembers()
}

function onRegionFilterChange() {
  membersPage.value = 1
  void fetchMembers()
}

function onPlanFilterChange() {
  membersPage.value = 1
  void fetchMembers()
}

function onValidityFilterChange() {
  membersPage.value = 1
  void fetchMembers()
}

const memberDeletingId = ref(null)
const membersExporting = ref(false)
const showImportModal = ref(false)

/** MessageBox 文案转义（dangerouslyUseHTMLString 用） */
function escapeMessageBoxHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

async function deleteMemberRow(u) {
  if (!u?.id) return
  const label = `${u.name || '—'} · ${u.phone || ''}`
  const deleteDetail =
    '若有余额流水、配送记录、单次点餐或开卡工单，将仅做逻辑删除并保留数据；若四项均无记录则物理删除档案与地址。'
  try {
    await ElMessageBox.confirm(
      `<p class="okfood-message-box__subject">${escapeMessageBoxHtml(label)}</p><p class="okfood-message-box__detail">${deleteDetail}</p>`,
      '确定删除该会员？',
      {
        customClass: 'okfood-message-box okfood-message-box--delete',
        confirmButtonText: '确定删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'okfood-message-box__confirm--danger',
        cancelButtonClass: 'okfood-message-box__cancel',
        distinguishCancelAndClose: true,
        autofocus: 'cancel',
        dangerouslyUseHTMLString: true,
      },
    )
  } catch {
    return
  }
  memberDeletingId.value = u.id
  try {
    const data = await apiJson(`/api/admin/users/${Number(u.id)}`, { method: 'DELETE' }, { auth: true })
    const detail =
      data && typeof data === 'object' && typeof data.msg === 'string'
        ? data.msg
        : '已删除'
    showToast(detail, 'success')
    await fetchMembers()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  } finally {
    memberDeletingId.value = null
  }
}

/** 操作列「更多」下拉：请假 / 地址 / 修改与其它低频操作集中到一处 */
function onMembersActionDropdown(command, row) {
  if (command === 'leave') {
    void openLeaveMember(row)
    return
  }
  if (command === 'reinstate_delivery') {
    void reinstateMemberToDeliverySheet(row)
    return
  }
  if (command === 'addresses') {
    void openMemberAddresses(row)
    return
  }
  if (command === 'edit') {
    void openEditMember(row)
    return
  }
  if (command === 'edit_balance') {
    openBalanceEdit(row)
    return
  }
  if (command === 'records') {
    void openMemberDeliveryRecords(row)
    return
  }
  if (command === 'operation_logs') {
    void openMemberOperationLogs(row)
    return
  }
  if (command === 'meal_compensation') {
    openMemberMealCompensation(row)
    return
  }
  if (command === 'refund') {
    void openMemberRefund(row)
    return
  }
  if (command === 'grant_coupon') {
    goGrantCouponForMember(row)
    return
  }
  if (command === 'delete') {
    void deleteMemberRow(row)
  }
}

/** 与列表请求一致；exportMode 为 true 时固定仅「剩余次数>0」（不导出 balance=0） */
function buildMembersListParams(page, pageSize, { exportMode = false } = {}) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })
  if (exportMode) {
    if (membersStatusSegment.value === 'renew_pending') {
      params.set('renew_pending_only', '1')
    } else {
      params.set('validity', 'active')
    }
  } else {
    const vq = validityQuery()
    if (vq) params.set('validity', vq)
  }
  const pq = String(membersPlanFilter.value ?? '').trim()
  if (pq) {
    if (pq === '周卡' || pq === '月卡') {
      params.set('plan_type', pq)
    } else {
      params.set('membership_template_id', pq)
    }
  }
  const q = searchQuery.value.trim()
  if (q) params.set('q', q)
  if (membersStatusSegment.value === 'delivering') params.set('delivering_only', '1')
  else if (membersStatusSegment.value === 'inactive') params.set('inactive_only', '1')
  else if (membersStatusSegment.value === 'awaiting_setup') params.set('awaiting_setup_only', '1')
  else if (membersStatusSegment.value === 'paused') params.set('delivery_deferred_only', '1')
  else if (membersStatusSegment.value === 'leave') params.set('on_leave_only', '1')
  else if (membersStatusSegment.value === 'renew_pending') params.set('renew_pending_only', '1')
  const mrf = String(membersRegionFilter.value ?? '').trim()
  if (mrf === 'unassigned') params.set('unassigned_region', '1')
  else if (mrf) {
    const rid = mrf
    if (rid && rid !== 'unassigned') params.set('delivery_region_id', rid)
  }
  return params
}

async function fetchMembers() {
  if (!adminAccessToken.value) return
  membersLoading.value = true
  try {
    const params = buildMembersListParams(membersPage.value, membersPageSize.value)
    const qs = params.toString()
    const data = await apiJson(`/api/admin/users?${qs}`, {}, { auth: true })
    const rawItems = Array.isArray(data?.items) ? data.items : []
    const rows = rawItems.map(mapAdminUserToRow)
    membersRows.value = rows
    memberList.value = rows
    membersTotal.value = Number(data?.total) || 0
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载会员列表失败', 'error')
  } finally {
    membersLoading.value = false
  }
  await nextTick()
  updateMembersTableHeight()
}

async function exportMembersExcel() {
  if (!adminAccessToken.value || membersExporting.value) return
  membersExporting.value = true
  const pageSize = 100
  const collected = []
  try {
    let page = 1
    let total = 0
    for (; ;) {
      const params = buildMembersListParams(page, pageSize, { exportMode: true })
      const data = await apiJson(`/api/admin/users?${params.toString()}`, {}, { auth: true })
      const rawItems = Array.isArray(data?.items) ? data.items : []
      total = Number(data?.total) || 0
      let idx = collected.length
      for (const raw of rawItems) {
        const u = mapAdminUserToRow(raw, idx)
        idx += 1
        if ((Number(u.balance) || 0) > 0) collected.push(u)
      }
      if (page * pageSize >= total || rawItems.length < pageSize) break
      page += 1
    }
    if (!collected.length) {
      showToast('没有可导出数据（不含剩余次数为 0 的会员），或当前筛选下无符合条件记录', 'error')
      return
    }
    const out = collected.map((u) => ({
      会员ID: u.id ?? '',
      姓名: u.name || '',
      微信昵称: u.wechat_name ? String(u.wechat_name) : '',
      手机: u.phone || '',
      套餐类型: u.plan || '',
      配送片区: u.area && u.area !== '—' ? String(u.area) : '',
      配送地址详情: memberAddressDetailWithoutArea(u) || '',
      '午餐/晚餐/总餐次': u.balanceLabel || String(u.balance),
      每日份数: u.daily_meal_units ?? '',
      请假信息: u.leave_kind
        ? [u.leave_badge, u.leave_detail].filter(Boolean).join(' ').trim()
        : '',
      状态: u.status || '',
      用户操作时间: formatMemberOperationTime(u.updated_at),
      起送业务日: u.delivery_start_date || '',
      备注: u.remarks != null && String(u.remarks).length ? String(u.remarks) : '',
    }))
    const ws = XLSX.utils.json_to_sheet(out)
    ws['!cols'] = [
      { wch: 10 },
      { wch: 12 },
      { wch: 14 },
      { wch: 14 },
      { wch: 8 },
      { wch: 14 },
      { wch: 36 },
      { wch: 14 },
      { wch: 8 },
      { wch: 22 },
      { wch: 10 },
      { wch: 16 },
      { wch: 12 },
      { wch: 28 },
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '会员档案')
    const stamp = shanghaiTodayYmd()
    const exportTag = isRenewPendingFilter.value
      ? '待续费'
      : isDeliveringFilter.value
        ? '正常配送中'
        : '剩余次数大于0'
    XLSX.writeFile(wb, `会员档案_${exportTag}_${stamp}.xlsx`)
    showToast(`已导出 ${out.length} 条`, 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '导出失败', 'error')
  } finally {
    membersExporting.value = false
  }
}

let membersSearchTimer = 0
watch(searchQuery, () => {
  if (!adminAccessToken.value) return
  window.clearTimeout(membersSearchTimer)
  membersSearchTimer = window.setTimeout(() => {
    membersPage.value = 1
    void fetchMembers()
  }, 320)
})

const goMembersPrev = () => {
  if (membersPage.value <= 1) return
  membersPage.value -= 1
  void fetchMembers()
}

const goMembersNext = () => {
  if (membersPage.value >= membersTotalPages.value) return
  membersPage.value += 1
  void fetchMembers()
}

const memberStatusClass = (status) => {
  if (status === '已退款') return 'member-pill member-pill--rose'
  if (status === '请假中') return 'member-pill member-pill--rose'
  if (status === '待续费') return 'member-pill member-pill--amber'
  if (status === '待完善') return 'member-pill member-pill--amber'
  if (status === '已过期') return 'member-pill member-pill--slate'
  if (status === '未开卡') return 'member-pill member-pill--slate'
  if (status === '暂不开卡') return 'member-pill member-pill--slate'
  if (status === '已暂停') return 'member-pill member-pill--slate'
  if (status === '明日暂停') return 'member-pill member-pill--amber'
  return 'member-pill member-pill--emerald'
}

function planTagClass(plan, planBase, mealScopeLabel) {
  // 全餐（午+晚）单独配色，与仅午餐的周卡/月卡标签区分
  const scope = (mealScopeLabel || String(plan || '').split(' · ')[1] || '').trim()
  if (scope === '全餐') return 't-plan--full-meal'
  const base = (planBase || String(plan || '').split(' · ')[0] || '').trim()
  if (base === '周卡') return 't-plan--week'
  if (base === '月卡') return 't-plan--month'
  return 't-plan--count'
}

/** 会员表副行：仅展示昵称，去掉「微信」字样（含历史脏数据前缀） */
function memberWechatLineText(wechatRaw) {
  const s = String(wechatRaw ?? '').trim()
  if (!s) return ''
  return s.replace(/^微信\s*/u, '').trim()
}

/** --- 手工请假（管理端，不受小程序当日截止时间限制） --- */
const showLeaveModal = ref(false)
const leaveSaving = ref(false)
const leaveTarget = ref(null)
const leaveMode = ref('tomorrow')
const leaveMealPeriod = ref('lunch')
/** 多天请假（区间）：YYYY-MM-DD，与小程序「多天请假」同一接口口径 */
const leaveRangeStart = ref('')
const leaveRangeEnd = ref('')

const leavePeriodTabs = computed(() => {
  const u = leaveTarget.value
  if (!u) return [{ value: 'lunch', label: '午餐' }]
  const periods = Array.isArray(u.entitled_meal_periods) ? u.entitled_meal_periods : []
  const hasLunch = periods.includes('lunch')
  const hasDinner = periods.includes('dinner')
  const tabs = []
  if (hasLunch && hasDinner) tabs.push({ value: 'all', label: '全天' })
  if (hasLunch) tabs.push({ value: 'lunch', label: '午餐' })
  if (hasDinner) tabs.push({ value: 'dinner', label: '晚餐' })
  if (!tabs.length) tabs.push({ value: 'lunch', label: '午餐' })
  return tabs
})

function shanghaiTodayYmd() {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const y = parts.find((p) => p.type === 'year')?.value
    const m = parts.find((p) => p.type === 'month')?.value
    const d = parts.find((p) => p.type === 'day')?.value
    if (y && m && d) return `${y}-${m}-${d}`
  } catch {
    /* ignore */
  }
  const n = new Date()
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`
}

/** el-date-picker：禁止选择早于 minYmd（YYYY-MM-DD）的日历日 */
function calendarDateToYmd(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
function leaveDateDisabledBeforeMin(d, minYmd) {
  return calendarDateToYmd(d) < minYmd
}

function addDaysYmdShanghai(ymd, deltaDays) {
  if (!ymd) return ''
  const t = new Date(`${ymd}T12:00:00+08:00`)
  const t2 = new Date(t.getTime() + deltaDays * 24 * 60 * 60 * 1000)
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(t2)
  const y = parts.find((p) => p.type === 'year')?.value
  const m = parts.find((p) => p.type === 'month')?.value
  const d = parts.find((p) => p.type === 'day')?.value
  return y && m && d ? `${y}-${m}-${d}` : ''
}

function defaultAdminLeaveRange() {
  const t = shanghaiTodayYmd()
  const start = addDaysYmdShanghai(t, 1)
  return { start, end: start }
}

function openLeaveMember(u) {
  leaveTarget.value = u
  leaveMode.value = 'tomorrow'
  const r = defaultAdminLeaveRange()
  leaveRangeStart.value = r.start
  leaveRangeEnd.value = r.end
  const tabs = []
  const periods = Array.isArray(u?.entitled_meal_periods) ? u.entitled_meal_periods : []
  const hasLunch = periods.includes('lunch')
  const hasDinner = periods.includes('dinner')
  if (hasLunch && hasDinner) tabs.push({ value: 'all', label: '全天' })
  if (hasLunch) tabs.push({ value: 'lunch', label: '午餐' })
  if (hasDinner) tabs.push({ value: 'dinner', label: '晚餐' })
  leaveMealPeriod.value = tabs[0]?.value || 'lunch'
  showLeaveModal.value = true
}

async function submitLeaveMember() {
  const u = leaveTarget.value
  if (!u || !u.phone) return
  if (leaveMode.value === 'range') {
    const s = (leaveRangeStart.value || '').trim()
    const e = (leaveRangeEnd.value || '').trim()
    if (!s || !e) {
      showToast('请填写开始日期与结束日期', 'error')
      return
    }
    if (e < s) {
      showToast('结束日期不能早于开始日期', 'error')
      return
    }
  }
  leaveSaving.value = true
  try {
    const payload = { phone: u.phone, type: leaveMode.value, meal_period: leaveMealPeriod.value }
    if (leaveMode.value === 'range') {
      payload.start = leaveRangeStart.value.trim()
      payload.end = leaveRangeEnd.value.trim()
    }
    await apiJson(
      '/api/admin/member/leave',
      { method: 'POST', body: JSON.stringify(payload) },
      { auth: true },
    )
    showLeaveModal.value = false
    showToast('请假状态已更新', 'success')
    await fetchMembers()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    leaveSaving.value = false
  }
}

/** 推单冻结后极端补送：强制将会员写入当日大表快照（默认取消请假不加回） */
async function reinstateMemberToDeliverySheet(u) {
  if (!u?.phone) return
  const periods = Array.isArray(u?.entitled_meal_periods) ? u.entitled_meal_periods : []
  let mealPeriod = 'lunch'
  if (periods.includes('dinner') && !periods.includes('lunch')) mealPeriod = 'dinner'
  const periodLabel = mealPeriod === 'dinner' ? '晚餐' : '午餐'
  const ok = await confirmForceReinstateDelivery(u, periodLabel)
  if (!ok) return
  try {
    await apiJson(
      '/api/admin/delivery-sheet/reinstate-member',
      {
        method: 'POST',
        body: JSON.stringify({ phone: u.phone, meal_period: mealPeriod }),
      },
      { auth: true },
    )
    showToast('已强制加入当天配送大表', 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '强制加入失败', 'error')
  }
}

/** --- 修改会员（弹窗子组件 MemberEditModal） --- */
const showEditModal = ref(false)
const editTargetMember = ref(null)

watch(showEditModal, (v) => {
  if (!v) editTargetMember.value = null
})

async function onMemberEditSaved() {
  await fetchMembers()
}

/** 不含所属片区：map_location_text + door_detail；否则从列表 address 去掉片区前缀 */
function memberAddressDetailWithoutArea(u) {
  const mapT = typeof u.map_location_text === 'string' ? u.map_location_text.trim() : ''
  const door = typeof u.door_detail === 'string' ? u.door_detail.trim() : ''
  const detail = [mapT, door].filter(Boolean).join(' ').trim()
  if (detail) return detail
  const rawAddr = String(u.address || '').trim()
  if (!rawAddr || rawAddr.startsWith('（未设置')) return ''
  const areaTag = String(u.area || '').trim()
  if (areaTag && areaTag !== '—' && rawAddr.startsWith(areaTag)) {
    return rawAddr.slice(areaTag.length).trim()
  }
  return rawAddr
}

/** Tooltip 内：片区 + 门牌/地图选点详情，便于运营快速核对完整地址 */
function memberAddressTooltipContent(u) {
  const detail = memberAddressDetailWithoutArea(u).trim()
  const area = String(u.area || '').trim()
  const raw = String(u.address || '').trim()
  if (!detail && !area && !raw) return ''
  if (area && area !== '—') {
    if (detail) return `${area} · ${detail}`.trim()
    return area
  }
  if (detail) return detail
  return raw
}

function openEditMember(u) {
  editTargetMember.value = u
  showEditModal.value = true
}

/** 修改剩余次数与每配送日份数（与档案弹窗分开，避免改资料时覆盖次数） */
const showBalanceModal = ref(false)
const balanceTargetMember = ref(null)

watch(showBalanceModal, (v) => {
  if (!v) balanceTargetMember.value = null
})

function openBalanceEdit(u) {
  balanceTargetMember.value = u
  showBalanceModal.value = true
}

/** --- 会员地址管理（地图选点子组件 MemberAddressesModal） --- */
const showAddrModal = ref(false)
const addrTargetMember = ref(null)

watch(showAddrModal, (v) => {
  if (!v) addrTargetMember.value = null
})

function openMemberAddresses(u) {
  if (!u?.id) return
  addrTargetMember.value = u
  showAddrModal.value = true
}

/** --- 消费记录：已确认送达的配送业务日 --- */
const showDeliveryRecordModal = ref(false)
const deliveryRecordTarget = ref(null)
const deliveryRecordLoading = ref(false)
const deliveryRecordDates = ref([])
const deliveryRecordTotal = ref(0)
const deliveryRecordTotalMeals = ref(0)
const deliveryRecordTruncated = ref(false)

/** 消费记录：入账类（购买/补餐）用 +，扣次类用 - */
function isConsumptionAdditionKind(kind) {
  return kind === 'meal_compensation' || kind === 'card_recharge'
}

function formatSignedMealUnits(kind, units) {
  const n = Math.max(1, Number(units) || 1)
  return `${isConsumptionAdditionKind(kind) ? '+' : '-'}${n} 份`
}

function normalizeConsumptionMealPeriod(periodRaw) {
  return String(periodRaw || '').trim().toLowerCase() === 'dinner' ? 'dinner' : 'lunch'
}

function consumptionMealPeriodLabel(periodRaw) {
  return normalizeConsumptionMealPeriod(periodRaw) === 'dinner' ? '晚餐' : '午餐'
}

function normalizeConsumptionRecordKind(kindRaw) {
  if (kindRaw === 'single_meal') return 'single_meal'
  if (kindRaw === 'meal_compensation') return 'meal_compensation'
  if (kindRaw === 'card_recharge') return 'card_recharge'
  return 'subscription'
}

async function openMemberDeliveryRecords(u) {
  if (!u?.id) return
  deliveryRecordTarget.value = u
  deliveryRecordDates.value = []
  deliveryRecordTotal.value = 0
  deliveryRecordTotalMeals.value = 0
  deliveryRecordTruncated.value = false
  showDeliveryRecordModal.value = true
  deliveryRecordLoading.value = true
  try {
    const data = await apiJson(`/api/admin/users/${Number(u.id)}/delivered-dates`, {}, { auth: true })
    const items = Array.isArray(data?.items) ? data.items : []
    deliveryRecordDates.value = items
      .map((row) => {
        if (!row || row.delivery_date == null) return null
        const ymd = String(row.delivery_date).slice(0, 10)
        if (!ymd) return null
        const mealUnits = Math.max(1, Number(row.meal_units) || 1)
        const kind = normalizeConsumptionRecordKind(row.deduction_kind)
        const mealPeriod = normalizeConsumptionMealPeriod(row.meal_period)
        return { delivery_date: ymd, meal_units: mealUnits, deduction_kind: kind, meal_period: mealPeriod }
      })
      .filter(Boolean)
    deliveryRecordTotal.value = Number(data?.total) || deliveryRecordDates.value.length
    deliveryRecordTotalMeals.value = Number(data?.total_meal_units) || 0
    deliveryRecordTruncated.value = Boolean(data?.truncated)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    showDeliveryRecordModal.value = false
    deliveryRecordTarget.value = null
  } finally {
    deliveryRecordLoading.value = false
  }
}

watch(showDeliveryRecordModal, (v) => {
  if (!v) {
    deliveryRecordTarget.value = null
    deliveryRecordDates.value = []
    deliveryRecordTotal.value = 0
    deliveryRecordTotalMeals.value = 0
    deliveryRecordTruncated.value = false
  }
})

/** --- 操作记录：小程序 / 后台对该会员的自助与关键变更审计（按时间倒序分页） --- */
const showOperationLogModal = ref(false)
const operationLogTarget = ref(null)
const operationLogLoading = ref(false)
const operationLogItems = ref([])
const operationLogTotal = ref(0)
/** 与后端 list_member_operations 上限一致；弹窗内列表滚动，不再分页按钮 */
const OPERATION_LOG_FETCH_SIZE = 200
const operationLogTruncated = ref(false)

function formatOperationLogTime(iso) {
  const s = typeof iso === 'string' ? iso.trim() : ''
  if (!s) return '—'
  try {
    const d = parseApiDateTimeBeijing(s)
    if (Number.isNaN(d.getTime())) return s
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).format(d)
  } catch {
    return s
  }
}

function operationLogSourceLabel(src) {
  const k = String(src || '').trim().toLowerCase()
  if (k === 'admin') return '后台'
  if (k === 'miniprogram') return '小程序'
  return src ? String(src) : '—'
}

function operationLogOperatorLabel(op) {
  const s = String(op || '').trim()
  if (!s) return '—'
  if (s.startsWith('admin:')) return s.slice(6) || '后台'
  if (s.startsWith('member:')) return '会员本人'
  return s
}

async function fetchMemberOperationLogs() {
  if (!operationLogTarget.value?.id) return
  operationLogLoading.value = true
  try {
    const mid = Number(operationLogTarget.value.id)
    const data = await apiJson(
      `/api/admin/users/${mid}/operation-logs?page=1&page_size=${OPERATION_LOG_FETCH_SIZE}`,
      {},
      { auth: true },
    )
    operationLogItems.value = Array.isArray(data?.items) ? data.items : []
    operationLogTotal.value = Number(data?.total) || 0
    operationLogTruncated.value =
      operationLogTotal.value > operationLogItems.value.length
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    showOperationLogModal.value = false
    operationLogTarget.value = null
  } finally {
    operationLogLoading.value = false
  }
}

async function openMemberOperationLogs(u) {
  if (!u?.id) return
  operationLogTarget.value = u
  operationLogItems.value = []
  operationLogTotal.value = 0
  operationLogTruncated.value = false
  showOperationLogModal.value = true
  await fetchMemberOperationLogs()
}

watch(showOperationLogModal, (v) => {
  if (!v) {
    operationLogTarget.value = null
    operationLogItems.value = []
    operationLogTotal.value = 0
    operationLogTruncated.value = false
  }
})

/** --- 补餐赔付：餐品问题补回已消费次数 --- */
const showMealCompensationModal = ref(false)
const mealCompensationTarget = ref(null)

watch(showMealCompensationModal, (v) => {
  if (!v) mealCompensationTarget.value = null
})

function openMemberMealCompensation(u) {
  if (!u?.id) return
  mealCompensationTarget.value = u
  showMealCompensationModal.value = true
}

async function onMemberMealCompensationSaved() {
  await fetchMembers()
}

/** --- 退卡退款：按剩余次数 × 菜单单价计算应退（不按开卡实收） --- */
const showRefundModal = ref(false)
const refundTarget = ref(null)
const refundPreview = ref(null)
const refundPreviewLoading = ref(false)
const refundSubmitting = ref(false)
const refundRemark = ref('')

function fmtRefundYuan(v) {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 用户操作时间：后端 updated_at（ISO），展示为 YYYY-MM-DD HH:mm */
function formatMemberOperationTime(iso) {
  const s = String(iso || '').trim()
  if (!s) return '—'
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/)
  if (m) return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`
  return s.length >= 16 ? s.slice(0, 16).replace('T', ' ') : s
}

function canMemberRefund(row) {
  if (row?.membership_refunded_at) return false
  return Number(row?.balance) > 0
}

async function openMemberRefund(u) {
  if (!u?.id || !canMemberRefund(u)) {
    showToast('该会员剩余次数为 0，无法退卡', 'error')
    return
  }
  refundTarget.value = u
  refundPreview.value = null
  refundRemark.value = ''
  showRefundModal.value = true
  refundPreviewLoading.value = true
  try {
    const data = await apiJson(`/api/admin/users/${Number(u.id)}/membership-refund-preview`, {}, { auth: true })
    refundPreview.value = data && typeof data === 'object' ? data : null
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '无法计算退款', 'error')
    showRefundModal.value = false
    refundTarget.value = null
  } finally {
    refundPreviewLoading.value = false
  }
}

async function submitMemberRefund() {
  const u = refundTarget.value
  const p = refundPreview.value
  if (!u?.id || !p) return
  const amt = Number(p.refund_amount_yuan)
  if (!Number.isFinite(amt) || amt < 0) {
    showToast('退款金额无效，请刷新后重试', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `${u.name || '—'} · ${u.phone || ''}\n\n已消费 ${p.meals_consumed} 次，退剩余 ${p.meals_remaining} 次 × ¥ ${fmtRefundYuan(p.unit_price_yuan)}\n应退 ¥ ${fmtRefundYuan(amt)}`,
      '确认退卡退款',
      {
        type: 'warning',
        confirmButtonText: '确认退卡',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }
  refundSubmitting.value = true
  try {
    await apiJson(
      `/api/admin/users/${Number(u.id)}/membership-refund`,
      {
        method: 'POST',
        body: JSON.stringify({
          confirm_refund_yuan: String(p.refund_amount_yuan),
          remark: refundRemark.value.trim() || null,
        }),
      },
      { auth: true },
    )
    showRefundModal.value = false
    showToast('退卡退款已确认，请按应退金额退款给用户', 'success')
    await fetchMembers()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '退卡失败', 'error')
  } finally {
    refundSubmitting.value = false
  }
}

watch(showRefundModal, (v) => {
  if (!v) {
    refundTarget.value = null
    refundPreview.value = null
    refundRemark.value = ''
  }
})

function goGrantCouponForMember(row) {
  const phone = String(row?.phone || '').trim()
  if (!phone) {
    showToast('该会员无手机号，无法发券', 'error')
    return
  }
  router.push({
    path: '/marketing/member-coupons',
    query: { grant: '1', phone },
  })
}

function goBatchGrantCouponsForRenewPending() {
  router.push({
    path: '/marketing/member-coupons',
    query: { grant: '1', batch: 'renew_pending' },
  })
}

async function onMemberAddressesSaved() {
  await fetchMembers()
}

onMounted(async () => {
  applyMembersRouteQueryFilters()
  await Promise.all([loadRegionFilterOptions(), loadMembershipPlanFilterOptions()])
  await fetchMembers()
  if (typeof window !== 'undefined') {
    mobileMediaQuery = window.matchMedia(MOBILE_MEDIA)
    syncNarrowScreen()
    mobileMediaQuery.addEventListener('change', syncNarrowScreen)
  }
  await nextTick()
  updateMembersTableHeight()
  membersTableResizeObserver = new ResizeObserver(() => {
    updateMembersTableHeight()
  })
  if (membersTableHostRef.value) {
    membersTableResizeObserver.observe(membersTableHostRef.value)
  }
})

/** keep-alive 切回标签页时刷新列表，避免配送扣次后仍展示旧剩余次数 */
onActivated(async () => {
  await loadMembershipPlanFilterOptions()
  void fetchMembers()
})

onUnmounted(() => {
  membersTableResizeObserver?.disconnect()
  membersTableResizeObserver = null
  mobileMediaQuery?.removeEventListener('change', syncNarrowScreen)
})
</script>

<template>
  <section class="tab-content animate-up members-view-fill">
    <div class="table-container table-container--members-fill">
      <div class="table-header table-header--members">
        <!-- 顶栏：搜索左置 → 筛选（10px 间距）→ 右侧导入/导出；不展示汇总统计 -->
        <div class="members-toolbar-row">
          <div class="members-toolbar-search members-search-wrap">
            <el-input
              v-model="searchQuery"
              clearable
              placeholder="姓名/手机/地址…"
              class="members-search-el-input"
            >
              <template #prefix>
                <Search :size="14" class="members-search-el-icon" aria-hidden="true" />
              </template>
            </el-input>
            <button
              v-if="isNarrowScreen"
              type="button"
              class="members-filter-toggle"
              :class="{ 'is-open': mobileFiltersOpen }"
              :aria-expanded="mobileFiltersOpen"
              :aria-label="mobileFiltersOpen ? '收起筛选' : '展开筛选'"
              @click="mobileFiltersOpen = !mobileFiltersOpen"
            >
              <ChevronDown :size="18" stroke-width="2.25" aria-hidden="true" />
            </button>
          </div>
          <div v-show="!isNarrowScreen || mobileFiltersOpen" class="members-toolbar-filters-scroll">
            <div class="members-filter-toolbar">
              <div class="members-extra-filters" aria-label="状态、套餐、片区与会员卡状态筛选">
                <div class="members-filter-pair">
                  <label class="members-filter-label" for="members-validity-filter">状态</label>
                  <el-select
                    id="members-validity-filter"
                    v-model="membersValidityFilter"
                    class="members-region-select-el"
                    placeholder="全部"
                    @change="onValidityFilterChange"
                  >
                    <el-option label="全部" value="" />
                    <el-option label="生效中" value="active" />
                    <el-option label="已过期" value="expired" />
                    <el-option label="已退款" value="refunded" />
                  </el-select>
                </div>
                <div class="members-filter-pair">
                  <label class="members-filter-label" for="members-plan-filter">套餐</label>
                  <el-select
                    id="members-plan-filter"
                    v-model="membersPlanFilter"
                    class="members-region-select-el"
                    placeholder="全部"
                    clearable
                    @change="onPlanFilterChange"
                  >
                    <el-option label="全部" value="" />
                    <template v-if="membershipPlanFilterOptions.length">
                      <el-option
                        v-for="opt in membershipPlanFilterOptions"
                        :key="opt.id"
                        :label="opt.label"
                        :value="String(opt.id)"
                      />
                    </template>
                    <template v-else>
                      <el-option label="周卡" value="周卡" />
                      <el-option label="月卡" value="月卡" />
                    </template>
                  </el-select>
                </div>
                <div class="members-filter-pair">
                  <label class="members-filter-label" for="members-region-filter">片区</label>
                  <el-select
                    id="members-region-filter"
                    v-model="membersRegionFilter"
                    class="members-region-select-el members-region-select-el--wide"
                    placeholder="全部"
                    clearable
                    filterable
                    @change="onRegionFilterChange"
                  >
                    <el-option label="全部" value="" />
                    <el-option label="未分配" value="unassigned" />
                    <el-option
                      v-for="r in regionFilterOptions"
                      :key="r.id"
                      :label="r.name || '—'"
                      :value="String(r.id)"
                    />
                  </el-select>
                </div>
                <div class="members-filter-pair">
                  <label class="members-filter-label" for="members-card-status-filter">会员卡状态</label>
                  <el-select
                    id="members-card-status-filter"
                    v-model="membersStatusSegment"
                    class="members-region-select-el"
                    placeholder="全部"
                    @change="onCardStatusFilterChange"
                  >
                    <el-option label="全部" value="" />
                    <el-option label="正常配送中" value="delivering" />
                    <el-option label="未开卡" value="inactive" />
                    <el-option label="待完善" value="awaiting_setup" />
                    <el-option label="已暂停" value="paused" />
                    <el-option label="请假中" value="leave" />
                    <el-option label="待续费" value="renew_pending" />
                  </el-select>
                </div>
              </div>
            </div>
          </div>
          <div v-if="adminAccessToken && !isNarrowScreen" class="members-toolbar-trailing">
            <div class="members-export-actions">
              <el-button
                type="default"
                size="small"
                class="members-export-btn"
                title="下载 Excel 模板，填写后批量导入会员档案"
                @click="showImportModal = true"
              >
                <Upload :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
                导入会员
              </el-button>
              <el-button
                type="primary"
                size="small"
                class="members-export-btn"
                :loading="membersExporting"
                :disabled="membersLoading"
                title="按当前搜索与筛选拉取全部分页；自动排除剩余次数为 0 的会员"
                @click="exportMembersExcel"
              >
                <Download :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
                导出 Excel
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <div v-if="isDeliveringFilter" class="members-awaiting-banner" role="status">
        <p class="members-awaiting-banner__text">
          当前展示<strong>正常配送中</strong>会员（生效履约中，非待完善/暂停/请假/待续费/未开卡/退款/已过期）。
          状态列应与筛选一致，均显示「正常配送中」。
        </p>
      </div>
      <div v-if="isRenewPendingFilter" class="members-renew-banner" role="status">
        <p class="members-renew-banner__text">
          当前展示<strong>待续费</strong>会员（生效中、午餐或晚餐剩余次数 ≤ 2，不含暂停/退款/请假）。可导出名单后电话/微信提醒续卡，或批量发放续卡优惠券。
        </p>
        <el-button type="warning" size="small" @click="goBatchGrantCouponsForRenewPending">
          <Ticket :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
          批量发券
        </el-button>
      </div>
     <div v-if="isAwaitingSetupFilter" class="members-awaiting-banner" role="status">
        <p class="members-awaiting-banner__text">
          当前展示<strong>待完善履约</strong>会员（已入账开卡工单，缺起送日或配送地址，且从未确认送达）。
          本列表仅用于人工复核与联系用户完善信息，<strong>不会自动修改</strong>会员档案或配送安排。
          主动暂停配送的会员请用「已暂停」筛选，不在此列；状态列应与筛选一致，均显示「待完善」。
        </p>
      </div>
      <div v-if="isPausedFilter" class="members-awaiting-banner" role="status">
        <p class="members-awaiting-banner__text">
          当前展示<strong>已暂停配送</strong>会员（主动暂停且仍有剩余次数，非待完善/请假/退款/已过期）。
          状态列与筛选口径一致，应均显示「已暂停」；请假中请用「请假中」筛选，待完善请用「待完善」筛选。
        </p>
      </div>
      <div
        ref="membersTableHostRef"
        class="members-table-host"
        :class="{ 'members-table-host--mobile-cards': isNarrowScreen }"
      >
        <!-- 桌面：表格 -->
        <AdminTable
          v-if="!isNarrowScreen"
          variant="members"
          class="members-el-table-body-scroll"
          size="small"
          :data="membersRows"
          :loading="membersLoading"
          :row-key="memberRowKey"
          :height="membersTableScrollHeight"
          empty-text="暂无会员数据"
        >
        <el-table-column label="序号" width="72" align="center" class-name="td-mono td-members-idx">
          <template #default="{ $index }">
            <span class="members-cell-pill members-cell-pill--idx">{{ tableRowIndex($index) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="会员信息" min-width="100">
          <template #default="{ row: u }">
            <div class="t-name">{{ u.name || '—' }}</div>
            <div v-if="memberWechatLineText(u.wechat_name)" class="t-sub t-wechat">
              {{ memberWechatLineText(u.wechat_name) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="电话"
          min-width="132"
          class-name="td-phone"
          label-class-name="td-phone"
        >
          <template #default="{ row: u }">
            <span class="member-phone-num">{{ u.phone || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="套餐类型" align="center" min-width="108">
          <template #default="{ row: u }">
            <span class="t-plan" :class="planTagClass(u.plan, u.planBase, u.meal_scope_label)">{{ u.plan }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="起送日期"
          align="center"
          width="112"
          min-width="112"
          class-name="td-delivery-start"
          label-class-name="td-delivery-start"
        >
          <template #default="{ row: u }">
            <span class="members-delivery-start-date">{{ u.delivery_start_date || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="配送地址" min-width="300" class-name="td-col-delivery-address">
          <template #default="{ row: u }">
            <el-tooltip
              :content="memberAddressTooltipContent(u)"
              placement="top-start"
              :show-after="400"
              :disabled="!memberAddressTooltipContent(u)"
              popper-class="members-address-tooltip-popper"
            >
              <span class="members-address-cell-ellipsis">
                {{ memberAddressDetailWithoutArea(u) || '—' }}
              </span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="请假时间" width="92" min-width="92" class-name="td-col-leave">
          <template #default="{ row: u }">
            <div v-if="!u.leave_kind" class="leave-cell leave-cell--empty">—</div>
            <div v-else class="leave-cell" :title="u.leave_detail || ''">
              <div class="leave-detail">{{ u.leave_detail }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="午 / 晚 / 总" align="left" min-width="96">
          <template #default="{ row: u }">
            <el-tooltip
              :content="u.remainTooltip || ''"
              placement="top"
              :show-after="400"
              :disabled="!u.remainTooltip"
            >
              <div class="balance-cell">
                 <span class="balance-text balance-triple">
                    <span class="balance-triple__n" :class="{ warning: u.remainLunchLow }">{{
                      u.remainLunchText
                      }}</span>
                    <span class="balance-triple__sep">/</span>
                    <span class="balance-triple__n" :class="{
                      warning: u.remainDinnerLow,
                      placeholder: u.showDinnerRemain !== true,
                    }">{{ u.remainDinnerText }}</span>
                    <span class="balance-triple__sep">/</span>
                    <span class="balance-triple__n">{{ u.remainQuotaText }}</span>
                  </span>

                <p
                  v-if="u.tomorrow_leave && !u.is_on_leave_today"
                  class="balance-leave-hint balance-leave-hint--tomorrow"
                >
                  明日配送请假
                </p>
              </div>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="108" width="108" class-name="td-col-status">
          <template #default="{ row: u }">
            <span :class="memberStatusClass(u.status)">{{ u.status }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="用户操作时间"
          min-width="128"
          class-name="td-col-operation-time"
          label-class-name="td-col-operation-time"
        >
          <template #default="{ row: u }">
            <span class="members-operation-time" :title="u.updated_at || ''">{{
              formatMemberOperationTime(u.updated_at)
            }}</span>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="100" class-name="td-remarks">
          <template #default="{ row: u }">
            {{ u.remarks || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" align="right" min-width="100" fixed="right">
          <template #default="{ row: u }">
            <div class="members-row-actions members-row-actions--denoised">
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                :popper-options="membersMoreDropdownPopperOptions"
                popper-class="okfood-members-more-dropdown"
                @command="(cmd) => onMembersActionDropdown(cmd, u)"
              >
                <el-button type="primary" link size="small" class="btn-members-link">
                  更多
                  <ChevronDown :size="14" aria-hidden="true" class="members-more-chevron" />
                </el-button>
                <template #dropdown>
                  <MembersMoreDropdownMenu
                    :refund-disabled="!canMemberRefund(u)"
                    :delete-disabled="memberDeletingId === u.id"
                    :delete-label="memberDeletingId === u.id ? '删除中…' : '删除'"
                  />
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        </AdminTable>

        <!-- 手机：卡片列表 -->
        <div v-else v-loading="membersLoading" class="members-mobile-list">
          <p v-if="!membersRows.length && !membersLoading" class="members-mobile-empty">暂无会员数据</p>
          <article
            v-for="(u, idx) in membersRows"
            :key="memberRowKey(u)"
            class="member-profile-card"
          >
            <header class="member-profile-card__head">
              <div class="member-profile-card__head-left">
                <span class="members-cell-pill members-cell-pill--idx">{{ tableRowIndex(idx) }}</span>
                <div class="member-profile-card__identity">
                  <span class="member-profile-card__name">{{ u.name || '—' }}</span>
                  <span v-if="memberWechatLineText(u.wechat_name)" class="member-profile-card__wechat">
                    {{ memberWechatLineText(u.wechat_name) }}
                  </span>
                </div>
              </div>
              <span :class="memberStatusClass(u.status)">{{ u.status }}</span>
            </header>

            <section class="member-profile-card__meta">
              <span class="t-plan" :class="planTagClass(u.plan, u.planBase, u.meal_scope_label)">{{
                u.plan
              }}</span>
             <span class="balance-text balance-triple member-profile-card__balance" :title="u.remainTooltip || ''">
                <span class="balance-triple__n" :class="{ warning: u.remainLunchLow }">{{
                  u.remainLunchText
                }}</span>
                <span class="balance-triple__sep">/</span>
               <span
class="balance-triple__n" :class="{
                  warning: u.remainDinnerLow,
                  placeholder: u.showDinnerRemain !== true,
                }">{{ u.remainDinnerText }}</span>
                <span class="balance-triple__sep">/</span>
                <span class="balance-triple__n">{{ u.remainQuotaText }}</span>
              </span>
              <span v-if="u.delivery_start_date" class="member-profile-card__start-date">
                起送 {{ u.delivery_start_date }}
              </span>
            </section>

            <section class="member-profile-card__ship">
              <div class="member-profile-card__contact">
                <a
                  v-if="(u.phone || '').trim()"
                  :href="`tel:${String(u.phone).replace(/\s/g, '')}`"
                  class="member-phone-num member-profile-card__phone td-mono"
                  @click.stop
                  >{{ u.phone }}</a
                >
                <span v-else class="member-profile-card__phone td-mono">—</span>
              </div>
              <p class="member-profile-card__addr">
                {{ memberAddressDetailWithoutArea(u) || '—' }}
              </p>
              <p
                v-if="String(u.area || '').trim() && u.area !== '—'"
                class="member-profile-card__area"
              >
                {{ u.area }}
              </p>
            </section>

            <p v-if="u.leave_kind" class="member-profile-card__leave">
              <span class="member-profile-card__leave-label">请假</span>
              <span class="member-profile-card__leave-text">{{ u.leave_detail }}</span>
            </p>
            <p
              v-if="u.tomorrow_leave && !u.is_on_leave_today"
              class="balance-leave-hint balance-leave-hint--tomorrow member-profile-card__tomorrow-leave"
            >
              明日配送请假
            </p>

            <p v-if="(u.remarks || '').trim()" class="member-profile-card__remark">
              <span class="member-profile-card__remark-label">备注</span>
              <span class="member-profile-card__remark-text">{{ u.remarks }}</span>
            </p>

            <footer class="member-profile-card__footer">
              <time class="member-profile-card__time" :title="u.updated_at || ''">
                {{ formatMemberOperationTime(u.updated_at) }}
              </time>
              <el-dropdown
                trigger="click"
                placement="bottom-end"
                :popper-options="membersMoreDropdownPopperOptions"
                popper-class="okfood-members-more-dropdown"
                @command="(cmd) => onMembersActionDropdown(cmd, u)"
              >
                <el-button type="primary" size="small" plain class="member-profile-card__more-btn">
                  更多操作
                  <ChevronDown :size="14" aria-hidden="true" class="members-more-chevron" />
                </el-button>
                <template #dropdown>
                  <MembersMoreDropdownMenu
                    :refund-disabled="!canMemberRefund(u)"
                    :delete-disabled="memberDeletingId === u.id"
                    :delete-label="memberDeletingId === u.id ? '删除中…' : '删除'"
                  />
                </template>
              </el-dropdown>
            </footer>
          </article>
        </div>
      </div>
      <div v-if="adminAccessToken" class="members-pagination members-pagination--float">
        <button type="button" class="btn-sm" :disabled="membersPage <= 1" @click="goMembersPrev">上一页</button>
        <span class="members-page-meta"
          >第 {{ membersPage }} / {{ membersTotalPages }} 页 · 共 {{ membersTotal }} 条</span
        >
        <button
          type="button"
          class="btn-sm"
          :disabled="membersPage >= membersTotalPages"
          @click="goMembersNext"
        >
          下一页
        </button>
      </div>
    </div>

    <OkfoodAdminDialogShell
      v-model:open="showLeaveModal"
      title="手工请假"
      subtitle="后台代操作，不校验小程序当日截止时间"
      size="md"
      :close-disabled="leaveSaving"
    >
      <template v-if="leaveTarget" #operation-context>
        <MemberOperationContext
          :name="leaveTarget.name"
          :phone="leaveTarget.phone"
          :plan="leaveTarget.plan"
        />
      </template>
      <div v-if="leavePeriodTabs.length > 1" class="form-group">
        <label>请假餐段</label>
        <el-radio-group v-model="leaveMealPeriod" class="leave-period-radio">
          <el-radio v-for="tab in leavePeriodTabs" :key="tab.value" :value="tab.value">
            {{ tab.label }}
          </el-radio>
        </el-radio-group>
      </div>
      <div class="form-group">
        <label>操作类型</label>
        <el-select v-model="leaveMode" class="leave-mode-select" placeholder="请选择">
          <el-option value="tomorrow" label="明日配送请假（与小程序「明天有事」一致）" />
          <el-option value="range" label="多天配送请假（与小程序「多天请假」一致，需选起止日期）" />
          <el-option value="clear_tomorrow" label="仅取消「明日请假」" />
          <el-option value="cancel" label="清空全部请假" />
        </el-select>
        <template v-if="leaveMode === 'range'">
          <div class="form-group form-group--leave-range">
            <label>开始日期</label>
            <el-date-picker
              v-model="leaveRangeStart"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="开始日期"
              class="leave-range-picker"
              :disabled-date="(d) => leaveDateDisabledBeforeMin(d, shanghaiTodayYmd())"
            />
          </div>
          <div class="form-group form-group--leave-range">
            <label>结束日期</label>
            <el-date-picker
              v-model="leaveRangeEnd"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="结束日期"
              class="leave-range-picker"
              :disabled-date="(d) => leaveDateDisabledBeforeMin(d, leaveRangeStart || shanghaiTodayYmd())"
            />
          </div>
        </template>
      </div>
      <div class="okfood-dlg-hint-block">
        <span class="okfood-dlg-hint-block__label">业务说明</span>
        <p class="okfood-dlg-hint-block__text">
          日期均为业务日；多天请假需选起止日期。后台代操作不校验当日请假截止时间。
        </p>
      </div>
      <template #footer>
        <el-button round :disabled="leaveSaving" @click="showLeaveModal = false">取消</el-button>
        <el-button round type="primary" :loading="leaveSaving" :disabled="leaveSaving" @click="submitLeaveMember">
          {{ leaveSaving ? '提交中…' : '确认' }}
        </el-button>
      </template>
    </OkfoodAdminDialogShell>

    <MemberEditModal v-model:open="showEditModal" :member="editTargetMember" :region-options="regionFilterOptions"
      @saved="onMemberEditSaved" />
    <MemberBalanceEditModal
      v-model:open="showBalanceModal"
      :member="balanceTargetMember"
      @saved="onMemberEditSaved"
    />
    <MemberImportModal v-model:open="showImportModal" @imported="loadMembersPage" />

    <MemberAddressesModal
      v-model:open="showAddrModal"
      :member="addrTargetMember"
      @saved="onMemberAddressesSaved"
    />

    <MemberMealCompensationModal
      v-model:open="showMealCompensationModal"
      :member="mealCompensationTarget"
      @saved="onMemberMealCompensationSaved"
    />

    <OkfoodAdminDialogShell
      v-model:open="showDeliveryRecordModal"
      title="消费记录"
      :subtitle="
        deliveryRecordLoading
          ? ''
          : `截至当前已消费 ${deliveryRecordTotalMeals} 份餐`
      "
      size="wide"
      dlg-class="okfood-admin-dlg--delivery-records"
    >
      <template v-if="deliveryRecordTarget" #operation-context>
        <MemberOperationContext
          :name="deliveryRecordTarget.name"
          :phone="deliveryRecordTarget.phone"
        />
      </template>
      <div class="okfood-dlg-hint-block" style="margin-top: 0">
        <span class="okfood-dlg-hint-block__label">记录口径说明</span>
        <p class="okfood-dlg-hint-block__text">
          含送达扣次、单次购买、补餐与开卡入账；+ / − 与餐段标注，按新到旧排列。
        </p>
      </div>
      <div v-if="deliveryRecordLoading" class="delivery-records-loading">加载中…</div>
      <template v-else>
        <p class="delivery-records-summary">
          共 <strong>{{ deliveryRecordTotal }}</strong> 条记录
          <span v-if="deliveryRecordTruncated" class="delivery-records-truncated"
            >（仅显示最近部分，可联系技术导出全量）</span
          >
        </p>
        <ul
          v-if="deliveryRecordDates.length"
          class="delivery-records-list delivery-records-list--scroll-5"
        >
          <li
            v-for="(row, idx) in deliveryRecordDates"
            :key="`${row.delivery_date}-${row.deduction_kind}-${row.meal_period}-${idx}`"
          >
            <span class="delivery-records-idx">{{ idx + 1 }}</span>
            <span class="delivery-records-line">
              {{ row.delivery_date }}
              <span
                class="delivery-records-kind-badge"
                :class="
                  row.meal_period === 'dinner'
                    ? 'delivery-records-kind-badge--dinner'
                    : 'delivery-records-kind-badge--lunch'
                "
                >{{ consumptionMealPeriodLabel(row.meal_period) }}</span
              >
              <span v-if="row.deduction_kind === 'single_meal'" class="delivery-records-kind-badge">单次购买</span>
              <span
                v-else-if="row.deduction_kind === 'meal_compensation'"
                class="delivery-records-kind-badge delivery-records-kind-badge--compensation"
                >补餐</span
              >
              <span
                v-else-if="row.deduction_kind === 'card_recharge'"
                class="delivery-records-kind-badge delivery-records-kind-badge--recharge"
                >开卡入账</span
              >
            </span>
            <span
              class="delivery-records-units"
              :class="{
                'delivery-records-units--addition': isConsumptionAdditionKind(row.deduction_kind),
                'delivery-records-units--deduction': !isConsumptionAdditionKind(row.deduction_kind),
              }"
            >
              {{ formatSignedMealUnits(row.deduction_kind, row.meal_units) }}
            </span>
          </li>
        </ul>
        <p v-else class="delivery-records-empty">
          暂无消费记录。套餐确认送达扣次或单次购买（会员卡）扣次后将显示在此。
        </p>
      </template>
      <template #footer>
        <el-button round type="primary" @click="showDeliveryRecordModal = false">关闭</el-button>
      </template>
    </OkfoodAdminDialogShell>

    <OkfoodAdminDialogShell
      v-model:open="showOperationLogModal"
      title="操作记录"
      subtitle="审计日志 · 新到旧"
      size="wide"
      fit-content
    >
      <template v-if="operationLogTarget" #operation-context>
        <MemberOperationContext
          :name="operationLogTarget.name"
          :phone="operationLogTarget.phone"
        />
      </template>
      <div class="okfood-dlg-hint-block" style="margin-top: 0">
        <span class="okfood-dlg-hint-block__label">审计说明</span>
        <p class="okfood-dlg-hint-block__text">
          记录该会员通过小程序或后台产生的关键操作（暂停配送、修改份数、地址与请假、档案修改等），含时间、摘要与操作人。
        </p>
      </div>
      <div v-if="operationLogLoading" class="delivery-records-loading">加载中…</div>
      <template v-else>
        <p class="delivery-records-summary operation-logs-summary-line">
          共 <strong>{{ operationLogTotal }}</strong> 条
          <span v-if="operationLogItems.length" class="delivery-records-summary-hint">
            · 列表最多展示约 5 行，超出滚动
          </span>
          <span v-if="operationLogTruncated" class="delivery-records-truncated"
            >（仅显示最近 {{ operationLogItems.length }} 条，可联系技术导出全量）</span
          >
        </p>
        <div
          v-if="operationLogItems.length"
          class="operation-logs-table-wrap operation-logs-table-wrap--scroll-5"
        >
          <table class="operation-logs-table">
            <thead>
              <tr>
                <th scope="col">时间</th>
                <th scope="col">操作</th>
                <th scope="col">摘要</th>
                <th scope="col">来源</th>
                <th scope="col">操作人</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in operationLogItems" :key="row.id">
                <td class="operation-logs-td-time">{{ formatOperationLogTime(row.created_at) }}</td>
                <td class="operation-logs-td-op">
                  {{ row.operation_label || row.operation_type || '—' }}
                </td>
                <td class="operation-logs-td-summary">{{ row.summary || '—' }}</td>
                <td class="operation-logs-td-src">
                  <span class="operation-logs-src">{{ operationLogSourceLabel(row.source) }}</span>
                </td>
                <td class="operation-logs-td-operator">
                  {{ row.operator_label || operationLogOperatorLabel(row.operator) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="delivery-records-empty">暂无操作记录。</p>
      </template>
      <template #footer>
        <el-button round type="primary" @click="showOperationLogModal = false">关闭</el-button>
      </template>
    </OkfoodAdminDialogShell>

    <OkfoodAdminDialogShell
      v-model:open="showRefundModal"
      title="退卡退款"
      subtitle="按剩余次数 × 菜单单价计算应退"
      size="wide"
      dlg-class="okfood-admin-dlg--refund-fit"
      :close-disabled="refundSubmitting"
      :close-on-backdrop="!refundSubmitting"
    >
      <template v-if="refundTarget" #operation-context>
        <MemberOperationContext
          :name="refundTarget.name"
          :phone="refundTarget.phone"
          :plan="refundTarget.plan"
        />
      </template>
      <div v-if="refundPreviewLoading" class="delivery-records-loading">计算中…</div>
      <div v-else-if="refundPreview" class="okfood-refund-dlg-layout">
        <div class="okfood-refund-summary-v2">
          <div class="okfood-refund-summary-v2__chips">
            <span class="okfood-refund-summary-v2__chip"
              >已消费 <strong>{{ refundPreview.meals_consumed }}</strong> 次</span
            >
            <span class="okfood-refund-summary-v2__chip"
              >可退 <strong>{{ refundPreview.meals_remaining }}</strong> 次</span
            >
            <span class="okfood-refund-summary-v2__chip">
              累计 <strong>{{ refundPreview.meal_quota_total }}</strong> 次 · 单价 ¥
              {{ fmtRefundYuan(refundPreview.unit_price_yuan) }}
            </span>
          </div>
          <div class="okfood-refund-summary-v2__amount">
            <span class="okfood-refund-summary-v2__amount-label">应退金额</span>
            <span class="okfood-refund-summary-v2__amount-value"
              >¥ {{ fmtRefundYuan(refundPreview.refund_amount_yuan) }}</span
            >
          </div>
        </div>
        <div class="okfood-dlg-hint-block okfood-refund-hint-static">
          <span class="okfood-dlg-hint-block__label">退款与财务说明</span>
          <p class="okfood-dlg-hint-block__text">
            确认后将清零剩余次数、暂停配送并写入财务扣减；请在线下或微信侧按应退金额退款给用户。不按开卡实收计算，避免渠道重复退款。
          </p>
        </div>
        <div
          v-if="Array.isArray(refundPreview.consumption_items) && refundPreview.consumption_items.length"
          class="okfood-refund-body-scroll"
          aria-label="已消费明细列表"
        >
          <ul
            class="members-refund-consumption-list members-refund-consumption-list--refund-detail"
          >
            <li v-for="(row, idx) in refundPreview.consumption_items" :key="`${row.delivery_date}-${idx}`">
              <span class="members-refund-consumption-date">{{ row.delivery_date }}</span>
              <span class="members-refund-consumption-dish">{{ row.dish_name || '—' }}</span>
              <span class="members-refund-consumption-amt">
                {{ row.meal_units }} 份 × ¥ {{ fmtRefundYuan(row.unit_price_yuan) }}
                = ¥ {{ fmtRefundYuan(row.line_total_yuan) }}
              </span>
            </li>
          </ul>
        </div>
        <div class="form-group okfood-refund-remark">
          <label for="members-refund-remark">备注（选填）</label>
          <el-input
            id="members-refund-remark"
            v-model="refundRemark"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="如：微信转账已退、现场现金退等"
            :disabled="refundSubmitting"
          />
        </div>
      </div>
      <template v-if="refundPreview && !refundPreviewLoading" #footer>
        <el-button round :disabled="refundSubmitting" @click="showRefundModal = false">取消</el-button>
        <el-button round type="danger" :loading="refundSubmitting" @click="submitMemberRefund">确认退卡</el-button>
      </template>
    </OkfoodAdminDialogShell>

  </section>
</template>

<style scoped>
/* 顶栏：搜索 / 筛选 / 按钮统一高度 */
.members-toolbar-row {
  --members-toolbar-control-h: 32px;
}

/* 宽度按 11 位手机号 + 图标/清除钮即可，给筛选与导入导出留一排空间 */
.members-search-wrap {
  flex: 0 1 auto;
  width: clamp(9.25rem, 11vw, 11rem);
  min-width: 9.25rem;
  max-width: 11rem;
}

.members-search-el-input {
  width: 100%;
}

/* 单层白色圆角搜索框（图标在框内左侧），不再套灰色 search-box 外容器 */
.members-search-el-input :deep(.el-input__wrapper) {
  width: 100%;
  min-height: var(--members-toolbar-control-h);
  height: var(--members-toolbar-control-h);
  padding: 0 10px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: none;
}

.members-search-el-input :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(var(--el-color-primary-rgb, 232, 146, 124), 0.42);
  box-shadow: 0 0 0 3px
    color-mix(in srgb, var(--el-color-primary) 12%, transparent);
}

.members-search-el-input :deep(.el-input__inner) {
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
}

.members-search-el-input :deep(.el-input__inner::placeholder) {
  color: #94a3b8;
  font-weight: 500;
}

.members-search-el-input :deep(.el-input__prefix) {
  display: inline-flex;
  align-items: center;
}

.members-search-el-input :deep(.members-search-el-icon) {
  flex-shrink: 0;
  color: #64748b;
}

.members-search-el-input :deep(.el-input__wrapper.is-focus .members-search-el-icon) {
  color: var(--el-color-primary);
}
.members-renew-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem 1rem;
  margin: 0 0 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  border: 1px solid #fde68a;
  background: #fffbeb;
}

.members-renew-banner__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #92400e;
}

.members-renew-banner__text strong {
  color: #b45309;
}

.members-awaiting-banner {
  margin: 0 0 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
}

.members-awaiting-banner__text {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #1e40af;
}

.members-awaiting-banner__text strong {
  color: #1d4ed8;
}
.members-region-select-el {
  width: 118px;
  --el-component-size: var(--members-toolbar-control-h);
}

.members-region-select-el :deep(.el-select__wrapper) {
  min-height: var(--members-toolbar-control-h);
  height: var(--members-toolbar-control-h);
  padding: 0 10px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  font-size: 12px;
  font-weight: 600;
}

.members-region-select-el :deep(.el-select__wrapper.is-focused) {
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--el-color-primary) 42%, #e2e8f0) inset,
    0 0 0 3px color-mix(in srgb, var(--el-color-primary) 12%, transparent);
}

.members-region-select-el :deep(.el-select__placeholder),
.members-region-select-el :deep(.el-select__selected-item) {
  font-size: 12px;
  font-weight: 600;
}

.members-export-actions .members-export-btn {
  --el-button-size: var(--members-toolbar-control-h);
  height: var(--members-toolbar-control-h);
  min-height: var(--members-toolbar-control-h);
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  border-radius: 999px;
}

.members-export-actions .members-export-btn :deep(.el-icon),
.members-export-actions .members-export-btn svg {
  vertical-align: -2px;
}

.members-region-select-el--wide {
  width: 168px;
}
.leave-mode-select {
  width: 100%;
}
.leave-range-picker {
  width: 100%;
}
.members-refund-consumption-list {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  overflow: hidden;
}
.members-refund-consumption-list li {
  display: grid;
  gap: 8px;
  padding: 8px 10px;
  font-size: 12px;
  background: #fff;
}
.members-refund-consumption-list:not(.members-refund-consumption-list--refund-detail) li {
  grid-template-columns: 92px 1fr auto;
  align-items: center;
}
.members-refund-consumption-list li + li {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.members-refund-consumption-date {
  color: var(--el-text-color-secondary, #909399);
}
.modal-card--refund {
  max-width: 440px;
}

/* 列表序号 pill */
.members-cell-pill {
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

.members-cell-pill--idx {
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

.members-view-fill :deep(.td-members-idx .cell) {
  overflow: visible;
  white-space: nowrap;
  text-overflow: clip;
}

.members-operation-time {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--el-text-color-regular, #606266);
  white-space: nowrap;
}

/* 手机端：卡片列表 */
.members-table-host--mobile-cards {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.members-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  padding: 0.65rem 0.75rem 0.85rem;
  min-height: 120px;
}

.members-mobile-empty {
  margin: 2rem 0;
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
}

.member-profile-card {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.85rem 0.9rem 0.7rem;
  border-radius: 12px;
  border: 1px solid #e8edf3;
  background: #fff;
}

.member-profile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.65rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid #f1f5f9;
}

.member-profile-card__head-left {
  display: flex;
  align-items: flex-start;
  gap: 0.45rem;
  min-width: 0;
  flex: 1;
}

.member-profile-card__identity {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.member-profile-card__name {
  font-size: 15px;
  font-weight: 800;
  line-height: 1.3;
  color: #0f172a;
  word-break: break-word;
}

.member-profile-card__wechat {
  font-size: 11px;
  font-weight: 600;
  line-height: 1.25;
  color: #94a3b8;
}

.member-profile-card__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.5rem;
}

.member-profile-card__balance {
  font-size: 13px;
  font-weight: 700;
}

.member-profile-card__start-date {
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #64748b;
}

.member-profile-card__ship {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.6rem 0.7rem;
  border-radius: 8px;
  background: #f8fafc;
}

.member-profile-card__contact {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.member-profile-card__phone {
  font-size: 14px;
  font-weight: 700;
  color: #0d5c46;
  text-decoration: none;
}

.member-profile-card__addr {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #475569;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.member-profile-card__area {
  margin: 0;
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.member-profile-card__leave {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  margin: 0;
  padding: 0.45rem 0.55rem;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.45;
  background: #fff1f2;
  border: 1px solid #fecdd3;
}

.member-profile-card__leave-label {
  flex-shrink: 0;
  font-weight: 700;
  color: #be123c;
}

.member-profile-card__leave-text {
  flex: 1;
  min-width: 0;
  color: #9f1239;
  word-break: break-word;
}

.member-profile-card__tomorrow-leave {
  margin: 0;
}

.member-profile-card__remark {
  display: flex;
  align-items: flex-start;
  gap: 0.4rem;
  margin: 0;
  padding: 0.45rem 0.55rem;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.45;
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.member-profile-card__remark-label {
  flex-shrink: 0;
  font-weight: 700;
  color: #b45309;
}

.member-profile-card__remark-text {
  flex: 1;
  min-width: 0;
  color: #92400e;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.member-profile-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.65rem;
  margin-top: 0.1rem;
  padding-top: 0.55rem;
  border-top: 1px solid #f1f5f9;
}

.member-profile-card__time {
  flex: 1;
  min-width: 0;
  font-size: 11px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
  color: #94a3b8;
}

.member-profile-card__more-btn {
  flex-shrink: 0;
  margin: 0;
}

@media (max-width: 768px) {
  .members-toolbar-row {
    flex-direction: column;
    flex-wrap: nowrap;
    align-items: stretch;
    gap: 10px;
  }

  .members-search-wrap {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    min-width: 0;
    max-width: none;
  }

  .members-search-el-input {
    flex: 1 1 auto;
    min-width: 0;
  }

  .members-filter-toggle {
    flex: 0 0 32px;
    width: 32px;
    height: 32px;
    margin: 0;
    padding: 0;
    border: 1px solid #e2e8f0;
    border-radius: 999px;
    background: #fff;
    color: #64748b;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .members-filter-toggle svg {
    transition: transform 0.2s ease;
  }

  .members-filter-toggle.is-open svg {
    transform: rotate(180deg);
  }

  .members-renew-banner,
  .members-awaiting-banner {
    margin-left: 0.75rem;
    margin-right: 0.75rem;
  }
}
</style>
