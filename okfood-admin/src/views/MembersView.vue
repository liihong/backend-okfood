<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { Search, Phone, X } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const membersPage = ref(1)
const membersPageSize = ref(20)
const membersTotal = ref(0)
const membersLoading = ref(false)
const searchQuery = ref('')
const membersValidityTab = ref('active')
/** 片区：'' | 'unassigned' | 区域 id 字符串 */
const membersRegionFilter = ref('')
/** 仅未开卡 is_active=false */
const membersInactiveOnly = ref(false)
const regionFilterOptions = ref([])

const membersTotalPages = computed(() =>
  Math.max(1, Math.ceil(membersTotal.value / membersPageSize.value)),
)

function validityQuery() {
  return membersValidityTab.value === 'expired' ? 'expired' : 'active'
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

async function fetchMembers() {
  if (!adminAccessToken.value) return
  membersLoading.value = true
  try {
    const params = new URLSearchParams({
      page: String(membersPage.value),
      page_size: String(membersPageSize.value),
      validity: validityQuery(),
    })
    const q = searchQuery.value.trim()
    if (q) params.set('q', q)
    if (membersInactiveOnly.value) params.set('inactive_only', 'true')
    if (membersRegionFilter.value === 'unassigned') params.set('unassigned_region', 'true')
    else if (membersRegionFilter.value) params.set('delivery_region_id', membersRegionFilter.value)
    const data = await apiJson(`/api/admin/users?${params.toString()}`, {}, { auth: true })
    memberList.value = (data.items || []).map(mapAdminUserToRow)
    membersTotal.value = Number(data.total) || 0
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

watch(membersRegionFilter, () => {
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
const leaveRangeStart = ref('')
const leaveRangeEnd = ref('')

function openLeaveMember(u) {
  leaveTarget.value = u
  leaveMode.value = 'tomorrow'
  leaveRangeStart.value = ''
  leaveRangeEnd.value = ''
  showLeaveModal.value = true
}

async function submitLeaveMember() {
  const u = leaveTarget.value
  if (!u || !u.phone) return
  if (leaveMode.value === 'range') {
    if (!leaveRangeStart.value || !leaveRangeEnd.value) {
      showToast('区间请假请填写开始与结束日期', 'error')
      return
    }
  }
  leaveSaving.value = true
  try {
    const payload = { phone: u.phone, type: leaveMode.value }
    if (leaveMode.value === 'range') {
      payload.start = leaveRangeStart.value
      payload.end = leaveRangeEnd.value
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

/** --- 修改会员 --- */
const showEditModal = ref(false)
const editSaving = ref(false)
/** 弹窗内只读展示的当前片区（接口解析名） */
const editAreaDisplay = ref('—')
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
})

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
  const ad = typeof u.area === 'string' && u.area.trim() ? u.area.trim() : '未分配'
  editAreaDisplay.value = ad === '—' ? '未分配' : ad
  const p0 = u.plan && u.plan !== '—' ? u.plan : '次卡'
  editInitialPlanType.value = p0
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    address: defaultAddressDetailForEdit(u),
    remarks: u.remarks || '',
    daily_meal_units: Math.max(1, Math.min(50, Number(u.daily_meal_units) || 1)),
    plan_type: p0,
    use_auto_area: false,
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
      address: editForm.value.address.trim(),
      daily_meal_units: Math.max(1, Math.min(50, Number(editForm.value.daily_meal_units) || 1)),
    }
    if (editForm.value.use_auto_area) {
      payload.use_auto_area = true
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

onMounted(() => {
  void loadRegionFilterOptions()
  void fetchMembers()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header table-header--members">
        <div class="search-box">
          <Search :size="18" />
          <input v-model="searchQuery" placeholder="搜索姓名、电话或片区地址..." />
        </div>
        <p class="members-recharge-hint">
          续卡与加次数请至侧栏「开卡工单」办理：工单标记已缴后使用「同步入账」；次数流水会写入余额日志并附带工单说明。
        </p>
        <div class="members-filter-toolbar">
          <div class="members-validity-tabs" role="tablist" aria-label="会员有效期">
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
            <label class="members-filter-label" for="members-region-filter">片区</label>
            <select
              id="members-region-filter"
              v-model="membersRegionFilter"
              class="members-region-select"
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
      <p v-if="membersLoading" class="members-loading">加载会员列表中…</p>
      <table class="data-table data-table--members">
        <thead>
          <tr>
            <th>会员信息</th>
            <th>电话</th>
            <th>配送片区</th>
            <th class="text-center">剩余 / 总次数</th>
            <th>状态</th>
            <th>备注</th>
            <th class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in memberList" :key="u.id">
            <td>
              <div class="t-name">
                {{ u.name }}
                <span class="t-plan" :class="planTagClass(u.plan)">{{ u.plan }}</span>
              </div>
              <div v-if="u.wechat_name" class="t-sub t-wechat">微信 {{ u.wechat_name }}</div>
            </td>
            <td class="td-phone">
              <div class="member-phone-cell">
                <Phone :size="12" class="member-phone-icon" />
                <span class="member-phone-num">{{ u.phone || '—' }}</span>
              </div>
            </td>
            <td>
              <span class="area-tag">{{ u.area }}</span>
            </td>
            <td class="text-center">
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
            </td>
            <td>
              <span :class="memberStatusClass(u.status)">{{ u.status }}</span>
            </td>
            <td class="td-remarks">{{ u.remarks || '—' }}</td>
            <td class="text-right">
              <div class="members-row-actions">
                <button type="button" class="btn-sm secondary" @click="openLeaveMember(u)">
                  请假
                </button>
                <button type="button" class="btn-sm secondary" @click="openEditMember(u)">
                  修改会员信息
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
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

    <div v-if="showLeaveModal" class="modal-overlay" @click.self="showLeaveModal = false">
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
              <option value="range">区间请假（多天）</option>
              <option value="clear_tomorrow">仅取消「明日请假」</option>
              <option value="cancel">清空全部请假（明日 + 区间）</option>
            </select>
            <p class="modal-hint">后台代操作不校验当日请假截止时间；日期均为上海业务日。</p>
          </div>
          <div v-if="leaveMode === 'range'" class="form-group leave-range-row">
            <div>
              <label>开始日期</label>
              <input v-model="leaveRangeStart" type="date" required />
            </div>
            <div>
              <label>结束日期</label>
              <input v-model="leaveRangeEnd" type="date" required />
            </div>
          </div>
          <button type="submit" class="btn-submit-order" :disabled="leaveSaving">
            {{ leaveSaving ? '提交中…' : '确认' }}
          </button>
        </form>
      </div>
    </div>

    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>修改会员信息</h3>
            <p>EDIT MEMBER PROFILE</p>
          </div>
          <button type="button" class="close-btn" @click="showEditModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="submitEditMember">
          <div class="form-group">
            <label>手机号</label>
            <input :value="editForm.phone" type="text" disabled class="input-disabled" />
          </div>
          <div class="form-group">
            <label>姓名</label>
            <input v-model="editForm.name" required maxlength="100" />
          </div>
          <div class="form-group">
            <label>默认配送地址</label>
            <textarea v-model="editForm.address" required rows="3" maxlength="500"></textarea>
          </div>
          <div class="form-group">
            <label>配送片区（只读）</label>
            <p class="modal-hint modal-hint--tight" style="margin: 0 0 8px; font-weight: 600">
              {{ editAreaDisplay }}
            </p>
            <label class="checkbox-row">
              <input v-model="editForm.use_auto_area" type="checkbox" />
              <span>保存时按地址/坐标重新自动划区</span>
            </label>
            <p class="modal-hint">片区由坐标匹配「配送区域」多边形生成，后台不可手写或下拉指定。</p>
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
            <textarea v-model="editForm.remarks" rows="2" maxlength="500" placeholder="可留空"></textarea>
          </div>
          <button type="submit" class="btn-submit-order" :disabled="editSaving">
            {{ editSaving ? '保存中…' : '保存' }}
          </button>
        </form>
      </div>
    </div>

  </section>
</template>
