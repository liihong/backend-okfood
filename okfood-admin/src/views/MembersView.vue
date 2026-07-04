<script setup>
defineOptions({ name: 'MembersView' })
import { ref, watch, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import {
  Search,
  X,
  Trash2,
  MapPin,
  CalendarOff,
  Pencil,
  Download,
  Receipt,
  ChevronDown,
  History,
  Banknote,
  UtensilsCrossed,
  Ticket,
} from 'lucide-vue-next'
import * as XLSX from 'xlsx'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { parseApiDateTimeBeijing } from '../utils/beijingDateTime.js'
import MemberEditModal from './components/MemberEditModal.vue'
import MemberAddressesModal from './components/MemberAddressesModal.vue'
import MemberMealCompensationModal from './components/MemberMealCompensationModal.vue'

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
/** 套餐：'' | 周卡 | 月卡 */
const membersPlanFilter = ref('')
/** 片区：'' | 'unassigned' | 区域 id 字符串 */
const membersRegionFilter = ref('')
/** 会员卡状态：'' 全部 | inactive 未开卡 | paused 暂停配送 | leave 请假中 */
const membersStatusSegment = ref('')
const regionFilterOptions = ref([])

const route = useRoute()
const router = useRouter()

/** 当前是否为待续费筛选（客服续卡提醒场景） */
const isRenewPendingFilter = computed(() => membersStatusSegment.value === 'renew_pending')

/** 从路由 query 恢复筛选（会员统计页跳转带参） */
function applyMembersRouteQueryFilters() {
  const q = route.query
  const validity = String(q.validity ?? '').trim()
  if (['active', 'expired', 'refunded'].includes(validity)) {
    membersValidityFilter.value = validity
  }
  const segment = String(q.segment ?? '').trim()
  if (['inactive', 'paused', 'leave', 'renew_pending'].includes(segment)) {
    membersStatusSegment.value = segment
  }
  const region = String(q.region ?? '').trim()
  if (region === 'unassigned') {
    membersRegionFilter.value = 'unassigned'
  }
}

/** 顶栏全库统计（不受当前搜索/筛选影响） */
const membersStats = ref({ total: null, active: null, expired: null, refunded: null, refund_rate_percent: null })
const membersStatsLoading = ref(true)

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

async function fetchMemberStats() {
  if (!adminAccessToken.value) return
  membersStatsLoading.value = true
  try {
    const data = await apiJson('/api/admin/users/stats', {}, { auth: true })
    membersStats.value = {
      total: Number(data?.total) || 0,
      active: Number(data?.active) || 0,
      expired: Number(data?.expired) || 0,
      refunded: Number(data?.refunded) || 0,
      refund_rate_percent: data?.refund_rate_percent ?? null,
    }
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      membersStats.value = { total: null, active: null, expired: null, refunded: null, refund_rate_percent: null }
      return
    }
    membersStats.value = { total: null, active: null, expired: null, refunded: null, refund_rate_percent: null }
  } finally {
    membersStatsLoading.value = false
  }
}

const memberDeletingId = ref(null)
const membersExporting = ref(false)

