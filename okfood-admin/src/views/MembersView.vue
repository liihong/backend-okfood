<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { Search, Phone, X, Trash2, MapPin } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import MemberDeliveryMapPicker from '../components/MemberDeliveryMapPicker.vue'
import MemberEditModal from './components/MemberEditModal.vue'

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
/** 仅未开卡 is_active=false */
const membersInactiveOnly = ref(false)
/** 仅当前请假中（与列表「请假中」及后端 on_leave_only 一致） */
const membersOnLeaveOnly = ref(false)
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

function toggleInactiveOnly() {
  membersInactiveOnly.value = !membersInactiveOnly.value
  membersPage.value = 1
  void fetchMembers()
}

function toggleOnLeaveOnly() {
  membersOnLeaveOnly.value = !membersOnLeaveOnly.value
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

async function fetchMembers() {
  if (!adminAccessToken.value) return
  membersLoading.value = true
  try {
    const params = new URLSearchParams({
      page: String(membersPage.value),
      page_size: String(membersPageSize.value),
    })
    const vq = validityQuery()
    if (vq) params.set('validity', vq)
    const pq = membersPlanFilter.value.trim()
    if (pq) params.set('plan_type', pq)
    const q = searchQuery.value.trim()
    if (q) params.set('q', q)
    if (membersInactiveOnly.value) params.set('inactive_only', '1')
    if (membersOnLeaveOnly.value) params.set('on_leave_only', '1')
    if (membersRegionFilter.value === 'unassigned') params.set('unassigned_region', '1')
    else if (membersRegionFilter.value) {
      const rid = String(membersRegionFilter.value).trim()
      if (rid && rid !== 'unassigned') params.set('delivery_region_id', rid)
    }
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

/** --- 会员地址管理（地图选点 + 地点/门牌拆分） --- */
const showAddrModal = ref(false)
const addrMember = ref(null)
const addrList = ref([])
const addrLoading = ref(false)
const addrSaving = ref(false)
/** 当前编辑行：含地图用字符串经纬度 */
const addrEdit = ref(null)
/** 多条地址时下拉切换 */
const addrSelectedId = ref(null)

function formatAddrPca(a) {
  if (!a || typeof a !== 'object') return '—'
  const parts = [a.province, a.city, a.district].filter((x) => x && String(x).trim())
  return parts.length ? parts.join(' ') : '—'
}

function pickAddrEdit(a) {
  const lng = a.location?.lng
  const lat = a.location?.lat
  addrSelectedId.value = Number(a.id)
  addrEdit.value = {
    id: a.id,
    contact_name: a.contact_name || '',
    contact_phone: a.contact_phone || '',
    map_location_text: a.map_location_text || '',
    door_detail: a.door_detail || '',
    remarks: a.remarks || '',
    lngStr: lng != null && lng !== '' ? String(lng) : '',
    latStr: lat != null && lat !== '' ? String(lat) : '',
  }
}

function addrOptionLabel(a) {
  const tag = a.is_default ? '默认 · ' : ''
  return `${tag}${a.contact_name || '—'} ${a.contact_phone || ''}`.trim()
}

function onAddrSelectChange(id) {
  if (id == null || id === '') return
  const row = addrList.value.find((x) => Number(x.id) === Number(id))
  if (row) pickAddrEdit(row)
}

const addrHeadCoordDisplay = computed(() => {
  if (!addrEdit.value) return '—'
  const a = String(addrEdit.value.lngStr ?? '').trim()
  const b = String(addrEdit.value.latStr ?? '').trim()
  if (a && b) return `${a}, ${b}`
  return '未选点'
})

const addrHeadPcaDisplay = computed(() => {
  if (!addrEdit.value) return '—'
  const row = addrList.value.find((x) => Number(x.id) === Number(addrEdit.value.id))
  return formatAddrPca(row)
})

async function openMemberAddresses(u) {
  if (!u?.id) return
  addrMember.value = u
  addrList.value = []
  addrEdit.value = null
  addrSelectedId.value = null
  showAddrModal.value = true
  addrLoading.value = true
  try {
    const list = await apiJson(`/api/admin/users/${Number(u.id)}/addresses`, {}, { auth: true })
    addrList.value = Array.isArray(list) ? list : []
    const def = addrList.value.find((x) => x.is_default) || addrList.value[0]
    if (def) pickAddrEdit(def)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载地址失败', 'error')
    showAddrModal.value = false
  } finally {
    addrLoading.value = false
  }
}

function onAddrMapWarn(msg) {
  const s = typeof msg === 'string' && msg.trim() ? msg.trim() : '地图提示'
  showToast(s, 'error')
}

async function saveMemberAddress() {
  const m = addrMember.value
  const ed = addrEdit.value
  if (!m?.id || !ed?.id) return
  addrSaving.value = true
  try {
    const payload = {
      contact_name: (ed.contact_name || '').trim(),
      contact_phone: (ed.contact_phone || '').trim(),
      map_location_text: (ed.map_location_text || '').trim() || null,
      door_detail: (ed.door_detail || '').trim() || null,
      remarks: (ed.remarks || '').trim() || null,
    }
    const lng = Number(String(ed.lngStr ?? '').trim())
    const lat = Number(String(ed.latStr ?? '').trim())
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      payload.location = { lng, lat }
    }
    await apiJson(
      `/api/admin/users/${Number(m.id)}/addresses/${Number(ed.id)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
      { auth: true },
    )
    showToast('地址已保存', 'success')
    const list = await apiJson(`/api/admin/users/${Number(m.id)}/addresses`, {}, { auth: true })
    addrList.value = Array.isArray(list) ? list : []
    const updated = addrList.value.find((x) => Number(x.id) === Number(ed.id))
    if (updated) pickAddrEdit(updated)
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
    addrSaving.value = false
  }
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
        <div
          v-if="adminAccessToken"
          class="members-header-stats members-header-stats--inline"
          aria-live="polite"
        >
          <template v-if="membersStats.total !== null">
            当前总会员：<strong>{{ membersStats.total }}</strong> 个，生效中
            <strong>{{ membersStats.active }}</strong> 个，已过期
            <strong>{{ membersStats.expired }}</strong> 个
          </template>
          <span v-else-if="membersStatsLoading" class="members-header-stats--muted">统计加载中…</span>
          <span v-else class="members-header-stats--muted">统计暂不可用</span>
        </div>
        <div class="members-query-row">
          <div class="search-box search-box--members-inline">
            <Search :size="18" />
            <input v-model="searchQuery" placeholder="搜索姓名、电话或片区地址..." />
          </div>
          <div class="members-filter-toolbar">
            <div class="members-validity-tabs" role="tablist" aria-label="会员有效期">
              <button
                type="button"
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'all' }"
                :aria-selected="membersValidityTab === 'all'"
                @click="membersValidityTab = 'all'"
              >
                全部
              </button>
              <button
                type="button"
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'active' }"
                :aria-selected="membersValidityTab === 'active'"
                @click="membersValidityTab = 'active'"
              >
                生效中
              </button>
              <button
                type="button"
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersValidityTab === 'expired' }"
                :aria-selected="membersValidityTab === 'expired'"
                @click="membersValidityTab = 'expired'"
              >
                已过期
              </button>
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
              <button
                type="button"
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersInactiveOnly }"
                :aria-selected="membersInactiveOnly"
                @click="toggleInactiveOnly"
              >
                未开卡
              </button>
              <button
                type="button"
                role="tab"
                class="members-validity-tab"
                :class="{ 'members-validity-tab--active': membersOnLeaveOnly }"
                :aria-selected="membersOnLeaveOnly"
                @click="toggleOnLeaveOnly"
              >
                请假中
              </button>
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
        <el-table-column label="会员信息" min-width="128">
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
        <el-table-column label="会员级别" align="center" min-width="88">
          <template #default="{ row: u }">
            <span class="t-plan" :class="planTagClass(u.plan)">{{ u.plan }}</span>
          </template>
        </el-table-column>
        <el-table-column label="配送地址" min-width="300" show-overflow-tooltip>
          <template #default="{ row: u }">
            {{ memberAddressDetailWithoutArea(u) || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="请假时间" min-width="92" width="102" class-name="td-col-leave">
          <template #default="{ row: u }">
            <div v-if="!u.leave_kind" class="leave-cell leave-cell--empty">—</div>
            <div v-else class="leave-cell" :title="u.leave_detail || ''">
              <span class="leave-badge" :class="'leave-badge--' + u.leave_kind">{{ u.leave_badge }}</span>
              <div class="leave-detail">{{ u.leave_detail }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="剩余 / 总次数" align="center" min-width="108">
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
        <el-table-column label="状态" min-width="88">
          <template #default="{ row: u }">
            <span :class="memberStatusClass(u.status)">{{ u.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="备注" min-width="100" class-name="td-remarks">
          <template #default="{ row: u }">
            {{ u.remarks || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" align="right" min-width="268" width="278" fixed="right">
          <template #default="{ row: u }">
            <div class="members-row-actions">
              <button type="button" class="btn-sm secondary btn-members-op" title="地址管理：地图选点，地点与门牌分别保存"
                @click="openMemberAddresses(u)">
                <MapPin :size="12" aria-hidden="true" />
                地址
              </button>
              <button type="button" class="btn-sm secondary btn-members-op" title="手工请假" @click="openLeaveMember(u)">
                请假
              </button>
              <button
                type="button"
                class="btn-sm secondary btn-members-op"
                title="修改会员信息"
                @click="openEditMember(u)"
              >
                修改
              </button>
              <button
                type="button"
                class="btn-sm danger btn-members-op"
                :disabled="memberDeletingId === u.id"
                title="删除会员"
                @click="deleteMemberRow(u)"
              >
                <Trash2 :size="12" aria-hidden="true" />
                删除
              </button>
            </div>
          </template>
        </el-table-column>
      </AdminTable>
      <div v-if="adminAccessToken" class="members-pagination">
        <button type="button" class="btn-sm" :disabled="membersPage <= 1" @click="goMembersPrev">
          上一页
        </button>
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
          <button type="button" class="close-btn" @click="showLeaveModal = false">
            <X :size="20" />
          </button>
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
          <button type="submit" class="btn-submit-order" :disabled="leaveSaving">
            {{ leaveSaving ? '提交中…' : '确认' }}
          </button>
        </form>
      </div>
    </div>

    <MemberEditModal v-model:open="showEditModal" :member="editTargetMember" :region-options="regionFilterOptions"
      @saved="onMemberEditSaved" />

    <div v-if="showAddrModal" class="modal-overlay" v-esc-close="() => (showAddrModal = false)"
      @click.self="showAddrModal = false">
      <div class="modal-card modal-card--member-edit members-addr-modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>地址管理</h3>
            <p>MEMBER ADDRESSES</p>
          </div>
          <button type="button" class="close-btn" @click="showAddrModal = false">
            <X :size="20" />
          </button>
        </div>
        <div class="modal-form members-addr-modal-body">
          <div v-if="addrLoading">
            <el-skeleton animated :rows="5" />
          </div>
          <template v-else-if="addrList.length === 0">
            <el-empty description="该会员暂无配送地址记录。" :image-size="80" />
          </template>
          <template v-else>
            <el-select v-if="addrList.length > 1" v-model="addrSelectedId" class="members-addr-switch"
              placeholder="切换配送地址" filterable size="small" @change="onAddrSelectChange">
              <el-option v-for="a in addrList" :key="a.id" :label="addrOptionLabel(a)" :value="Number(a.id)" />
            </el-select>

            <div v-if="addrMember && addrEdit" class="members-addr-first-row">
              <el-space wrap :size="8" alignment="center">
                <span class="members-addr-k">会员</span>
                <el-text truncated class="members-addr-name">{{ addrMember.name || '—' }}</el-text>
                <el-text type="info" truncated>{{ addrMember.phone || '' }}</el-text>
                <el-divider direction="vertical" class="members-addr-divider" />
                <span class="members-addr-k">经纬度</span>
                <el-tag size="small" type="info" effect="plain" class="members-addr-coord-tag">{{
                  addrHeadCoordDisplay
                }}</el-tag>
                <el-divider direction="vertical" class="members-addr-divider" />
                <span class="members-addr-k">省市区</span>
                <el-text size="small" class="members-addr-pca-line" truncated>{{ addrHeadPcaDisplay }}</el-text>
              </el-space>
            </div>

            <el-form v-if="addrEdit" label-position="top" size="small" class="members-addr-el-form"
              @submit.prevent="saveMemberAddress">
              <el-row :gutter="12">
                <el-col :xs="24" :sm="12">
                  <el-form-item label="收件人">
                    <el-input v-model="addrEdit.contact_name" maxlength="100" clearable placeholder="收件人姓名" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="12">
                  <el-form-item label="联系电话">
                    <el-input v-model="addrEdit.contact_phone" maxlength="20" clearable placeholder="手机号" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="地图选点（GCJ-02）" class="members-addr-map-form-item">

                <div class="members-addr-map-wrap">
                  <MemberDeliveryMapPicker :key="'ma-' + addrEdit.id" v-model:lng-str="addrEdit.lngStr"
                    v-model:lat-str="addrEdit.latStr" v-model:map-location-text="addrEdit.map_location_text"
                    :search-input-id="'members-addr-amap-' + addrEdit.id" @warn="onAddrMapWarn" />
                </div>
              </el-form-item>

              <el-row :gutter="12">
                <el-col :xs="24" :sm="14">
                  <el-form-item label="地点信息（小区 / 道路 / POI）">
                    <el-input v-model="addrEdit.map_location_text" type="textarea"
                      :autosize="{ minRows: 2, maxRows: 4 }" maxlength="500" show-word-limit
                      placeholder="不含门牌；可与地图文案同步" />
                  </el-form-item>
                </el-col>
                <el-col :xs="24" :sm="10">
                  <el-form-item label="门牌（楼栋 / 单元 / 室号）">
                    <el-input v-model="addrEdit.door_detail" type="textarea" :autosize="{ minRows: 2, maxRows: 3 }"
                      maxlength="500" placeholder="例如：3 号楼 1202" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-form-item label="地址备注">
                <el-input v-model="addrEdit.remarks" type="textarea" :autosize="{ minRows: 1, maxRows: 3 }"
                  maxlength="500" placeholder="忌口等，可留空" />
              </el-form-item>

              <el-form-item class="members-addr-actions">
                <el-button type="primary" :loading="addrSaving" native-type="submit">保存地址</el-button>
              </el-form-item>
            </el-form>
          </template>
        </div>
      </div>
    </div>

  </section>
</template>

<style scoped>
.members-addr-modal-card {
  max-width: min(620px, 96vw);
}

.members-addr-modal-body {
  padding: 1rem 1.25rem 1.35rem;
  max-height: min(82vh, 680px);
  overflow: auto;
}

.members-addr-switch {
  width: 100%;
  margin-bottom: 10px;
}

.members-addr-first-row {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.members-addr-k {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.members-addr-name {
  max-width: 7rem;
}

.members-addr-divider {
  margin: 0 2px !important;
  height: 14px !important;
}

.members-addr-coord-tag {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.members-addr-pca-line {
  max-width: min(200px, 36vw);
  vertical-align: middle;
}

.members-addr-el-form {
  margin-top: 2px;
}

.members-addr-el-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.members-addr-map-form-item :deep(.el-form-item__content) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.members-addr-tip {
  padding: 6px 10px;
}

.members-addr-tip :deep(.el-alert__title) {
  font-size: 12px;
  line-height: 1.45;
}

.members-addr-tip-text {
  font-size: 12px;
}

.members-addr-map-wrap {
  width: 100%;
}

.members-addr-map-wrap :deep(.mdmp-map) {
  height: min(188px, 30vh);
  min-height: 150px;
}

.members-addr-actions {
  margin-bottom: 0 !important;
}

.members-addr-actions :deep(.el-form-item__content) {
  justify-content: flex-end;
}
</style>
