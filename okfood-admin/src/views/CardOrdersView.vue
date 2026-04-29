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
import MemberDeliveryMapPicker from '../components/MemberDeliveryMapPicker.vue'

const list = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchQuery = ref('')
const payFilter = ref('')
/** 默认 false：仅待处理（未缴或已缴未入账）；勾选后查全部历史 */
const includeHistory = ref(false)

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

function truncateText(s, max) {
  const t = (s == null ? '' : String(s)).trim()
  if (!t) return ''
  if (t.length <= max) return t
  return `${t.slice(0, Math.max(0, max - 1))}…`
}

/** 列表格内备注缩略（完整内容用单元格 title 展示） */
function remarkPreview(text) {
  const t = (text == null ? '' : String(text)).trim()
  if (!t) return '—'
  return truncateText(t, 22)
}

/** 创建人 + 时间单行：MM-DD HH:mm */
function cardOrderCreatedLine(row) {
  const who = truncateText(row.created_by, 10)
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

function memberLine2Title(row) {
  const p = (row.member_phone || '').trim()
  const w = (row.member_wechat_name || '').trim()
  if (w) return `${p} · 微信 ${w}`
  return p || ''
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
    if (includeHistory.value) params.set('include_history', 'true')
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

watch(includeHistory, () => {
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
  open_mode: 'new_member',
  phone: '',
  name: '',
  wechat_name: '',
  delivery_start_mode: 'date',
  delivery_start_date: todayInputDate(),
  card_kind: '周卡',
  pay_channel: '微信',
  pay_status: '未缴',
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

/** 续卡同步入账后：剩余、总次数均 +本次卡次数 */
const renewSyncPreview = computed(() => {
  const p = renewPreview.value
  if (!p || createForm.value.open_mode !== 'renew') return null
  const bal = Number(p.balance) || 0
  const add = planDefaultTotal(createForm.value.card_kind)
  if (add == null) return null
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
    if (mode === 'renew') scheduleRenewPreview()
  },
)

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
    card_kind: '周卡',
    pay_channel: '微信',
    pay_status: '未缴',
    amount_yuan: '',
    remark: '',
    delivery_lng: '',
    delivery_lat: '',
    map_location_text: '',
    door_detail: '',
  }
  showCreateModal.value = true
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
  const deferStart = createForm.value.delivery_start_mode === 'defer'
  let startD = null
  if (!deferStart) {
    startD = (createForm.value.delivery_start_date || '').trim()
    if (!startD) {
      showToast('请选择开始配送日期', 'error')
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

  createSubmitting.value = true
  try {
    const body = {
      phone,
      open_mode: openMode,
      delivery_start_date: deferStart ? null : startD,
      card_kind: createForm.value.card_kind,
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
  card_kind: '',
  delivery_start_mode: 'date',
  delivery_start_date: '',
  pay_channel: '微信',
  pay_status: '未缴',
  amount_yuan: '',
  remark: '',
  applied_to_member: false,
})

function openEditModal(row) {
  const ds = row.delivery_start_date ? String(row.delivery_start_date).slice(0, 10) : ''
  editForm.value = {
    id: row.id,
    member_phone: row.member_phone || '',
    member_name: row.member_name || '',
    member_wechat_name: row.member_wechat_name || '',
    card_kind: row.card_kind || '',
    delivery_start_mode: ds ? 'date' : 'defer',
    delivery_start_date: ds || todayInputDate(),
    pay_channel: row.pay_channel || '微信',
    pay_status: row.pay_status || '未缴',
    amount_yuan: row.amount_yuan != null && row.amount_yuan !== '' ? String(row.amount_yuan) : '',
    remark: row.remark || '',
    applied_to_member: !!row.applied_to_member,
  }
  showEditModal.value = true
}

async function submitEdit() {
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
  editSubmitting.value = true
  try {
    const body = {
      delivery_start_date: deferEdit ? null : editStartD,
      pay_channel: editForm.value.pay_channel,
      pay_status: editForm.value.pay_status,
    }
    if (!editForm.value.applied_to_member) {
      body.card_kind = editForm.value.card_kind || '周卡'
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
 <section class="tab-content animate-up card-orders-page">
    <div class="table-container">
      <div class="table-header table-header--members table-header--couriers-row">
        <div class="search-box search-box--flex">
          <Search :size="18" />
          <input v-model="searchQuery" placeholder="搜索手机、姓名或微信昵称…" />
        </div>
        <div class="card-orders-filters">
         <label class="card-orders-filter-label card-orders-filter-label--check">
            <input v-model="includeHistory" type="checkbox" class="card-orders-history-check" />
            查看历史开卡记录
          </label>
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

      <AdminTable
class="card-orders-table"
        variant="members"
size="small"
        :data="list"
        :loading="loading"
        row-key="id"
        empty-text="暂无工单"
      >
       <el-table-column label="单号" width="72" class-name="td-mono td-co-id">
          <template #default="{ row }">#{{ row.id }}</template>
        </el-table-column>
       <el-table-column label="会员" class-name="td-co-member">
          <template #default="{ row }">
           <div class="co-member-compact">
              <div class="co-member-line1">
                <span class="co-member-name" :title="row.member_name || ''">{{
                  row.member_name || '—'
                }}</span>
                <span class="t-plan co-plan-tag" :class="planTagClass(row.card_kind)">{{
                  row.card_kind
                }}</span>
              </div>
             <div class="co-member-line2" :title="memberLine2Title(row)">
                <Phone :size="11" class="member-phone-icon co-phone-icon" />
                <span class="co-phone-num">{{ row.member_phone }}</span>
                <template v-if="row.member_wechat_name">
                  <span class="co-sep">·</span>
                  <span class="co-wx">{{ truncateText(row.member_wechat_name, 6) }}</span>
                </template>
              </div>
           </div>
          </template>
        </el-table-column>
       <el-table-column label="起送日" width="112" class-name="td-mono co-nowrap">
          <template #default="{ row }">{{ row.delivery_start_date || '—' }}</template>
        </el-table-column>
       <el-table-column prop="pay_channel" label="渠道" min-width="24" class-name="co-nowrap" />
        <el-table-column label="状态" min-width="34" class-name="co-nowrap">
          <template #default="{ row }">
            <span :class="payStatusClass(row.pay_status)">{{ row.pay_status }}</span>
          </template>
        </el-table-column>
       <el-table-column label="实收" align="right" width="72" min-width="64" class-name="co-amt">
          <template #default="{ row }">
           <span class="font-black co-amt-num">
              {{ row.amount_yuan != null && row.amount_yuan !== '' ? row.amount_yuan : '—' }}
            </span>
          </template>
        </el-table-column>
       <el-table-column label="入账" width="82" min-width="74" align="center" class-name="co-nowrap">
          <template #default="{ row }">
            <span
class="member-pill co-sync-pill"
              :class="row.applied_to_member ? 'member-pill--emerald' : 'member-pill--slate'"
            >
              {{ row.applied_to_member ? '已同步' : '未同步' }}
            </span>
          </template>
        </el-table-column>
       <el-table-column label="备注" min-width="200" width="152" class-name="td-co-remark">
          <template #default="{ row }">
            <span class="co-remark-text" :title="(row.remark || '').trim() || undefined">{{
              remarkPreview(row.remark)
            }}</span>
          </template>
        </el-table-column>
       <el-table-column label="创建" min-width="150" width="132" class-name="td-co-created">
          <template #default="{ row }">
           <span class="co-created-line" :title="`${row.created_by || ''} ${row.created_at || ''}`">{{
              cardOrderCreatedLine(row)
            }}</span>
          </template>
        </el-table-column>
       <el-table-column label="操作" align="right" width="76" fixed="right" class-name="td-co-actions">
          <template #default="{ row }">
            <button type="button" class="btn-sm" @click="openEditModal(row)">更新</button>
          </template>
        </el-table-column>
      </AdminTable>
      <div v-if="adminAccessToken" class="members-pagination">
        <button type="button" class="btn-sm" :disabled="page <= 1" @click="goPrev">上一页</button>
        <span class="members-page-meta">第 {{ page }} / {{ totalPages }} 页 · 共 {{ total }} 条</span>
        <button type="button" class="btn-sm" :disabled="page >= totalPages" @click="goNext">
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
        <form class="modal-form modal-form--card-order" @submit.prevent="submitCreate">
          <div class="form-group open-mode-group">
            <label>办理类型</label>
            <div class="open-mode-options">
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="createForm.open_mode" type="radio" value="new_member" />
                  <span class="radio-tile-title">新会员开卡</span>
                </span>
                <span class="radio-tile-sub">填写姓名、微信昵称并写入档案</span>
              </label>
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="createForm.open_mode" type="radio" value="renew" />
                  <span class="radio-tile-title">老会员续卡</span>
                </span>
                <span class="radio-tile-sub">仅核对手机号；入账叠加剩余与总次数</span>
              </label>
            </div>
          </div>
          <div class="form-group">
            <label>会员手机号</label>
            <input
              v-model="createForm.phone"
              required
              maxlength="20"
              placeholder="已注册会员的手机号"
              @input="onCreatePhoneInput"
            />
          </div>
          <div v-if="createForm.open_mode === 'renew'" class="renew-preview-box">
            <p v-if="renewPreviewLoading" class="modal-hint">正在查询该手机号会员…</p>
            <template v-else-if="renewPreview">
              <p class="modal-hint">
已匹配：<strong>{{ renewPreview.name || '—' }}</strong>
                · 套餐 {{ renewPreview.plan_type || '—' }}
                · 当前剩余 <strong>{{ Number(renewPreview.balance) || 0 }}</strong>
                次
              </p>
              <p v-if="renewSyncPreview" class="modal-hint modal-hint--accent">
                同步入账后约：<strong>剩余 {{ renewSyncPreview.nextBal }}</strong> /
                <strong>总 {{ renewSyncPreview.nextTotal }}</strong>
                （本次 +{{ renewSyncPreview.add }}）
              </p>
            </template>
            <p v-else-if="(createForm.phone || '').trim().length >= 5" class="modal-hint modal-hint--warn">
              未找到该手机号会员，请确认已注册或改用「新会员开卡」。
            </p>
          </div>
          <div v-if="createForm.open_mode === 'new_member'" class="form-row">
            <div class="form-group">
              <label>会员姓名</label>
              <input v-model="createForm.name" required maxlength="100" placeholder="写入档案 name" />
            </div>
            <div class="form-group">
              <label>微信昵称</label>
              <input v-model="createForm.wechat_name" required maxlength="100" placeholder="写入档案 wechat_name" />
            </div>
          </div>
          <div class="form-group card-order-delivery-address-block">
            <label>配送位置（可选）</label>
            <p class="modal-hint card-order-map-hint">
              与小程序一致：地图搜索或点选后自动填入详细地址（坐标仅后台保存，用于划区）；收货手机号与上方会员手机号相同。门牌号可补充。
            </p>
            <MemberDeliveryMapPicker
              v-model:lng-str="createForm.delivery_lng"
              v-model:lat-str="createForm.delivery_lat"
              v-model:map-location-text="createForm.map_location_text"
              @warn="onDeliveryMapWarn"
            />
            <div class="form-group">
              <label>地图详细地址</label>
              <textarea
                v-model="createForm.map_location_text"
                rows="2"
                maxlength="500"
                placeholder="选点后自动填入，可直接修改"
              />
            </div>
            <div class="form-group">
              <label>门牌号 / 单元楼层</label>
              <input v-model="createForm.door_detail" maxlength="500" placeholder="如：3 号楼 1202" />
            </div>
          </div>
          <div class="form-group open-mode-group">
            <label>开始配送日（业务日）</label>
            <div class="open-mode-options">
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="createForm.delivery_start_mode" type="radio" value="date" />
                  <span class="radio-tile-title">指定起送日</span>
                </span>
                <span class="radio-tile-sub">选择具体业务日起参与配送大表</span>
              </label>
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="createForm.delivery_start_mode" type="radio" value="defer" />
                  <span class="radio-tile-title">暂不开卡</span>
                </span>
                <span class="radio-tile-sub">已缴仍入次数与套餐；暂不写入起送日、不激活配送，可日后在「更新」中补日期</span>
              </label>
            </div>
            <div
              v-if="createForm.delivery_start_mode === 'date'"
              class="card-order-delivery-block"
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
              <p class="modal-hint card-order-delivery-hint">
                须不早于系统允许的最早业务日（上海）；该日起可查见、可派单。
              </p>
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>卡类型</label>
              <select v-model="createForm.card_kind">
                <option value="周卡">周卡（默认 +{{ planDefaultTotal('周卡') }} 次）</option>
                <option value="月卡">月卡（默认 +{{ planDefaultTotal('月卡') }} 次）</option>
                <option value="次卡">次卡（默认 +{{ planDefaultTotal('次卡') }} 次）</option>
              </select>
            </div>
            <div class="form-group">
              <label>缴费渠道</label>
              <select v-model="createForm.pay_channel">
                <option value="微信">微信</option>
                <option value="支付宝">支付宝</option>
                <option value="线下">线下</option>
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
          <p class="modal-hint">
            缴费状态为「已缴」时，创建后将自动同步剩余次数（周卡 +{{ planDefaultTotal('周卡') }} / 月卡
            +{{ planDefaultTotal('月卡') }} / 次卡 +{{ planDefaultTotal('次卡') }}）与套餐；仅在选择「指定起送日」时同时写入起送日并激活。选「未缴」则不入账。
          </p>
          <button type="submit" class="btn-submit-order" :disabled="createSubmitting">
            {{ createSubmitting ? '提交中…' : '创建工单' }}
          </button>
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
        <form class="modal-form modal-form--card-order" @submit.prevent="submitEdit">
          <div class="form-group">
            <label>会员</label>
            <input
              :value="`${editForm.member_name || '—'}${editForm.member_wechat_name ? ' / 微信 ' + editForm.member_wechat_name : ''}（${editForm.member_phone}）`"
              type="text"
              disabled
              class="input-disabled"
            />
          </div>
          <div class="form-group">
            <label>卡类型</label>
            <select v-model="editForm.card_kind" class="input-delivery-area" :disabled="editForm.applied_to_member">
              <option value="周卡">周卡（同步入账 +{{ planDefaultTotal('周卡') }} 次）</option>
              <option value="月卡">月卡（同步入账 +{{ planDefaultTotal('月卡') }} 次）</option>
              <option value="次卡">次卡（同步入账 +{{ planDefaultTotal('次卡') }} 次）</option>
            </select>
            <p v-if="editForm.applied_to_member" class="modal-hint">已入账工单不可改卡类型；若档案套餐标签有误请在「会员管理」中修正。</p>
          </div>
          <div class="form-group open-mode-group">
            <label>开始配送日</label>
            <div class="open-mode-options">
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="editForm.delivery_start_mode" type="radio" value="date" />
                  <span class="radio-tile-title">指定起送日</span>
                </span>
                <span class="radio-tile-sub">写入或修改具体业务日</span>
              </label>
              <label class="radio-tile">
                <span class="radio-tile-head">
                  <input v-model="editForm.delivery_start_mode" type="radio" value="defer" />
                  <span class="radio-tile-title">暂不开卡</span>
                </span>
                <span class="radio-tile-sub">工单上不保存起送日；已入账的会员起送日以档案为准</span>
              </label>
            </div>
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
              <select v-model="editForm.pay_channel">
                <option value="微信">微信</option>
                <option value="支付宝">支付宝</option>
                <option value="线下">线下</option>
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
          <p v-if="!editForm.applied_to_member" class="modal-hint">
            缴费状态为「已缴」且尚未入账时，保存将自动同步剩余次数与套餐；仅「指定起送日」时同时写入会员起送日并激活。
          </p>
          <button type="submit" class="btn-submit-order" :disabled="editSubmitting">
            {{ editSubmitting ? '保存中…' : '保存' }}
          </button>
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

.card-orders-history-check {
  width: 1rem;
  height: 1rem;
  margin: 0;
  accent-color: var(--primary, #3b82f6);
  cursor: pointer;
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
  margin-bottom: 4px;
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
/* Element Plus 日期选择：与弹窗内原生输入框的圆角、背景一致 */
.form-group :deep(.card-order-date-picker) {
  display: block;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}
.form-group :deep(.card-order-delivery-block .el-date-editor) {
  width: 100% !important;
  max-width: 100%;
  box-sizing: border-box;
}
.form-group :deep(.card-order-date-picker .el-input__wrapper) {
  width: 100%;
  min-height: 3.1rem;
  background: #f8fafc;
  border: 2px solid transparent;
  border-radius: 1.25rem;
  box-shadow: none;
}
.form-group :deep(.card-order-date-picker .el-input__wrapper.is-focus) {
  border-color: #0e5a44;
  background: #fff;
}
/* 开卡工单列表：更小行高、备注/创建信息缩略 */
.card-orders-page :deep(.card-orders-table.admin-table--members.el-table--small .el-table__header th.el-table__cell) {
  padding: 0.32rem 0.45rem;
  font-size: 11px;
}

.card-orders-page :deep(.card-orders-table.admin-table--members.el-table--small .el-table__body td.el-table__cell) {
  padding: 0.22rem 0.45rem;
}

.card-orders-page :deep(.card-orders-table .cell) {
  line-height: 1.22;
  font-size: 12px;
}

.co-member-compact {
  min-width: 0;
  line-height: 1.18;
}

.co-member-line1 {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  min-width: 0;
}

.co-member-name {
  font-weight: 800;
  font-size: 12px;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
}

.co-plan-tag {
  flex-shrink: 0;
  margin-left: 0;
  padding: 1px 6px;
  font-size: 10px;
  line-height: 1.2;
}

.co-member-line2 {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 1px;
  min-width: 0;
  font-size: 11px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.co-phone-icon {
  flex-shrink: 0;
  opacity: 0.85;
}

.co-phone-num {
  flex-shrink: 0;
}

.co-sep {
  opacity: 0.55;
  flex-shrink: 0;
}

.co-wx {
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.card-orders-page :deep(.co-nowrap .cell) {
  white-space: nowrap;
}

.co-amt-num {
  font-size: 12px;
  font-weight: 900;
}

.co-sync-pill {
  font-size: 10px;
  padding: 1px 6px;
  font-weight: 800;
}

.co-remark-text {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #475569;
  max-width: 100%;
}

.co-created-line {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #64748b;
  max-width: 100%;
}

.card-orders-page :deep(.td-co-actions .btn-sm) {
  padding: 0.22rem 0.42rem;
  font-size: 11px;
}
</style>
