<script setup>
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { Search, Phone, X } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

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

function openLeaveMember(u) {
  leaveTarget.value = u
  leaveMode.value = 'tomorrow'
  showLeaveModal.value = true
}

async function submitLeaveMember() {
  const u = leaveTarget.value
  if (!u || !u.phone) return
  leaveSaving.value = true
  try {
    const payload = { phone: u.phone, type: leaveMode.value }
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

/** --- 修改会员 --- */
const showEditModal = ref(false)
const editSaving = ref(false)
/** 打开编辑弹窗时的套餐类型，用于判断是否与档案一致、是否提交 plan_type */
const editInitialPlanType = ref('次卡')
const editForm = ref({
  phone: '',
  name: '',
  address: '',
  remarks: '',
  /** 每配送日份数（多张周卡等） */
  daily_meal_units: 1,
  /** 档案套餐标签：与列表「周卡/月卡」角标一致；仅改展示与统计口径，不自动改余额 */
  plan_type: '次卡',
  use_auto_area: false,
  /** 会员剩余订餐次数（管理端直接改数，差值记入 balance_logs） */
  balance: 0,
  /** 起送业务日 YYYY-MM-DD，空表示未设置 */
  delivery_start_date: '',
  /** 门店自提 */
  store_pickup: false,
  /** 会员卡停用(暂停配送/先不开卡)，同 members.delivery_deferred；勾选后不参与排期与分拣 */
  delivery_deferred: false,
  /** 配送片区：'' 表示未分配，否则为区域 id 字符串（与下拉 value 一致） */
  delivery_region_id: '',
})

watch(
  () => editForm.value.delivery_deferred,
  (v) => {
    if (v) editForm.value.store_pickup = false
  },
)

/** 编辑框仅填详细地址：优先 API 的 detail_address，否则从旧版「片区 + 详细」展示串回推 */
function defaultAddressDetailForEdit(u) {
  let detail = typeof u.detail_address === 'string' ? u.detail_address.trim() : ''
  if (detail) return detail
  const rawAddr = String(u.address || '').trim()
  if (!rawAddr || rawAddr.startsWith('（未设置')) return ''
  const areaTag = String(u.area || '').trim()
  if (areaTag && areaTag !== '—' && rawAddr.startsWith(areaTag)) {
    return rawAddr.slice(areaTag.length).trim()
  }
  return rawAddr
}

async function openEditMember(u) {
  const p0 = u.plan && u.plan !== '—' ? u.plan : '次卡'
  editInitialPlanType.value = p0
  const dr =
    u.delivery_region_id != null && u.delivery_region_id !== ''
      ? String(u.delivery_region_id)
      : ''
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    address: defaultAddressDetailForEdit(u),
    remarks: u.remarks || '',
    daily_meal_units: Math.max(1, Math.min(50, Number(u.daily_meal_units) || 1)),
    plan_type: p0,
    use_auto_area: false,
    balance: Math.max(0, Math.min(999999, Math.floor(Number(u.balance) || 0))),
    delivery_start_date:
      typeof u.delivery_start_date === 'string' && u.delivery_start_date.trim()
        ? u.delivery_start_date.trim().slice(0, 10)
        : '',
    store_pickup: u.store_pickup === true,
    delivery_deferred: u.delivery_deferred === true,
    delivery_region_id: dr,
  }
  showEditModal.value = true
}

async function submitEditMember() {
  if (!editForm.value.phone) return
  editSaving.value = true
  try {
    const payload = {
      phone: editForm.value.phone,
      name: editForm.value.name.trim(),
      remarks: editForm.value.remarks.trim() || null,
      address: editForm.value.address.trim() || null,
      daily_meal_units: Math.max(1, Math.min(50, Number(editForm.value.daily_meal_units) || 1)),
      balance: Math.max(0, Math.min(999999, Math.floor(Number(editForm.value.balance) || 0))),
      delivery_start_date: editForm.value.delivery_start_date?.trim()
        ? editForm.value.delivery_start_date.trim().slice(0, 10)
        : null,
      store_pickup: editForm.value.store_pickup === true,
      delivery_deferred: editForm.value.delivery_deferred === true,
    }
    if (editForm.value.use_auto_area) {
      payload.use_auto_area = true
    } else {
      const dr = editForm.value.delivery_region_id
      payload.delivery_region_id = dr === '' || dr == null ? null : Number(dr)
    }
    const pt = String(editForm.value.plan_type || '次卡').trim() || '次卡'
    if (pt !== editInitialPlanType.value) {
      payload.plan_type = pt
    }
    await apiJson(
      '/api/admin/member/profile',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      { auth: true },
    )
    showEditModal.value = false
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
    editSaving.value = false
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
            <div class="members-extra-filters" aria-label="片区与开卡筛选">
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
            </div>
          </div>
        </div>
      </div>
      <AdminTable
        variant="members"
        :data="membersRows"
        :loading="membersLoading"
        :row-key="memberRowKey"
        empty-text="暂无会员数据"
      >
        <el-table-column label="会员信息" min-width="160">
          <template #default="{ row: u }">
            <div class="t-name">
              {{ u.name }}
              <span class="t-plan" :class="planTagClass(u.plan)">{{ u.plan }}</span>
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
        <el-table-column label="配送片区" min-width="100">
          <template #default="{ row: u }">
            <span class="area-tag">{{ u.area }}</span>
          </template>
        </el-table-column>
        <el-table-column label="开始配送时间" min-width="120" align="center" class-name="td-delivery-start">
          <template #default="{ row: u }">
            {{ u.delivery_start_date || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="自提" align="center" min-width="72">
          <template #default="{ row: u }">
            <span :class="u.store_pickup ? 'pickup-tag pickup-tag--on' : 'pickup-tag'">{{
              u.store_pickup ? '是' : '否'
            }}</span>
          </template>
        </el-table-column>
        <el-table-column label="剩余 / 总次数" align="center" min-width="120">
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
        <el-table-column label="操作" align="right" min-width="200" fixed="right">
          <template #default="{ row: u }">
            <div class="members-row-actions">
              <button type="button" class="btn-sm secondary" @click="openLeaveMember(u)">
                请假
              </button>
              <button type="button" class="btn-sm secondary" @click="openEditMember(u)">
                修改会员信息
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
              <option value="clear_tomorrow">仅取消「明日请假」</option>
              <option value="cancel">清空全部请假</option>
            </select>
            <p class="modal-hint">后台代操作不校验当日请假截止时间；日期均为上海业务日。</p>
          </div>
          <button type="submit" class="btn-submit-order" :disabled="leaveSaving">
            {{ leaveSaving ? '提交中…' : '确认' }}
          </button>
        </form>
      </div>
    </div>

    <div
      v-if="showEditModal"
      class="modal-overlay"
      v-esc-close="() => (showEditModal = false)"
      @click.self="showEditModal = false"
    >
      <div class="modal-card modal-card--member-edit">
        <div class="modal-header">
          <div class="header-info">
            <h3>修改会员信息</h3>
            <p>EDIT MEMBER PROFILE</p>
          </div>
          <button type="button" class="close-btn" @click="showEditModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form modal-form--member-two-col" @submit.prevent="submitEditMember">
          <div class="form-group">
            <label>手机号</label>
            <input :value="editForm.phone" type="text" disabled class="input-disabled" />
          </div>
          <div class="form-group">
            <label>姓名</label>
            <input v-model="editForm.name" required maxlength="100" />
          </div>
          <div class="form-group form-group--span-full">
            <label>默认配送地址</label>
            <textarea v-model="editForm.address" required rows="3" maxlength="500"></textarea>
          </div>
          <div class="form-group form-group--span-full">
            <label>配送片区</label>
            <select
              v-model="editForm.delivery_region_id"
              class="input-delivery-area"
              :disabled="editForm.use_auto_area"
            >
              <option value="">未分配</option>
              <option v-for="r in regionFilterOptions" :key="r.id" :value="String(r.id)">
                {{ r.name || '—' }}
              </option>
            </select>
            <label class="checkbox-row">
              <input v-model="editForm.use_auto_area" type="checkbox" />
              <span>保存时按地址/坐标重新自动划区（勾选后忽略下方手动片区）</span>
            </label>
            <p class="modal-hint">
              下拉列表与列表筛选一致（仅启用中的配送区域）。未勾选自动划区时，保存会先按地址地理编码划区，再以您选择的片区覆盖。
            </p>
          </div>
          <div class="form-group form-group--span-full member-delivery-block">
            <label>开始配送日期（起送业务日）</label>
            <div class="member-delivery-controls-row">
              <div class="member-delivery-date-wrap">
                <input v-model="editForm.delivery_start_date" type="date" />
              </div>
              <label class="checkbox-row member-delivery-check">
                <input v-model="editForm.delivery_deferred" type="checkbox" />
                <span>暂停配送（会员卡停用）</span>
              </label>
              <label class="checkbox-row member-delivery-check">
                <input
                  v-model="editForm.store_pickup"
                  type="checkbox"
                  :disabled="editForm.delivery_deferred"
                />
                <span>门店自提（不到家配送，仍计入备餐大表「门店自提」分组）</span>
              </label>
            </div>
            <p class="modal-hint">
              上海业务日：该日及之后才进入配送排期；留空表示未设置起送日。保存时会与「未开卡 / 余额」等规则一并生效；勾选「暂停配送」时保存会清空起送日。
            </p>
            <p class="modal-hint">
              与小程序「暂不配送 / 先不开卡」为同一数据字段。勾选后不参与配送大表/分拣、不计入开卡分货，并会清空起送日、关闭门店自提。取消勾选且有余额时恢复为在册活跃（是否排期仍取决于起送日等条件）。
            </p>
          </div>
          <div class="form-group">
            <label>会员剩余次数</label>
            <input
              v-model.number="editForm.balance"
              type="number"
              min="0"
              max="999999"
              step="1"
              required
            />
            <p class="modal-hint">
              直接修改当前剩余订餐次数；与旧值的差额会写入余额流水（原因：管理端调整）。常规续卡仍建议走「开卡工单」入账。
            </p>
          </div>
          <div class="form-group">
            <label>每配送日份数</label>
            <input
              v-model.number="editForm.daily_meal_units"
              type="number"
              min="1"
              max="50"
              step="1"
              required
            />
            <p class="modal-hint">例如购 2 张周卡、同日需送 2 份时填 2；确认送达将按该倍数扣减剩余次数。</p>
          </div>
          <div class="form-group">
            <label>套餐类型（档案标签）</label>
            <select v-model="editForm.plan_type" class="input-delivery-area">
              <option value="周卡">周卡</option>
              <option value="月卡">月卡</option>
              <option value="次卡">次卡</option>
            </select>
            <p class="modal-hint">
              仅同步列表与小程序展示的套餐角标，不会增减剩余次数；次数增减须通过「开卡工单」同步入账。若续月卡后角标仍为周卡，可在此改为月卡。
            </p>
          </div>
          <div class="form-group">
            <label>备注（忌口等）</label>
            <textarea v-model="editForm.remarks" rows="4" maxlength="500" placeholder="可留空"></textarea>
          </div>
          <button type="submit" class="btn-submit-order" :disabled="editSaving">
            {{ editSaving ? '保存中…' : '保存' }}
          </button>
        </form>
      </div>
    </div>

  </section>
</template>
