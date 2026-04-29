<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { Search, Phone, X, Trash2, MapPin, CalendarOff, Pencil, Download } from 'lucide-vue-next'
import * as XLSX from 'xlsx'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
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
  const pq = membersPlanFilter.value.trim()
  if (pq) params.set('plan_type', pq)
  const q = searchQuery.value.trim()
  if (q) params.set('q', q)
  if (membersStatusSegment.value === 'inactive') params.set('inactive_only', '1')
  else if (membersStatusSegment.value === 'paused') params.set('delivery_deferred_only', '1')
  else if (membersStatusSegment.value === 'leave') params.set('on_leave_only', '1')
  if (membersRegionFilter.value === 'unassigned') params.set('unassigned_region', '1')
  else if (membersRegionFilter.value) {
    const rid = String(membersRegionFilter.value).trim()
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

/** 不含所属片区：优先 detail_address，否则从旧版「片区 + 详细」串去掉 u.area 前缀 */
function memberAddressDetailWithoutArea(u) {
  const detail = typeof u.detail_address === 'string' ? u.detail_address.trim() : ''
  if (detail) return detail
  const rawAddr = String(u.address || '').trim()
  if (!rawAddr || rawAddr.startsWith('（未设置')) return ''
  const areaTag = String(u.area || '').trim()
  if (areaTag && areaTag !== '—' && rawAddr.startsWith(areaTag)) {
    return rawAddr.slice(areaTag.length).trim()
  }
  return rawAddr
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
            <input v-model="searchQuery" placeholder="搜索姓名、电话或片区地址..." />
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
              <select
                id="members-plan-filter"
                v-model="membersPlanFilter"
                class="members-region-select"
                @change="onPlanFilterChange"
              >
                <option value="">全部</option>
                <option value="周卡">周卡</option>
                <option value="月卡">月卡</option>
              </select>
              <label class="members-filter-label" for="members-region-filter">片区</label>
              <select
                id="members-region-filter"
                v-model="membersRegionFilter"
                class="members-region-select"
                @change="onRegionFilterChange"
              >
                <option value="">全部</option>
                <option value="unassigned">未分配</option>
                <option v-for="r in regionFilterOptions" :key="r.id" :value="String(r.id)">
                  {{ r.name || '—' }}
                </option>
              </select>
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
        <el-table-column label="电话" min-width="120" class-name="td-phone">
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
        <el-table-column label="配送地址" min-width="300" show-overflow-tooltip>
          <template #default="{ row: u }">
            {{ memberAddressDetailWithoutArea(u) || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="请假时间" min-width="150" width="120" class-name="td-col-leave">
          <template #default="{ row: u }">
            <div v-if="!u.leave_kind" class="leave-cell leave-cell--empty">—</div>
            <div v-else class="leave-cell" :title="u.leave_detail || ''">
              <span class="leave-badge" :class="'leave-badge--' + u.leave_kind">{{ u.leave_badge }}</span>
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
              <p v-if="u.is_on_leave_today" class="balance-leave-hint">今日配送请假</p>
              <p
                v-else-if="u.tomorrow_leave"
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
        <el-table-column label="操作" align="right" min-width="240" fixed="right">
          <template #default="{ row: u }">
            <div class="members-row-actions">
              <el-button class="btn-members-op" type="primary" title="地址管理：地图选点，地点与门牌分别保存"
                @click="openMemberAddresses(u)">
                <MapPin :size="12" aria-hidden="true" style="margin-right: 5px;" />
                地址
              </el-button>
              <el-button class="btn-members-op" type="warning" title="手工请假" @click="openLeaveMember(u)">
                <CalendarOff :size="12" aria-hidden="true" style="margin-right: 5px;" />
                请假
              </el-button>
              <el-button class="btn-members-op" type="primary" title="修改会员信息" @click="openEditMember(u)">
                <Pencil :size="12" aria-hidden="true" style="margin-right: 5px;" />
                修改
              </el-button>
              <el-button type="danger" class="btn-members-op"
                :disabled="memberDeletingId === u.id"
                title="删除会员"
                @click="deleteMemberRow(u)"
              >
                <Trash2 :size="12" aria-hidden="true" />
                删除
              </el-button>
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
            <select v-model="leaveMode" class="input-delivery-area">
              <option value="tomorrow">明日配送请假（与小程序「明天有事」一致）</option>
              <option value="range">多天配送请假（与小程序「多天请假」一致，需选起止日期）</option>
              <option value="clear_tomorrow">仅取消「明日请假」</option>
              <option value="cancel">清空全部请假</option>
            </select>
            <template v-if="leaveMode === 'range'">
              <div class="form-group form-group--leave-range">
                <label>开始日期</label>
                <input
                  v-model="leaveRangeStart"
                  type="date"
                  class="input-delivery-area"
                  :min="shanghaiTodayYmd()"
                  required
                />
              </div>
              <div class="form-group form-group--leave-range">
                <label>结束日期</label>
                <input
                  v-model="leaveRangeEnd"
                  type="date"
                  class="input-delivery-area"
                  :min="leaveRangeStart || shanghaiTodayYmd()"
                  required
                />
              </div>
            </template>
            <p class="modal-hint">后台代操作不校验当日请假截止时间；日期均为上海业务日。</p>
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

  </section>
</template>