async function deleteMemberRow(u) {
  if (!u?.id) return
  const label = `${u.name || '—'} · ${u.phone || ''}`
  try {
    await ElMessageBox.confirm(
      `${label}\n\n若有余额流水、配送记录、单次点餐或开卡工单，将仅做逻辑删除并保留数据；若四项均无记录则物理删除档案与地址。`,
      '确定删除该会员？',
      { type: 'warning', confirmButtonText: '确定删除', cancelButtonText: '取消' },
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
    await fetchMemberStats()
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
  if (command === 'addresses') {
    void openMemberAddresses(row)
    return
  }
  if (command === 'edit') {
    void openEditMember(row)
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
  if (pq) params.set('plan_type', pq)
  const q = searchQuery.value.trim()
  if (q) params.set('q', q)
  if (membersStatusSegment.value === 'inactive') params.set('inactive_only', '1')
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
      '剩余／总次数': u.balanceLabel || String(u.balance),
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
    const exportTag = isRenewPendingFilter.value ? '待续费' : '剩余次数大于0'
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
  if (status === '已过期') return 'member-pill member-pill--slate'
  if (status === '未开卡') return 'member-pill member-pill--slate'
  if (status === '暂停配送') return 'member-pill member-pill--slate'
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
    await fetchMemberStats()
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

/** --- 修改会员（弹窗子组件 MemberEditModal） --- */
const showEditModal = ref(false)
const editTargetMember = ref(null)

watch(showEditModal, (v) => {
  if (!v) editTargetMember.value = null
})

async function onMemberEditSaved() {
  await fetchMembers()
  await fetchMemberStats()
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

function formatDeliveryBizYmdLabel(ymd) {
  const s = typeof ymd === 'string' ? ymd.trim().slice(0, 10) : ''
  if (s.length !== 10) return ymd != null ? String(ymd) : '—'
  try {
    const d = new Date(`${s}T12:00:00+08:00`)
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      weekday: 'short',
    }).format(d)
  } catch {
    return s
  }
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
        const kindRaw = row.deduction_kind
        const kind =
          kindRaw === 'single_meal'
            ? 'single_meal'
            : kindRaw === 'meal_compensation'
              ? 'meal_compensation'
              : 'subscription'
        return { delivery_date: ymd, meal_units: mealUnits, deduction_kind: kind }
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
const operationLogPage = ref(1)
const operationLogPageSize = 20

const operationLogTotalPages = computed(() =>
  Math.max(1, Math.ceil(operationLogTotal.value / operationLogPageSize)),
)

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

async function fetchMemberOperationLogsPage() {
  if (!operationLogTarget.value?.id) return
  operationLogLoading.value = true
  try {
    const mid = Number(operationLogTarget.value.id)
    const p = operationLogPage.value
    const ps = operationLogPageSize
    const data = await apiJson(
      `/api/admin/users/${mid}/operation-logs?page=${p}&page_size=${ps}`,
      {},
      { auth: true },
    )
    operationLogItems.value = Array.isArray(data?.items) ? data.items : []
    operationLogTotal.value = Number(data?.total) || 0
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
  operationLogPage.value = 1
  operationLogItems.value = []
  operationLogTotal.value = 0
  showOperationLogModal.value = true
  await fetchMemberOperationLogsPage()
}

function goOperationLogPrev() {
  if (operationLogPage.value <= 1) return
  operationLogPage.value -= 1
  void fetchMemberOperationLogsPage()
}

function goOperationLogNext() {
  if (operationLogPage.value >= operationLogTotalPages.value) return
  operationLogPage.value += 1
  void fetchMemberOperationLogsPage()
}

watch(showOperationLogModal, (v) => {
  if (!v) {
    operationLogTarget.value = null
    operationLogItems.value = []
    operationLogTotal.value = 0
    operationLogPage.value = 1
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
  await fetchMemberStats()
}

/** --- 退卡退款：按消费日菜单单价扣款后退还余款 --- */
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
      `${u.name || '—'} · ${u.phone || ''}\n\n已消费 ${p.meals_consumed} 次，退剩余 ${p.meals_remaining} 次\n应退 ¥ ${fmtRefundYuan(amt)}`,
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
    await fetchMemberStats()
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
  await loadRegionFilterOptions()
  await fetchMemberStats()
  await fetchMembers()
  await nextTick()
  updateMembersTableHeight()
  membersTableResizeObserver = new ResizeObserver(() => {
    updateMembersTableHeight()
  })
  if (membersTableHostRef.value) {
    membersTableResizeObserver.observe(membersTableHostRef.value)
  }
})

onUnmounted(() => {
  membersTableResizeObserver?.disconnect()
  membersTableResizeObserver = null
})
</script>

<template>
  <section class="tab-content animate-up members-view-fill">
    <div class="table-container table-container--members-fill">
      <div class="table-header table-header--members">
        <!-- 单行工具栏：左起「搜索 → 全部/筛选…」，右侧「统计 + 导出」 -->
        <div class="members-toolbar-row">
          <div class="members-toolbar-primary">
            <div class="search-box search-box--members-inline">
              <Search :size="18" />
              <el-input
                v-model="searchQuery"
                clearable
                placeholder="输入姓名、手机或地址检索…"
                class="members-search-el-input"
              />
            </div>
            <div class="members-toolbar-filters-scroll">
              <div class="members-filter-toolbar">
                <div class="members-extra-filters" aria-label="状态、套餐、片区与会员卡状态筛选">
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
                    <el-option label="周卡" value="周卡" />
                    <el-option label="月卡" value="月卡" />
                  </el-select>
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
                  <label class="members-filter-label" for="members-card-status-filter">会员卡状态</label>
                  <el-select
                    id="members-card-status-filter"
                    v-model="membersStatusSegment"
                    class="members-region-select-el"
                    placeholder="全部"
                    @change="onCardStatusFilterChange"
                  >
                    <el-option label="全部" value="" />
                    <el-option label="未开卡" value="inactive" />
                    <el-option label="暂停配送" value="paused" />
                    <el-option label="请假中" value="leave" />
                    <el-option label="待续费" value="renew_pending" />
                  </el-select>
                </div>
              </div>
            </div>
          </div>
          <div class="members-toolbar-trailing">
            <div v-if="adminAccessToken" class="members-overview-stats" aria-label="会员档案统计">
              <span class="members-overview-stat">
                <span class="members-overview-stat__label">总户数</span><span class="members-overview-stat__sep">:</span>
                <strong class="members-overview-stat__value members-overview-stat__value--neutral">{{
                  membersStatsLoading ? '…' : membersStats.total ?? '—'
                }}</strong>
              </span>
              <span class="members-overview-stat">
                <span class="members-overview-stat__label">生效中</span><span class="members-overview-stat__sep">:</span>
                <strong class="members-overview-stat__value members-overview-stat__value--active">{{
                  membersStatsLoading ? '…' : membersStats.active ?? '—'
                }}</strong>
              </span>
              <span class="members-overview-stat">
                <span class="members-overview-stat__label">已过期</span><span class="members-overview-stat__sep">:</span>
                <strong class="members-overview-stat__value members-overview-stat__value--muted">{{
                  membersStatsLoading ? '…' : membersStats.expired ?? '—'
                }}</strong>
              </span>
              <span class="members-overview-stat">
                <span class="members-overview-stat__label">已退款</span><span class="members-overview-stat__sep">:</span>
                <strong class="members-overview-stat__value members-overview-stat__value--danger">{{
                  membersStatsLoading ? '…' : membersStats.refunded ?? '—'
                }}</strong>
              </span>
              <span class="members-overview-stat">
                <span class="members-overview-stat__label">退款率</span><span class="members-overview-stat__sep">:</span>
                <strong class="members-overview-stat__value members-overview-stat__value--danger">
                  <template v-if="membersStatsLoading">…</template>
                  <template v-else-if="membersStats.refund_rate_percent != null">
                    {{ Number(membersStats.refund_rate_percent).toFixed(2) }}%
                  </template>
                  <template v-else>—</template>
                </strong>
              </span>
            </div>
            <div v-if="adminAccessToken" class="members-export-actions">
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
      <div v-if="isRenewPendingFilter" class="members-renew-banner" role="status">
        <p class="members-renew-banner__text">
          当前展示<strong>待续费</strong>会员（生效中、剩余次数 ≤ 2，不含暂停/退款/请假）。可导出名单后电话/微信提醒续卡，或批量发放续卡优惠券。
        </p>
        <el-button type="warning" size="small" @click="goBatchGrantCouponsForRenewPending">
          <Ticket :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
          批量发券
        </el-button>
      </div>
      <div ref="membersTableHostRef" class="members-table-host">
        <AdminTable
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
            <div v-if="u.wechat_name" class="t-sub t-wechat">微信 {{ u.wechat_name }}</div>
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
          min-width="104"
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
        <el-table-column label="请假时间" min-width="150" width="120" class-name="td-col-leave">
          <template #default="{ row: u }">
            <div v-if="!u.leave_kind" class="leave-cell leave-cell--empty">—</div>
            <div v-else class="leave-cell" :title="u.leave_detail || ''">
              <div class="leave-detail">{{ u.leave_detail }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="剩余 / 总次数" align="center" min-width="90">
          <template #default="{ row: u }">
            <div class="balance-cell">
              <span class="balance-text" :class="{ warning: u.balance <= 2 && u.is_active }">{{
                u.balanceLabel
              }}</span>
              <p
                v-if="u.tomorrow_leave && !u.is_on_leave_today"
                class="balance-leave-hint balance-leave-hint--tomorrow"
              >
                明日配送请假
              </p>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="80">
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
              <el-dropdown trigger="click" @command="(cmd) => onMembersActionDropdown(cmd, u)">
                <el-button type="primary" link size="small" class="btn-members-link">
                  更多
                  <ChevronDown :size="14" aria-hidden="true" class="members-more-chevron" />
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="leave">
                      <span class="members-dropdown-item-inner" title="手工请假">
                        <CalendarOff :size="14" aria-hidden="true" />
                        请假
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="addresses">
                      <span
                        class="members-dropdown-item-inner"
                        title="地址管理：查看全部配送地址，编辑、地图选点，并可代为切换默认地址"
                      >
                        <MapPin :size="14" aria-hidden="true" />
                        地址
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="edit">
                      <span class="members-dropdown-item-inner" title="修改会员信息">
                        <Pencil :size="14" aria-hidden="true" />
                        修改
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="records" divided>
                      <span class="members-dropdown-item-inner" title="套餐已确认送达的业务日（扣次记录）">
                        <Receipt :size="14" aria-hidden="true" />
                        消费记录
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="operation_logs">
                      <span
                        class="members-dropdown-item-inner"
                        title="该会员在小程序或后台触发的配送、地址、请假等操作留痕"
                      >
                        <History :size="14" aria-hidden="true" />
                        操作记录
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="meal_compensation" divided>
                      <span
                        class="members-dropdown-item-inner"
                        title="餐品问题赔付：将已消费次数补回余额，并写入操作审计"
                      >
                        <UtensilsCrossed :size="14" aria-hidden="true" />
                        补餐赔付
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="grant_coupon">
                      <span
                        class="members-dropdown-item-inner"
                        title="跳转优惠券发放页，向该会员发放续卡优惠券"
                      >
                        <Ticket :size="14" aria-hidden="true" />
                        发优惠券
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item command="refund" :disabled="!canMemberRefund(u)">
                      <span
                        class="members-dropdown-item-inner"
                        title="按已消费/剩余次数计算应退金额，确认后写入财务扣减"
                      >
                        <Banknote :size="14" aria-hidden="true" />
                        退卡退款
                      </span>
                    </el-dropdown-item>
                    <el-dropdown-item
                      command="delete"
                      :disabled="memberDeletingId === u.id"
                      class="members-dd-item-delete"
                    >
                      <span class="members-dropdown-item-inner">
                        <Trash2 :size="14" aria-hidden="true" />
                        {{ memberDeletingId === u.id ? '删除中…' : '删除' }}
                      </span>
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
        </AdminTable>
      </div>
      <div v-if="adminAccessToken" class="members-pagination">
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

    <div
      v-if="showLeaveModal"
      class="modal-overlay"
      v-esc-close="() => (showLeaveModal = false)"
      @click.self="showLeaveModal = false"
    >
      <div class="modal-card modal-card--leave">
        <div class="modal-header">
          <div class="header-info">
            <h3>手工请假</h3>
            <p>ADMIN LEAVE</p>
          </div>
          <el-button text circle class="close-btn" @click="showLeaveModal = false">
            <X :size="20" />
          </el-button>
        </div>
        <form class="modal-form" @submit.prevent="submitLeaveMember">
          <p v-if="leaveTarget" class="modal-hint modal-hint--tight">
            {{ leaveTarget.name || '—' }} · {{ leaveTarget.phone || '' }}
            <span v-if="leaveTarget.plan"> · {{ leaveTarget.plan }}</span>
          </p>
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
            <p class="modal-hint">后台代操作不校验当日请假截止时间；日期均为业务日。</p>
          </div>
          <el-button type="primary" class="btn-submit-order" native-type="submit" :loading="leaveSaving"
            :disabled="leaveSaving">
            {{ leaveSaving ? '提交中…' : '确认' }}
          </el-button>
        </form>
      </div>
    </div>

    <MemberEditModal v-model:open="showEditModal" :member="editTargetMember" :region-options="regionFilterOptions"
      @saved="onMemberEditSaved" />

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

    <div
      v-if="showDeliveryRecordModal"
      class="modal-overlay"
      v-esc-close="() => (showDeliveryRecordModal = false)"
      @click.self="showDeliveryRecordModal = false"
    >
      <div class="modal-card modal-card--delivery-records">
        <div class="modal-header">
          <div class="header-info">
            <h3>消费记录</h3>
            <p>套餐送达 · 单次购买</p>
          </div>
          <div
            v-if="!deliveryRecordLoading"
            class="delivery-records-header-stat"
          >
            截至当前已消费 <strong>{{ deliveryRecordTotalMeals }}</strong> 份餐
          </div>
          <el-button text circle class="close-btn" @click="showDeliveryRecordModal = false">
            <X :size="20" />
          </el-button>
        </div>
        <div class="modal-body modal-body--delivery-records">
          <p v-if="deliveryRecordTarget" class="modal-hint modal-hint--tight">
            {{ deliveryRecordTarget.name || '—' }} · {{ deliveryRecordTarget.phone || '' }}
          </p>
          <p class="modal-hint delivery-records-caption">
            下列包含订阅套餐确认送达扣次、单次购买使用会员卡扣次的供餐日，以及补餐赔付记录，按新到旧排列。
          </p>
          <div v-if="deliveryRecordLoading" class="delivery-records-loading">加载中…</div>
          <template v-else>
            <p class="delivery-records-summary">
              共 <strong>{{ deliveryRecordTotal }}</strong> 条记录
              <span v-if="deliveryRecordTruncated" class="delivery-records-truncated">（仅显示最近部分，可联系技术导出全量）</span>
            </p>
            <ul v-if="deliveryRecordDates.length" class="delivery-records-list">
              <li
                v-for="(row, idx) in deliveryRecordDates"
                :key="`${row.delivery_date}-${row.deduction_kind}-${idx}`"
              >
                <span class="delivery-records-idx">{{ idx + 1 }}</span>
                <span class="delivery-records-line">
                  {{ formatDeliveryBizYmdLabel(row.delivery_date) }}
                  <span class="delivery-records-ymd-muted">（{{ row.delivery_date }}）</span>
                  <span
                    v-if="row.deduction_kind === 'single_meal'"
                    class="delivery-records-kind-badge"
                  >单次购买</span>
                  <span
                    v-else-if="row.deduction_kind === 'meal_compensation'"
                    class="delivery-records-kind-badge delivery-records-kind-badge--compensation"
                  >补餐</span>
                </span>
                <span
                  class="delivery-records-units"
                  :class="{ 'delivery-records-units--compensation': row.deduction_kind === 'meal_compensation' }"
                >
                  {{ row.deduction_kind === 'meal_compensation' ? '+' : '' }}{{ row.meal_units }} 份
                </span>
              </li>
            </ul>
            <p v-else class="delivery-records-empty">
              暂无消费记录。套餐确认送达扣次或单次购买（会员卡）扣次后将显示在此。
            </p>
          </template>
        </div>
      </div>
    </div>

    <div
      v-if="showOperationLogModal"
      class="modal-overlay"
      v-esc-close="() => (showOperationLogModal = false)"
      @click.self="showOperationLogModal = false"
    >
      <div class="modal-card modal-card--operation-logs">
        <div class="modal-header">
          <div class="header-info">
            <h3>操作记录</h3>
            <p>审计日志 · 新到旧</p>
          </div>
          <el-button text circle class="close-btn" @click="showOperationLogModal = false">
            <X :size="20" />
          </el-button>
        </div>
        <div class="modal-body modal-body--operation-logs">
          <p v-if="operationLogTarget" class="modal-hint modal-hint--tight">
            {{ operationLogTarget.name || '—' }} · {{ operationLogTarget.phone || '' }}
          </p>
          <p class="modal-hint operation-logs-caption">
            记录该会员通过小程序或后台产生的关键操作（暂停配送、修改份数、地址与请假、档案修改等），含时间、摘要与操作人，便于后期追责。
          </p>
          <div v-if="operationLogLoading" class="delivery-records-loading">加载中…</div>
          <template v-else>
            <p class="delivery-records-summary operation-logs-summary-line">
              共 <strong>{{ operationLogTotal }}</strong> 条
              <span v-if="operationLogTotalPages > 1" class="operation-logs-page-inline">
                · 第 {{ operationLogPage }} / {{ operationLogTotalPages }} 页
              </span>
            </p>
            <div v-if="operationLogItems.length" class="operation-logs-table-wrap">
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
                    <td class="operation-logs-td-operator">{{ operationLogOperatorLabel(row.operator) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p v-else class="delivery-records-empty">暂无操作记录。</p>
            <div v-if="operationLogTotal > 0" class="operation-logs-pagination">
              <el-button
                plain
                size="small"
                :disabled="operationLogPage <= 1 || operationLogLoading"
                @click="goOperationLogPrev"
              >
                上一页
              </el-button>
              <el-button
                plain
                size="small"
                :disabled="operationLogPage >= operationLogTotalPages || operationLogLoading"
                @click="goOperationLogNext"
              >
                下一页
              </el-button>
            </div>
          </template>
        </div>
      </div>
    </div>

    <div
      v-if="showRefundModal"
      class="modal-overlay"
      v-esc-close="() => !refundSubmitting && (showRefundModal = false)"
      @click.self="!refundSubmitting && (showRefundModal = false)"
    >
      <div class="modal-card modal-card--refund">
        <div class="modal-header">
          <div class="header-info">
            <h3>退卡退款</h3>
            <p>按消费日菜单单价扣款后退还余款</p>
          </div>
          <el-button text circle class="close-btn" :disabled="refundSubmitting" @click="showRefundModal = false">
            <X :size="20" />
          </el-button>
        </div>
        <form class="modal-form" @submit.prevent="submitMemberRefund">
          <p v-if="refundTarget" class="modal-hint modal-hint--tight">
            {{ refundTarget.name || '—' }} · {{ refundTarget.phone || '' }}
            <span v-if="refundTarget.plan"> · {{ refundTarget.plan }}</span>
          </p>
          <div v-if="refundPreviewLoading" class="delivery-records-loading">计算中…</div>
          <template v-else-if="refundPreview">
            <dl class="members-refund-summary">
              <div class="members-refund-row">
                <dt>已消费</dt>
                <dd>{{ refundPreview.meals_consumed }} 次</dd>
              </div>
              <div class="members-refund-row">
                <dt>可退剩余</dt>
                <dd>{{ refundPreview.meals_remaining }} 次</dd>
              </div>
              <div class="members-refund-row">
                <dt>累计总次数</dt>
                <dd>{{ refundPreview.meal_quota_total }} 次</dd>
              </div>
              <div class="members-refund-row">
                <dt>开卡实收合计</dt>
                <dd>¥ {{ fmtRefundYuan(refundPreview.paid_total_yuan) }}</dd>
              </div>
              <div class="members-refund-row">
                <dt>已消费扣款</dt>
                <dd>− ¥ {{ fmtRefundYuan(refundPreview.consumed_value_yuan) }}</dd>
              </div>
              <div class="members-refund-row members-refund-row--amount">
                <dt>应退金额</dt>
                <dd class="members-refund-amount">¥ {{ fmtRefundYuan(refundPreview.refund_amount_yuan) }}</dd>
              </div>
            </dl>
            <ul
              v-if="Array.isArray(refundPreview.consumption_items) && refundPreview.consumption_items.length"
              class="members-refund-consumption-list"
            >
              <li
                v-for="(row, idx) in refundPreview.consumption_items"
                :key="`${row.delivery_date}-${idx}`"
              >
                <span class="members-refund-consumption-date">{{ row.delivery_date }}</span>
                <span class="members-refund-consumption-dish">{{ row.dish_name || '—' }}</span>
                <span class="members-refund-consumption-amt">
                  {{ row.meal_units }} 份 × ¥ {{ fmtRefundYuan(row.unit_price_yuan) }}
                  = ¥ {{ fmtRefundYuan(row.line_total_yuan) }}
                </span>
              </li>
            </ul>
            <p class="modal-hint members-refund-tip">
              确认后将清零该会员剩余次数、暂停配送，并写入财务扣减。请在线下或微信侧按应退金额退款给用户。
            </p>
            <div class="form-group">
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
            <div class="modal-actions">
              <el-button :disabled="refundSubmitting" @click="showRefundModal = false">取消</el-button>
              <el-button type="danger" native-type="submit" :loading="refundSubmitting">确认退卡</el-button>
            </div>
          </template>
        </form>
      </div>
    </div>

  </section>
</template>

<style scoped>
.members-search-el-input {
  flex: 1;
  min-width: 14rem;
  width: 100%;
}

.members-search-el-input :deep(.el-input__wrapper) {
  width: 100%;
}
.members-overview-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: flex-end;
  row-gap: 8px;
  column-gap: 12px;
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  flex: 0 1 auto;
  min-width: 0;
  margin-bottom: 0;
  padding: 0;
  border-radius: 0;
  background: transparent;
}
.members-overview-stat {
  display: inline-flex;
  align-items: baseline;
  flex-wrap: nowrap;
  gap: 0;
  white-space: nowrap;
}
.members-overview-stat__label {
  color: #64748b;
  font-weight: 700;
}
.members-overview-stat__sep {
  color: #64748b;
}
.members-overview-stat__value {
  margin-left: 2px;
  font-size: 16px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  font-family: var(--okfood-font-number);
}
.members-overview-stat__value--neutral {
  color: #0f172a;
}
.members-overview-stat__value--active {
  color: #0d5c46;
}
.members-overview-stat__value--muted {
  color: #64748b;
}
.members-overview-stat__value--danger {
  color: #ef4444;
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

.members-region-select-el {
  width: 118px;
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
.members-refund-summary {
  margin: 0 0 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--el-fill-color-light, #f5f7fa);
}
.members-refund-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
}
.members-refund-row + .members-refund-row {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.members-refund-row dt {
  margin: 0;
  color: var(--el-text-color-secondary, #909399);
}
.members-refund-row dd {
  margin: 0;
  font-weight: 600;
  text-align: right;
}
.members-refund-row--amount dd.members-refund-amount {
  color: var(--el-color-danger, #f56c6c);
  font-size: 18px;
}
.members-refund-tip {
  margin-bottom: 12px;
  line-height: 1.5;
}
.members-refund-consumption-list {
  margin: 0 0 12px;
  padding: 0;
  list-style: none;
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 8px;
  overflow: hidden;
}
.members-refund-consumption-list li {
  display: grid;
  grid-template-columns: 92px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  font-size: 12px;
  background: #fff;
}
.members-refund-consumption-list li + li {
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}
.members-refund-consumption-date {
  color: var(--el-text-color-secondary, #909399);
}
.members-refund-consumption-dish {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.members-refund-consumption-amt {
  font-weight: 600;
  white-space: nowrap;
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
</style>
