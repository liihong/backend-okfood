<script setup>
defineOptions({ name: 'CouriersView' })
import { computed, nextTick, onActivated, onMounted, onUnmounted, reactive, ref } from 'vue'
import { Phone, Plus, Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import OkfoodAdminDialogShell from '../components/OkfoodAdminDialogShell.vue'
import MemberOperationContext from '../components/MemberOperationContext.vue'

const couriersList = ref([])
const couriersLoading = ref(false)
const courierModalSubmitting = ref(false)
const showCourierModal = ref(false)
const courierModalMode = ref('create')
const courierForm = reactive({
  courier_id: '',
  name: '',
  phone: '',
  pin: '',
  is_active: true,
  fee_pending: '',
  fee_settled: '',
})
const showCourierPinModal = ref(false)
const pinResetCourierId = ref('')
const pinResetName = ref('')
const pinResetPhone = ref('')
const pinResetValue = ref('')
const pinResetSubmitting = ref(false)

const keyword = ref('')
const statusFilter = ref('')

const tableHostRef = ref(null)
const tableScrollHeight = ref(480)
/** @type {ResizeObserver | null} */
let tableResizeObserver = null

const displayedCouriers = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  return couriersList.value.filter((row) => {
    if (statusFilter.value === 'active' && row.is_active === false) return false
    if (statusFilter.value === 'inactive' && row.is_active !== false) return false
    if (!q) return true
    const blob = [row.courier_id, row.name, row.phone].map((v) => String(v || '').toLowerCase()).join(' ')
    return blob.includes(q)
  })
})

const tableEmptyText = computed(() => {
  if (couriersList.value.length && !displayedCouriers.value.length) return '没有符合条件的配送员'
  return '暂无配送员'
})

function updateTableHeight() {
  const el = tableHostRef.value
  if (!el) return
  const h = Math.floor(el.getBoundingClientRect().height)
  if (h >= 160) tableScrollHeight.value = h
}

function bindTableObserver() {
  void nextTick(() => {
    updateTableHeight()
    if (!tableResizeObserver) {
      tableResizeObserver = new ResizeObserver(() => updateTableHeight())
    }
    if (tableHostRef.value) tableResizeObserver.observe(tableHostRef.value)
  })
}

async function fetchCouriers() {
  if (!adminAccessToken.value) return
  couriersLoading.value = true
  try {
    const data = await apiJson('/api/admin/couriers', {}, { auth: true })
    couriersList.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载配送员失败', 'error')
  } finally {
    couriersLoading.value = false
  }
}

function courierRegionsLabel(regions) {
  if (!regions || !regions.length) return ''
  return regions.map((r) => (r.is_primary ? `${r.name}(主责)` : r.name)).join('、')
}

function formatMoneyYuan(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toFixed(2)
}

/**
 * 费用输入：留空表示本次不提交该字段；非数字才拦截。
 * @param {string} raw
 */
function parseOptionalFee(raw) {
  const s = String(raw || '').trim()
  if (s === '') return { ok: true, omit: true, value: 0 }
  const n = Number(s)
  if (!Number.isFinite(n)) return { ok: false, omit: true, value: 0 }
  return { ok: true, omit: false, value: n }
}

function resetCourierForm() {
  courierForm.courier_id = ''
  courierForm.name = ''
  courierForm.phone = ''
  courierForm.pin = ''
  courierForm.is_active = true
  courierForm.fee_pending = ''
  courierForm.fee_settled = ''
}

function openCourierCreateModal() {
  courierModalMode.value = 'create'
  resetCourierForm()
  showCourierModal.value = true
}

function openCourierEditModal(row) {
  courierModalMode.value = 'edit'
  courierForm.courier_id = row.courier_id || ''
  courierForm.name = row.name || ''
  courierForm.phone = row.phone || ''
  courierForm.pin = ''
  courierForm.is_active = row.is_active !== false
  courierForm.fee_pending =
    row.fee_pending !== undefined && row.fee_pending !== null ? String(row.fee_pending) : ''
  courierForm.fee_settled =
    row.fee_settled !== undefined && row.fee_settled !== null ? String(row.fee_settled) : ''
  showCourierModal.value = true
}

function openCourierPinModal(row) {
  pinResetCourierId.value = row.courier_id || ''
  pinResetName.value = row.name || ''
  pinResetPhone.value = row.phone || ''
  pinResetValue.value = ''
  showCourierPinModal.value = true
}

