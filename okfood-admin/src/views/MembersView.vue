<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import {
  Search,
  Phone,
  X,
  Trash2,
  MapPin,
  CalendarOff,
  Pencil,
  Download,
  Receipt,
  ChevronDown,
  History,
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

/** 本页表格数据（本地 ref；同步写入 memberList 供登出清空等兼容） */
const membersRows = ref([])

const membersPage = ref(1)
const membersPageSize = ref(20)
const membersTotal = ref(0)
const membersLoading = ref(false)
const searchQuery = ref('')
/** 有效期：全部 | 生效中 | 已过期（默认全部，仅点选后带 validity 参数） */
const membersValidityTab = ref('all')
/** 套餐：'' | 周卡 | 月卡 */
const membersPlanFilter = ref('')
/** 片区：'' | 'unassigned' | 区域 id 字符串 */
const membersRegionFilter = ref('')
/** 会员状态筛选：'' | inactive 未开卡（不含暂停配送） | paused 暂停配送 | leave 请假中；三者互斥 */
const membersStatusSegment = ref('')
const regionFilterOptions = ref([])

/** 顶栏全库统计（不受当前搜索/筛选影响） */
const membersStats = ref({ total: null, active: null, expired: null })
const membersStatsLoading = ref(true)

const membersTotalPages = computed(() =>
  Math.max(1, Math.ceil(membersTotal.value / membersPageSize.value)),
)

/** el-table 行主键：组合 id+phone，避免 bigint/重复 id 导致 Diff 落在已销毁的 DOM 上 */
function memberRowKey(row) {
  return `${String(row?.id ?? '')}__${String(row?.phone ?? '')}`
}

function validityQuery() {
  if (membersValidityTab.value === 'expired') return 'expired'
  if (membersValidityTab.value === 'active') return 'active'
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

/** 再次点击同一项则清除状态筛选 */
function selectMembersStatusSegment(seg) {
  const next = membersStatusSegment.value === seg ? '' : seg
  membersStatusSegment.value = next
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

async function fetchMemberStats() {
  if (!adminAccessToken.value) return
  membersStatsLoading.value = true
  try {
    const data = await apiJson('/api/admin/users/stats', {}, { auth: true })
    membersStats.value = {
      total: Number(data?.total) || 0,
      active: Number(data?.active) || 0,
      expired: Number(data?.expired) || 0,
    }
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      membersStats.value = { total: null, active: null, expired: null }
      return
    }
    membersStats.value = { total: null, active: null, expired: null }
  } finally {
    membersStatsLoading.value = false
  }
}

const memberDeletingId = ref(null)
const membersExporting = ref(false)

async function deleteMemberRow(u) {
  if (!u?.id) return
  const label = `${u.name || '—'} · ${u.phone || ''}`
  const ok = window.confirm(
    `确定删除该会员？\n${label}\n\n若有余额流水、配送记录、单次点餐或开卡工单，将仅做逻辑删除并保留数据；若四项均无记录则物理删除档案与地址。`,
  )
  if (!ok) return
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

/** 操作列「更多」下拉：消费记录、操作记录、删除等低频操作，减少表格右侧视觉噪音 */
function onMembersActionDropdown(command, row) {
  if (command === 'records') {
    void openMemberDeliveryRecords(row)
    return
  }
  if (command === 'operation_logs') {
    void openMemberOperationLogs(row)
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
    params.set('validity', 'active')
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
    await nextTick()
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
      { wch: 12 },
      { wch: 28 },
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, '会员档案')
    const stamp = shanghaiTodayYmd()
    XLSX.writeFile(wb, `会员档案_剩余次数大于0_${stamp}.xlsx`)
    showToast(`已导出 ${out.length} 条（已排除剩余次数为 0）`, 'success')
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

watch(membersValidityTab, () => {
  if (!adminAccessToken.value) return
  membersPage.value = 1
  void fetchMembers()
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
  if (status === '请假中') return 'member-pill member-pill--rose'
  if (status === '待续费') return 'member-pill member-pill--amber'
  if (status === '已过期') return 'member-pill member-pill--slate'
  if (status === '未开卡') return 'member-pill member-pill--slate'
  if (status === '暂停配送') return 'member-pill member-pill--slate'
  return 'member-pill member-pill--emerald'
}

function planTagClass(plan) {
  if (plan === '周卡') return 't-plan--week'
  if (plan === '月卡') return 't-plan--month'
  return 't-plan--count'
}

/** --- 手工请假（管理端，不受小程序当日截止时间限制） --- */
const showLeaveModal = ref(false)
const leaveSaving = ref(false)
const leaveTarget = ref(null)
const leaveMode = ref('tomorrow')
/** 多天请假（区间）：YYYY-MM-DD，与小程序「多天请假」同一接口口径 */
const leaveRangeStart = ref('')
const leaveRangeEnd = ref('')

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
    const payload = { phone: u.phone, type: leaveMode.value }
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
        return { delivery_date: ymd, meal_units: mealUnits }
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

async function onMemberAddressesSaved() {
  await fetchMembers()
}

onMounted(async () => {
  await loadRegionFilterOptions()
  await fetchMemberStats()
  await fetchMembers()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header table-header--members">

        <div class="members-query-row">
          <div class="search-box search-box--members-inline">
            <Search :size="18" />
            <el-input
              v-model="searchQuery"
              clearable
              placeholder="搜索姓名、电话或片区地址..."
              class="members-search-el-input"
            />
          </div>
          <div v-if="adminAccessToken" class="members-export-actions">
            <el-button type="primary" plain size="small" class="members-export-btn" :loading="membersExporting"
              :disabled="membersLoading" title="按当前搜索与筛选拉取全部分页；自动排除剩余次数为 0 的会员" @click="exportMembersExcel">
              <Download :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
              导出 Excel
            </el-button>
          </div>
          <div class="members-filter-toolbar">
            <div class="members-validity-tabs" role="tablist" aria-label="会员有效期">
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'all' }"
                :aria-selected="membersValidityTab === 'all'"
                @click="membersValidityTab = 'all'"
              >
                全部
              </el-button>
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'active' }"
                :aria-selected="membersValidityTab === 'active'"
                @click="membersValidityTab = 'active'"
              >
                生效中
              </el-button>
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'expired' }"
                :aria-selected="membersValidityTab === 'expired'"
                @click="membersValidityTab = 'expired'"
              >
                已过期
              </el-button>
            </div>
            <div class="members-extra-filters" aria-label="套餐、片区与状态筛选">
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
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersStatusSegment === 'inactive' }"
                :aria-selected="membersStatusSegment === 'inactive'"
                title="未激活会员卡且非暂停配送"
                @click="selectMembersStatusSegment('inactive')"
              >
                未开卡
              </el-button>
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersStatusSegment === 'paused' }"
                :aria-selected="membersStatusSegment === 'paused'"
                title="会员卡停用（暂停配送）"
                @click="selectMembersStatusSegment('paused')"
              >
                暂停配送
              </el-button>
              <el-button
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersStatusSegment === 'leave' }"
                :aria-selected="membersStatusSegment === 'leave'"
                @click="selectMembersStatusSegment('leave')"
              >
                请假中
              </el-button>
            </div>
          </div>
        </div>
      </div>
      <AdminTable
        variant="members"
        size="small"
        :data="membersRows"
        :loading="membersLoading"
        :row-key="memberRowKey"
        empty-text="暂无会员数据"
      >
        <el-table-column label="会员信息" min-width="100">
          <template #default="{ row: u }">
            <div class="t-name">
              {{ u.name }}
            </div>
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
            <div class="member-phone-cell">
              <Phone :size="12" class="member-phone-icon" />
              <span class="member-phone-num">{{ u.phone || '—' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="级别" align="center" min-width="75">
          <template #default="{ row: u }">
            <span class="t-plan" :class="planTagClass(u.plan)">{{ u.plan }}</span>
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
        <el-table-column label="备注" min-width="100" class-name="td-remarks">
          <template #default="{ row: u }">
            {{ u.remarks || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" align="right" min-width="220" fixed="right">
          <template #default="{ row: u }">
            <div class="members-row-actions members-row-actions--denoised">
              <el-button
                type="primary"
                link
                size="small"
                class="btn-members-link"
                title="手工请假"
                @click="openLeaveMember(u)"
              >
                <CalendarOff :size="12" aria-hidden="true" style="margin-right: 4px" />
                请假
              </el-button>
              <el-button
                type="primary"
                link
                size="small"
                class="btn-members-link"
                title="地址管理：查看全部配送地址，编辑、地图选点，并可代为切换默认地址"
                @click="openMemberAddresses(u)"
              >
                <MapPin :size="12" aria-hidden="true" style="margin-right: 4px" />
                地址
              </el-button>
              <el-button
                type="primary"
                link
                size="small"
                class="btn-members-link"
                title="修改会员信息"
                @click="openEditMember(u)"
              >
                <Pencil :size="12" aria-hidden="true" style="margin-right: 4px" />
                修改
              </el-button>
              <el-dropdown
                trigger="click"
                @command="(cmd) => onMembersActionDropdown(cmd, u)"
              >
                <el-button type="primary" link size="small" class="btn-members-link">
                  更多
                  <ChevronDown :size="14" aria-hidden="true" class="members-more-chevron" />
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="records">
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
                    <el-dropdown-item
                      command="delete"
                      divided
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
      <div v-if="adminAccessToken" class="members-pagination">
        <el-button plain size="small" :disabled="membersPage <= 1" @click="goMembersPrev">上一页</el-button>
        <span class="members-page-meta"
          >第 {{ membersPage }} / {{ membersTotalPages }} 页 · 共 {{ membersTotal }} 条</span
        >
        <el-button plain size="small"
          :disabled="membersPage >= membersTotalPages"
          @click="goMembersNext"
        >
          下一页
        </el-button>
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
          </p>
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
            <p>已送达配送日</p>
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
            下列为订阅套餐在骑手确认送达后扣次的业务日，按新到旧排列。
          </p>
          <div v-if="deliveryRecordLoading" class="delivery-records-loading">加载中…</div>
          <template v-else>
            <p class="delivery-records-summary">
              共 <strong>{{ deliveryRecordTotal }}</strong> 个配送日
              <span v-if="deliveryRecordTruncated" class="delivery-records-truncated">（仅显示最近部分，可联系技术导出全量）</span>
            </p>
            <ul v-if="deliveryRecordDates.length" class="delivery-records-list">
              <li v-for="(row, idx) in deliveryRecordDates" :key="`${row.delivery_date}-${idx}`">
                <span class="delivery-records-idx">{{ idx + 1 }}</span>
                <span class="delivery-records-line">
                  {{ formatDeliveryBizYmdLabel(row.delivery_date) }}
                  <span class="delivery-records-ymd-muted">（{{ row.delivery_date }}）</span>
                </span>
                <span class="delivery-records-units">{{ row.meal_units }} 份</span>
              </li>
            </ul>
            <p v-else class="delivery-records-empty">暂无记录。未产生「确认送达」或无套餐扣次时为空。</p>
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
            记录该会员通过小程序或后台产生的关键操作（暂停配送、修改份数、地址与请假等），含时间与摘要。
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

  </section>
</template>

<style scoped>
.members-search-el-input {
  flex: 1;
  min-width: 0;
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
</style>
