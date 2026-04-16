<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { ClipboardList, Phone, Plus, Search, X } from 'lucide-vue-next'
import {
  apiJson,
  adminAccessToken,
  handleAdminLogout,
  planDefaultTotal,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchQuery = ref('')
const payFilter = ref('')

function todayInputDate() {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function payStatusClass(s) {
  if (s === '已缴') return 'member-pill member-pill--emerald'
  return 'member-pill member-pill--amber'
}

function planTagClass(kind) {
  if (kind === '周卡') return 't-plan--week'
  if (kind === '月卡') return 't-plan--month'
  return 't-plan--count'
}

async function fetchList() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const params = new URLSearchParams({
      page: String(page.value),
      page_size: String(pageSize.value),
    })
    const q = searchQuery.value.trim()
    if (q) params.set('q', q)
    const pf = payFilter.value.trim()
    if (pf === '未缴' || pf === '已缴') params.set('pay_status', pf)
    const data = await apiJson(`/api/admin/card-orders?${params.toString()}`, {}, { auth: true })
    list.value = Array.isArray(data.items) ? data.items : []
    total.value = Number(data.total) || 0
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

const goPrev = () => {
  if (page.value <= 1) return
  page.value -= 1
  void fetchList()
}

const goNext = () => {
  if (page.value >= totalPages.value) return
  page.value += 1
  void fetchList()
}

/** --- 新建工单 --- */
const showCreateModal = ref(false)
const createSubmitting = ref(false)
const createForm = ref({
  phone: '',
  delivery_start_date: todayInputDate(),
  card_kind: '周卡',
  pay_channel: '微信',
  pay_status: '未缴',
  amount_yuan: '',
  remark: '',
  sync_member: false,
})

function openCreateModal() {
  createForm.value = {
    phone: '',
    delivery_start_date: todayInputDate(),
    card_kind: '周卡',
    pay_channel: '微信',
    pay_status: '未缴',
    amount_yuan: '',
    remark: '',
    sync_member: false,
  }
  showCreateModal.value = true
}

async function submitCreate() {
  const phone = (createForm.value.phone || '').trim()
  if (!phone) {
    showToast('请填写会员手机号', 'error')
    return
  }
  const startD = (createForm.value.delivery_start_date || '').trim()
  if (!startD) {
    showToast('请选择开始配送日期', 'error')
    return
  }
  createSubmitting.value = true
  try {
    const body = {
      phone,
      delivery_start_date: startD,
      card_kind: createForm.value.card_kind,
      pay_channel: createForm.value.pay_channel,
      pay_status: createForm.value.pay_status,
      sync_member: !!createForm.value.sync_member,
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
  card_kind: '',
  delivery_start_date: '',
  pay_channel: '微信',
  pay_status: '未缴',
  amount_yuan: '',
  remark: '',
  applied_to_member: false,
  sync_member: false,
})

function openEditModal(row) {
  const ds = row.delivery_start_date ? String(row.delivery_start_date).slice(0, 10) : ''
  editForm.value = {
    id: row.id,
    member_phone: row.member_phone || '',
    member_name: row.member_name || '',
    card_kind: row.card_kind || '',
    delivery_start_date: ds || todayInputDate(),
    pay_channel: row.pay_channel || '微信',
    pay_status: row.pay_status || '未缴',
    amount_yuan: row.amount_yuan != null && row.amount_yuan !== '' ? String(row.amount_yuan) : '',
    remark: row.remark || '',
    applied_to_member: !!row.applied_to_member,
    sync_member: false,
  }
  showEditModal.value = true
}

async function submitEdit() {
  if (!editForm.value.id) return
  editSubmitting.value = true
  try {
    const body = {
      delivery_start_date: (editForm.value.delivery_start_date || '').trim() || null,
      pay_channel: editForm.value.pay_channel,
      pay_status: editForm.value.pay_status,
      sync_member: !!editForm.value.sync_member,
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
    showToast('工单已更新')
    showEditModal.value = false
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    editSubmitting.value = false
  }
}

onMounted(() => {
  void fetchList()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header table-header--members table-header--couriers-row">
        <div class="search-box search-box--flex">
          <Search :size="18" />
          <input v-model="searchQuery" placeholder="搜索会员手机或姓名…" />
        </div>
        <div class="card-orders-filters">
          <label class="card-orders-filter-label">
            缴费
            <select v-model="payFilter" class="card-orders-select">
              <option value="">全部</option>
              <option value="未缴">未缴</option>
              <option value="已缴">已缴</option>
            </select>
          </label>
          <button type="button" class="btn-primary btn-primary--sm" @click="openCreateModal">
            <Plus :size="18" /> 新建开卡工单
          </button>
        </div>
      </div>
      <p class="card-orders-intro">
        <ClipboardList :size="16" class="card-orders-intro-icon" />
        必选「开始配送日」（上海业务日）：该日及之后才进入配送大表与配送员派单；此前即使有余额也不会出现。
        勾选「同步入账」且在「已缴」时，将写入次数、套餐类型、激活计划并写入该起送日。
      </p>
      <p v-if="loading" class="members-loading">加载工单中…</p>
      <table v-else class="data-table data-table--members">
        <thead>
          <tr>
            <th>单号</th>
            <th>会员</th>
            <th>卡类型</th>
            <th>起送日</th>
            <th>缴费渠道</th>
            <th>缴费状态</th>
            <th class="text-right">实收(元)</th>
            <th>入账</th>
            <th>备注</th>
            <th>创建人 / 时间</th>
            <th class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!list.length">
            <td colspan="11" class="members-loading">暂无工单</td>
          </tr>
          <tr v-for="row in list" :key="row.id">
            <td class="td-mono">#{{ row.id }}</td>
            <td>
              <div class="t-name">
                {{ row.member_name || '—' }}
                <span class="t-plan" :class="planTagClass(row.card_kind)">{{ row.card_kind }}</span>
              </div>
              <div class="member-phone-cell t-sub">
                <Phone :size="12" class="member-phone-icon" />
                <span class="member-phone-num">{{ row.member_phone }}</span>
              </div>
            </td>
            <td>{{ row.card_kind }}</td>
            <td class="td-mono">{{ row.delivery_start_date || '—' }}</td>
            <td>{{ row.pay_channel }}</td>
            <td>
              <span :class="payStatusClass(row.pay_status)">{{ row.pay_status }}</span>
            </td>
            <td class="text-right font-black">
              {{ row.amount_yuan != null && row.amount_yuan !== '' ? row.amount_yuan : '—' }}
            </td>
            <td>
              <span
                class="member-pill"
                :class="row.applied_to_member ? 'member-pill--emerald' : 'member-pill--slate'"
              >
                {{ row.applied_to_member ? '已同步' : '未同步' }}
              </span>
            </td>
            <td class="td-remarks">{{ row.remark || '—' }}</td>
            <td class="t-sub">
              <div>{{ row.created_by }}</div>
              <div>{{ row.created_at }}</div>
            </td>
            <td class="text-right">
              <button type="button" class="btn-sm" @click="openEditModal(row)">更新</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-if="adminAccessToken" class="members-pagination">
        <button type="button" class="btn-sm" :disabled="page <= 1" @click="goPrev">上一页</button>
        <span class="members-page-meta">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
        <button type="button" class="btn-sm" :disabled="page >= totalPages" @click="goNext">
          下一页
        </button>
      </div>
    </div>

    <div v-if="showCreateModal" class="modal-overlay" @click.self="showCreateModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>新建开卡工单</h3>
            <p>MEMBER CARD ORDER</p>
          </div>
          <button type="button" class="close-btn" @click="showCreateModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="submitCreate">
          <div class="form-group">
            <label>会员手机号</label>
            <input v-model="createForm.phone" required maxlength="20" placeholder="已注册会员的手机号" />
          </div>
          <div class="form-group">
            <label>开始配送日（业务日）</label>
            <input v-model="createForm.delivery_start_date" type="date" required />
            <p class="modal-hint">该日起参与配送大表；当日及之后日期可查见、可派单。</p>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>卡类型</label>
              <select v-model="createForm.card_kind">
                <option value="周卡">周卡（默认 +{{ planDefaultTotal('周卡') }} 次）</option>
                <option value="月卡">月卡（默认 +{{ planDefaultTotal('月卡') }} 次）</option>
              </select>
            </div>
            <div class="form-group">
              <label>缴费渠道</label>
              <select v-model="createForm.pay_channel">
                <option value="微信">微信</option>
                <option value="支付宝">支付宝</option>
              </select>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>缴费状态</label>
              <select v-model="createForm.pay_status">
                <option value="未缴">未缴</option>
                <option value="已缴">已缴</option>
              </select>
            </div>
            <div class="form-group">
              <label>实收金额(元，可选)</label>
              <input v-model="createForm.amount_yuan" type="number" min="0" step="0.01" placeholder="留空表示未填" />
            </div>
          </div>
          <div class="form-group">
            <label>备注</label>
            <textarea v-model="createForm.remark" rows="2" maxlength="500" placeholder="可选"></textarea>
          </div>
          <label class="checkbox-row">
            <input v-model="createForm.sync_member" type="checkbox" />
            <span>若状态为「已缴」，立即同步次数与套餐、激活计划并写入起送日</span>
          </label>
          <button type="submit" class="btn-submit-order" :disabled="createSubmitting">
            {{ createSubmitting ? '提交中…' : '创建工单' }}
          </button>
        </form>
      </div>
    </div>

    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
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
        <form class="modal-form" @submit.prevent="submitEdit">
          <div class="form-group">
            <label>会员</label>
            <input
              :value="`${editForm.member_name || '—'}（${editForm.member_phone}）· ${editForm.card_kind}`"
              type="text"
              disabled
              class="input-disabled"
            />
          </div>
          <div class="form-group">
            <label>开始配送日</label>
            <input v-model="editForm.delivery_start_date" type="date" required />
            <p v-if="editForm.applied_to_member" class="modal-hint">已同步的工单修改起送日会同步更新会员档案。</p>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>缴费渠道</label>
              <select v-model="editForm.pay_channel">
                <option value="微信">微信</option>
                <option value="支付宝">支付宝</option>
              </select>
            </div>
            <div class="form-group">
              <label>缴费状态</label>
              <select v-model="editForm.pay_status" :disabled="editForm.applied_to_member">
                <option value="未缴">未缴</option>
                <option value="已缴">已缴</option>
              </select>
            </div>
          </div>
          <p v-if="editForm.applied_to_member" class="modal-hint">已入账的工单不可改回「未缴」。</p>
          <div class="form-group">
            <label>实收金额(元，可选)</label>
            <input v-model="editForm.amount_yuan" type="number" min="0" step="0.01" placeholder="留空可清空金额" />
          </div>
          <div class="form-group">
            <label>备注</label>
            <textarea v-model="editForm.remark" rows="2" maxlength="500"></textarea>
          </div>
          <label class="checkbox-row">
            <input v-model="editForm.sync_member" type="checkbox" :disabled="editForm.applied_to_member" />
            <span>同步次数与起送规则（已缴且尚未同步时有效；与续卡次数规则一致）</span>
          </label>
          <button type="submit" class="btn-submit-order" :disabled="editSubmitting">
            {{ editSubmitting ? '保存中…' : '保存' }}
          </button>
        </form>
      </div>
    </div>
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
</style>