async function submitCourierModal() {
  if (courierModalSubmitting.value) return
  if (courierModalMode.value === 'create') {
    if (!(courierForm.courier_id || '').trim()) {
      showToast('请填写工号', 'error')
      return
    }
    const pin = (courierForm.pin || '').trim()
    if (pin.length < 4) {
      showToast('初始 PIN 至少 4 位', 'error')
      return
    }
  }
  const pendingFee = parseOptionalFee(courierForm.fee_pending)
  const settledFee = parseOptionalFee(courierForm.fee_settled)
  if (courierModalMode.value === 'edit' && (!pendingFee.ok || !settledFee.ok)) {
    showToast('金额须为数字', 'error')
    return
  }

  courierModalSubmitting.value = true
  try {
    if (courierModalMode.value === 'create') {
      await apiJson(
        '/api/admin/couriers',
        {
          method: 'POST',
          body: JSON.stringify({
            courier_id: (courierForm.courier_id || '').trim(),
            name: (courierForm.name || '').trim() || null,
            phone: (courierForm.phone || '').trim() || null,
            pin: (courierForm.pin || '').trim(),
            is_active: !!courierForm.is_active,
          }),
        },
        { auth: true },
      )
      showToast('配送员已创建')
    } else {
      const body = {
        name: (courierForm.name || '').trim() || null,
        phone: (courierForm.phone || '').trim() || null,
        is_active: !!courierForm.is_active,
      }
      if (!pendingFee.omit) body.fee_pending = pendingFee.value
      if (!settledFee.omit) body.fee_settled = settledFee.value
      await apiJson(
        `/api/admin/couriers/${encodeURIComponent(courierForm.courier_id)}`,
        {
          method: 'PATCH',
          body: JSON.stringify(body),
        },
        { auth: true },
      )
      showToast('已保存')
    }
    showCourierModal.value = false
    await fetchCouriers()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    courierModalSubmitting.value = false
  }
}

async function submitCourierPinReset() {
  if (pinResetSubmitting.value) return
  const pin = (pinResetValue.value || '').trim()
  if (pin.length < 4) {
    showToast('新 PIN 至少 4 位', 'error')
    return
  }
  pinResetSubmitting.value = true
  try {
    await apiJson(
      `/api/admin/couriers/${encodeURIComponent(pinResetCourierId.value)}/pin`,
      { method: 'POST', body: JSON.stringify({ pin }) },
      { auth: true },
    )
    showToast('PIN 已更新')
    showCourierPinModal.value = false
  } catch (e) {
    showToast(e instanceof Error ? e.message : '重置失败', 'error')
  } finally {
    pinResetSubmitting.value = false
  }
}

onMounted(() => {
  void fetchCouriers()
  bindTableObserver()
})

onActivated(() => {
  bindTableObserver()
})

onUnmounted(() => {
  tableResizeObserver?.disconnect()
  tableResizeObserver = null
})
</script>

