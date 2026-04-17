<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import { Search, Phone, X } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  memberList,
  mapAdminUserToRow,
  handleAdminLogout,
  planDefaultTotal,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const membersPage = ref(1)
const membersPageSize = ref(20)
const membersTotal = ref(0)
const membersLoading = ref(false)
const searchQuery = ref('')
const membersValidityTab = ref('active')

const membersTotalPages = computed(() =>
  Math.max(1, Math.ceil(membersTotal.value / membersPageSize.value)),
)

function validityQuery() {
  return membersValidityTab.value === 'expired' ? 'expired' : 'active'
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

/** --- 修改会员 --- */
const showEditModal = ref(false)
const editSaving = ref(false)
const deliveryRegionOptions = ref([])
const initialDeliveryArea = ref('未分配')
const editForm = ref({
  phone: '',
  name: '',
  address: '',
  remarks: '',
  delivery_area: '未分配',
  delivery_area_override: '',
  use_auto_area: false,
})

function normalizeAreaForForm(a) {
  const s = String(a || '').trim()
  if (!s || s === '—') return '未分配'
  return s
}

/** 编辑框仅填详细地址：优先 API 的 detail_address，否则从旧版「片区 + 详细」展示串回推 */
function defaultAddressDetailForEdit(u) {
  let detail = typeof u.detail_address === 'string' ? u.detail_address.trim() : ''
  if (detail) return detail
  const rawAddr = String(u.address || '').trim()
  if (!rawAddr || rawAddr.startsWith('（未设置')) return ''
  const areaTag = normalizeAreaForForm(u.area)
  if (areaTag && areaTag !== '—' && rawAddr.startsWith(areaTag)) {
    return rawAddr.slice(areaTag.length).trim()
  }
  return rawAddr
}

const deliveryAreaSelectOptions = computed(() => {
  const sorted = [...deliveryRegionOptions.value]
    .filter((x) => x && x !== '未分配')
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))
  const cur = normalizeAreaForForm(editForm.value.delivery_area)
  const out = ['未分配', ...sorted]
  if (cur && cur !== '未分配' && !out.includes(cur)) out.push(cur)
  return out
})

async function ensureDeliveryRegions() {
  try {
    const data = await apiJson('/api/admin/delivery-regions', {}, { auth: true })
    const list = Array.isArray(data) ? data : []
    const names = list
      .filter((r) => r && (r.is_active === true || r.is_active === 1))
      .map((r) => r.name)
      .filter((n) => typeof n === 'string' && n.trim())
    deliveryRegionOptions.value = [...new Set(names)].sort((a, b) => a.localeCompare(b, 'zh-CN'))
  } catch {
    deliveryRegionOptions.value = []
  }
}

async function openEditMember(u) {
  await ensureDeliveryRegions()
  const area0 = normalizeAreaForForm(u.area)
  initialDeliveryArea.value = area0
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    address: defaultAddressDetailForEdit(u),
    remarks: u.remarks || '',
    delivery_area: area0,
    delivery_area_override: '',
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
    }
    if (editForm.value.use_auto_area) {
      payload.use_auto_area = true
    } else {
      const eff = normalizeAreaForForm(
        editForm.value.delivery_area_override.trim() || editForm.value.delivery_area,
      )
      if (eff !== initialDeliveryArea.value) {
        payload.delivery_area = eff
      }
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

/** --- 续卡（充值次数） --- */
const showRechargeModal = ref(false)
const rechargeSaving = ref(false)
const rechargeForm = ref({
  phone: '',
  plan: '次卡',
  amount: 1,
})

function defaultRechargeAmount(plan) {
  if (plan === '周卡') return 6
  if (plan === '月卡') return 24
  return 1
}

function openRechargeMember(u) {
  const plan = u.plan || '次卡'
  rechargeForm.value = {
    phone: u.phone,
    plan,
    amount: defaultRechargeAmount(plan),
  }
  showRechargeModal.value = true
}

watch(
  () => rechargeForm.value.plan,
  (p) => {
    rechargeForm.value.amount = defaultRechargeAmount(p)
  },
)

async function submitRecharge() {
  const amt = Number(rechargeForm.value.amount)
  if (!rechargeForm.value.phone || !Number.isFinite(amt) || amt <= 0) {
    alert('请填写有效的续卡次数（正整数）')
    return
  }
  rechargeSaving.value = true
  try {
    await apiJson(
      '/api/admin/recharge',
      {
        method: 'POST',
        body: JSON.stringify({
          phone: rechargeForm.value.phone,
          amount: Math.floor(amt),
          plan_type: rechargeForm.value.plan,
        }),
      },
      { auth: true },
    )
    showRechargeModal.value = false
    await fetchMembers()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '续卡失败', 'error')
  } finally {
    rechargeSaving.value = false
  }
}

onMounted(() => {
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
              <span v-if="u.area_manual" class="area-manual-tag" title="片区为后台手工指定">手工</span>
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
                <button type="button" class="btn-sm secondary" @click="openEditMember(u)">
                  修改会员信息
                </button>
                <button type="button" class="btn-sm" @click="openRechargeMember(u)">续卡</button>
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
            <label>配送片区（与「配送区域」配置联动）</label>
            <select
              v-model="editForm.delivery_area"
              class="input-delivery-area"
              :disabled="editForm.use_auto_area"
            >
              <option v-for="n in deliveryAreaSelectOptions" :key="n" :value="n">{{ n }}</option>
            </select>
            <input
              v-model="editForm.delivery_area_override"
              type="text"
              maxlength="64"
              class="input-delivery-area input-delivery-area--secondary"
              placeholder="自定义片区名（可选，填写则覆盖上方下拉）"
              :disabled="editForm.use_auto_area"
            />
            <label class="checkbox-row">
              <input v-model="editForm.use_auto_area" type="checkbox" />
              <span>保存时按坐标重新自动划区（取消手工锁定）</span>
            </label>
            <p class="modal-hint">
              下拉为数据库中已启用的配送区域；手工指定后，仅改详细地址不会自动改写片区。
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

    <div v-if="showRechargeModal" class="modal-overlay" @click.self="showRechargeModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>续卡 · 增加次数</h3>
            <p>RECHARGE / RENEWAL</p>
          </div>
          <button type="button" class="close-btn" @click="showRechargeModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="submitRecharge">
          <div class="form-group">
            <label>手机号</label>
            <input :value="rechargeForm.phone" type="text" disabled class="input-disabled" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>卡类型</label>
              <select v-model="rechargeForm.plan">
                <option value="次卡">次卡</option>
                <option value="周卡">周卡（默认 +6 次）</option>
                <option value="月卡">月卡（默认 +24 次）</option>
              </select>
            </div>
            <div class="form-group">
              <label>增加次数</label>
              <input
                v-model.number="rechargeForm.amount"
                type="number"
                min="1"
                step="1"
                required
              />
            </div>
          </div>
          <p class="modal-hint">
            当前套餐默认：
            周卡 {{ planDefaultTotal('周卡') }} 次 / 月卡 {{ planDefaultTotal('月卡') }} 次；可自行修改「增加次数」。
          </p>
          <button type="submit" class="btn-submit-order" :disabled="rechargeSaving">
            {{ rechargeSaving ? '提交中…' : '确认续卡' }}
          </button>
        </form>
      </div>
    </div>
  </section>
</template>