<template>
  <section class="tab-content animate-up couriers-page members-view-fill">
    <div class="table-container table-container--members-fill">
      <div class="table-header table-header--members">
        <div class="members-toolbar-row">
          <p
            class="couriers-toolbar-hint"
            title="负责区域在「配送区域」中绑定配送员；此处维护档案、费用与登录 PIN。"
          >
            负责区域在「配送区域」中绑定；此处维护档案、费用与登录 PIN。
          </p>
          <div class="members-toolbar-search members-search-wrap couriers-search-wrap">
            <el-input
              v-model="keyword"
              clearable
              placeholder="工号 / 姓名 / 电话"
              class="members-search-el-input"
            >
              <template #prefix>
                <Search :size="14" class="members-search-el-icon" aria-hidden="true" />
              </template>
            </el-input>
          </div>
          <el-select v-model="statusFilter" class="couriers-status-select" placeholder="状态">
            <el-option label="全部状态" value="" />
            <el-option label="在职" value="active" />
            <el-option label="已停用" value="inactive" />
          </el-select>
          <div class="members-toolbar-trailing">
            <el-button type="primary" size="small" class="couriers-create-btn" @click="openCourierCreateModal">
              <Plus :size="14" aria-hidden="true" />
              新建配送员
            </el-button>
          </div>
        </div>
      </div>

      <div ref="tableHostRef" class="members-table-host">
        <AdminTable
          variant="members"
          class="members-el-table-body-scroll"
          size="small"
          :data="displayedCouriers"
          :loading="couriersLoading"
          row-key="courier_id"
          :height="tableScrollHeight"
          :empty-text="tableEmptyText"
        >
          <el-table-column prop="courier_id" label="工号" min-width="88" class-name="td-mono" />
          <el-table-column label="姓名" min-width="88">
            <template #default="{ row: c }">{{ c.name || '—' }}</template>
          </el-table-column>
          <el-table-column
            label="电话"
            min-width="148"
            class-name="td-phone"
            label-class-name="td-phone"
          >
            <template #default="{ row: c }">
              <div class="member-phone-cell">
                <Phone :size="12" class="member-phone-icon" />
                <span class="member-phone-num">{{ c.phone || '—' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="待结算(元)" align="right" min-width="108" class-name="td-mono">
            <template #default="{ row: c }">{{ formatMoneyYuan(c.fee_pending) }}</template>
          </el-table-column>
          <el-table-column label="已结算(元)" align="right" min-width="108" class-name="td-mono">
            <template #default="{ row: c }">{{ formatMoneyYuan(c.fee_settled) }}</template>
          </el-table-column>
          <el-table-column label="负责区域" min-width="140">
            <template #default="{ row: c }">
              <el-tooltip
                v-if="courierRegionsLabel(c.regions)"
                :content="courierRegionsLabel(c.regions)"
                placement="top"
                :show-after="300"
              >
                <span class="couriers-regions">{{ courierRegionsLabel(c.regions) }}</span>
              </el-tooltip>
              <span v-else class="couriers-regions couriers-regions--empty">—</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" min-width="88">
            <template #default="{ row: c }">
              <span
                class="member-pill"
                :class="c.is_active !== false ? 'member-pill--emerald' : 'member-pill--slate'"
              >
                {{ c.is_active !== false ? '在职' : '已停用' }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" align="right" min-width="148" fixed="right">
            <template #default="{ row: c }">
              <div class="members-row-actions">
                <el-button type="primary" link size="small" class="btn-members-link" @click="openCourierEditModal(c)">
                  编辑
                </el-button>
                <el-button type="primary" link size="small" class="btn-members-link" @click="openCourierPinModal(c)">
                  重置 PIN
                </el-button>
              </div>
            </template>
          </el-table-column>
        </AdminTable>
      </div>
    </div>

    <OkfoodAdminDialogShell
      v-model:open="showCourierModal"
      :title="courierModalMode === 'create' ? '新建配送员' : '编辑配送员'"
      :subtitle="
        courierModalMode === 'create'
          ? '工号创建后不可修改'
          : '费用留空则保持原金额'
      "
      fit-content
      dlg-class="okfood-admin-dlg--edit-fit"
      :close-disabled="courierModalSubmitting"
      :close-on-backdrop="!courierModalSubmitting"
    >
      <template v-if="courierModalMode === 'edit'" #operation-context>
        <MemberOperationContext
          :name="courierForm.name || courierForm.courier_id"
          :phone="courierForm.phone"
          :plan="courierForm.name ? `工号 ${courierForm.courier_id}` : ''"
        />
      </template>

      <form id="courier-profile-form" class="okfood-mem-edit-inner" @submit.prevent="submitCourierModal">
        <section class="okfood-mem-edit-sec">
          <header class="okfood-mem-edit-sec-head">
            <span class="okfood-mem-edit-bar" aria-hidden="true" />
            <h3 class="okfood-mem-edit-sec-title">档案</h3>
          </header>
          <div class="okfood-mem-edit-grid-2 couriers-form-grid">
            <div v-if="courierModalMode === 'create'" class="form-group okfood-mem-edit-field">
              <label for="courier-id">工号</label>
              <el-input
                id="courier-id"
                v-model="courierForm.courier_id"
                class="okfood-mem-edit-input"
                placeholder="如 C001"
                clearable
                :disabled="courierModalSubmitting"
              />
            </div>
            <div v-if="courierModalMode === 'create'" class="form-group okfood-mem-edit-field">
              <label for="courier-pin">初始 PIN</label>
              <el-input
                id="courier-pin"
                v-model="courierForm.pin"
                class="okfood-mem-edit-input"
                type="password"
                show-password
                placeholder="至少 4 位"
                autocomplete="new-password"
                :disabled="courierModalSubmitting"
              />
            </div>
            <div class="form-group okfood-mem-edit-field">
              <label for="courier-name">姓名</label>
              <el-input
                id="courier-name"
                v-model="courierForm.name"
                class="okfood-mem-edit-input"
                placeholder="配送员姓名"
                clearable
                :disabled="courierModalSubmitting"
              />
            </div>
            <div class="form-group okfood-mem-edit-field">
              <label for="courier-phone">电话</label>
              <el-input
                id="courier-phone"
                v-model="courierForm.phone"
                class="okfood-mem-edit-input"
                maxlength="20"
                placeholder="手机号"
                clearable
                :disabled="courierModalSubmitting"
              />
            </div>
          </div>
          <div class="couriers-active-row">
            <span class="couriers-active-row__label">在职</span>
            <el-switch v-model="courierForm.is_active" :disabled="courierModalSubmitting" />
            <span class="couriers-active-row__hint">关闭后无法登录配送端</span>
          </div>
        </section>

        <section v-if="courierModalMode === 'edit'" class="okfood-mem-edit-sec">
          <header class="okfood-mem-edit-sec-head">
            <span class="okfood-mem-edit-bar" aria-hidden="true" />
            <h3 class="okfood-mem-edit-sec-title">费用</h3>
            <span class="couriers-sec-note">留空表示不修改</span>
          </header>
          <div class="okfood-mem-edit-grid-2 couriers-form-grid">
            <div class="form-group okfood-mem-edit-field">
              <label for="courier-fee-pending">待结算金额(元)</label>
              <el-input
                id="courier-fee-pending"
                v-model="courierForm.fee_pending"
                class="okfood-mem-edit-input"
                placeholder="0.00"
                clearable
                :disabled="courierModalSubmitting"
              />
            </div>
            <div class="form-group okfood-mem-edit-field">
              <label for="courier-fee-settled">已结算累计(元)</label>
              <el-input
                id="courier-fee-settled"
                v-model="courierForm.fee_settled"
                class="okfood-mem-edit-input"
                placeholder="0.00"
                clearable
                :disabled="courierModalSubmitting"
              />
            </div>
          </div>
        </section>
      </form>

      <template #footer>
        <el-button round :disabled="courierModalSubmitting" @click="showCourierModal = false">取消</el-button>
        <el-button
          round
          type="primary"
          native-type="submit"
          form="courier-profile-form"
          :loading="courierModalSubmitting"
        >
          保存
        </el-button>
      </template>
    </OkfoodAdminDialogShell>

    <OkfoodAdminDialogShell
      v-model:open="showCourierPinModal"
      :title="`重置 PIN · ${pinResetCourierId}`"
      subtitle="至少 4 位，保存后立即生效"
      size="md"
      fit-content
      :close-disabled="pinResetSubmitting"
      :close-on-backdrop="!pinResetSubmitting"
    >
      <template #operation-context>
        <MemberOperationContext
          :name="pinResetName || pinResetCourierId"
          :phone="pinResetPhone"
          :plan="pinResetName ? `工号 ${pinResetCourierId}` : ''"
        />
      </template>
      <form id="courier-pin-form" @submit.prevent="submitCourierPinReset">
        <div class="form-group">
          <label for="courier-pin-reset">新 PIN</label>
          <el-input
            id="courier-pin-reset"
            v-model="pinResetValue"
            type="password"
            show-password
            placeholder="至少 4 位"
            autocomplete="new-password"
            :disabled="pinResetSubmitting"
          />
        </div>
      </form>
      <template #footer>
        <el-button round :disabled="pinResetSubmitting" @click="showCourierPinModal = false">取消</el-button>
        <el-button
          round
          type="primary"
          native-type="submit"
          form="courier-pin-form"
          :loading="pinResetSubmitting"
        >
          确认重置
        </el-button>
      </template>
    </OkfoodAdminDialogShell>
  </section>
</template>

<style scoped>
.couriers-toolbar-hint {
  margin: 0;
  flex: 1 1 auto;
  min-width: 8rem;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.35;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.couriers-search-wrap {
  width: 196px;
  min-width: 168px;
  max-width: 220px;
}

.couriers-status-select {
  width: 112px;
  flex: 0 0 auto;
  --el-component-size: var(--members-toolbar-control-h, 32px);
}

.couriers-status-select :deep(.el-select__wrapper) {
  min-height: var(--members-toolbar-control-h, 32px);
  height: var(--members-toolbar-control-h, 32px);
  padding: 0 10px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
  font-size: 12px;
  font-weight: 600;
}

.couriers-status-select :deep(.el-select__wrapper.is-focused) {
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--el-color-primary) 42%, #e2e8f0) inset,
    0 0 0 3px color-mix(in srgb, var(--el-color-primary) 12%, transparent);
}

.couriers-page :deep(.couriers-create-btn.el-button) {
  --el-button-size: var(--members-toolbar-control-h, 32px);
  height: var(--members-toolbar-control-h, 32px);
  min-height: var(--members-toolbar-control-h, 32px);
  padding: 0 12px;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  border-radius: 999px;
}

.couriers-page :deep(.couriers-create-btn svg) {
  margin-right: 4px;
  vertical-align: -2px;
}

.couriers-regions {
  display: inline-block;
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.couriers-regions--empty {
  color: #94a3b8;
  font-weight: 500;
}

.couriers-form-grid .form-group {
  margin-bottom: 0;
}

.couriers-active-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.couriers-active-row__label {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
}

.couriers-active-row__hint {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
}

.couriers-sec-note {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
}

@media (max-width: 860px) {
  .couriers-toolbar-hint {
    display: none;
  }
}
</style>
