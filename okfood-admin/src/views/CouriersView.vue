<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus, Phone, X } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

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
const pinResetValue = ref('')
const pinResetSubmitting = ref(false)

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
  if (!regions || !regions.length) return '—'
  return regions.map((r) => (r.is_primary ? `${r.name}(主责)` : r.name)).join('、')
}

function formatMoneyYuan(v) {
  if (v === null || v === undefined || v === '') return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return n.toFixed(2)
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

function openCourierPinModal(courierId) {
  pinResetCourierId.value = courierId
  pinResetValue.value = ''
  showCourierPinModal.value = true
}

async function submitCourierModal() {
  if (courierModalSubmitting.value) return
  courierModalSubmitting.value = true
  try {
    if (courierModalMode.value === 'create') {
      const pin = (courierForm.pin || '').trim()
      if (pin.length < 4) {
        showToast('初始 PIN 至少 4 位', 'error')
        return
      }
      await apiJson(
        '/api/admin/couriers',
        {
          method: 'POST',
          body: JSON.stringify({
            courier_id: (courierForm.courier_id || '').trim(),
            name: (courierForm.name || '').trim() || null,
            phone: (courierForm.phone || '').trim() || null,
            pin,
            is_active: !!courierForm.is_active,
          }),
        },
        { auth: true },
      )
      showToast('配送员已创建')
    } else {
      const fp = (courierForm.fee_pending || '').trim()
      const fs = (courierForm.fee_settled || '').trim()
      const body = {
        name: (courierForm.name || '').trim() || null,
        phone: (courierForm.phone || '').trim() || null,
        is_active: !!courierForm.is_active,
      }
      if (fp !== '') body.fee_pending = Number(fp)
      if (fs !== '') body.fee_settled = Number(fs)
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
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header table-header--members table-header--couriers-row">
        <p class="couriers-hint">
          负责区域在「配送区域」中绑定配送员；此处维护档案、费用与登录 PIN。
        </p>
        <button type="button" class="btn-primary btn-primary--sm" @click="openCourierCreateModal">
          <Plus :size="18" /> 新建配送员
        </button>
      </div>
      <p v-if="couriersLoading" class="members-loading">加载配送员列表中…</p>
      <table v-else class="data-table data-table--members">
        <thead>
          <tr>
            <th>工号</th>
            <th>姓名</th>
            <th>电话</th>
            <th class="text-right">待结算(元)</th>
            <th class="text-right">已结算(元)</th>
            <th>负责区域</th>
            <th>状态</th>
            <th class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in couriersList" :key="c.courier_id">
            <td class="td-mono">{{ c.courier_id }}</td>
            <td>{{ c.name || '—' }}</td>
            <td class="td-phone">
              <div class="member-phone-cell">
                <Phone :size="12" class="member-phone-icon" />
                <span class="member-phone-num">{{ c.phone || '—' }}</span>
              </div>
            </td>
            <td class="text-right">{{ formatMoneyYuan(c.fee_pending) }}</td>
            <td class="text-right">{{ formatMoneyYuan(c.fee_settled) }}</td>
            <td><span class="area-tag area-tag--multi">{{ courierRegionsLabel(c.regions) }}</span></td>
            <td>
              <span
                class="member-pill"
                :class="c.is_active !== false ? 'member-pill--emerald' : 'member-pill--slate'"
              >
                {{ c.is_active !== false ? '在职' : '已停用' }}
              </span>
            </td>
            <td class="text-right couriers-actions">
              <button type="button" class="btn-sm" @click="openCourierEditModal(c)">编辑</button>
              <button type="button" class="btn-sm" @click="openCourierPinModal(c.courier_id)">
                重置 PIN
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="showCourierModal" class="modal-overlay" @click.self="showCourierModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>{{ courierModalMode === 'create' ? '新建配送员' : '编辑配送员' }}</h3>
            <p>COURIER PROFILE</p>
          </div>
          <button type="button" class="close-btn" @click="showCourierModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="submitCourierModal">
          <div v-if="courierModalMode === 'create'" class="form-row">
            <div class="form-group">
              <label>工号</label>
              <input v-model="courierForm.courier_id" required placeholder="如 C001" />
            </div>
            <div class="form-group">
              <label>初始 PIN</label>
              <input
                v-model="courierForm.pin"
                type="password"
                required
                minlength="4"
                placeholder="至少 4 位"
              />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>姓名</label>
              <input v-model="courierForm.name" placeholder="配送员姓名" />
            </div>
            <div class="form-group">
              <label>电话</label>
              <input v-model="courierForm.phone" maxlength="20" placeholder="手机号" />
            </div>
          </div>
          <div v-if="courierModalMode === 'edit'" class="form-row">
            <div class="form-group">
              <label>待结算金额(元)</label>
              <input
                v-model="courierForm.fee_pending"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
              />
            </div>
            <div class="form-group">
              <label>已结算累计(元)</label>
              <input
                v-model="courierForm.fee_settled"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
              />
            </div>
          </div>
          <div v-if="courierModalMode === 'edit'" class="form-group">
            <label class="checkbox-inline">
              <input v-model="courierForm.is_active" type="checkbox" />
              在职（取消勾选即停用）
            </label>
          </div>
          <button type="submit" class="btn-submit-order" :disabled="courierModalSubmitting">
            {{ courierModalSubmitting ? '提交中…' : '保存' }}
          </button>
        </form>
      </div>
    </div>

    <div v-if="showCourierPinModal" class="modal-overlay" @click.self="showCourierPinModal = false">
      <div class="modal-card">
        <div class="modal-header">
          <div class="header-info">
            <h3>重置 PIN · {{ pinResetCourierId }}</h3>
            <p>COURIER PIN RESET</p>
          </div>
          <button type="button" class="close-btn" @click="showCourierPinModal = false">
            <X :size="20" />
          </button>
        </div>
        <form class="modal-form" @submit.prevent="submitCourierPinReset">
          <div class="form-group">
            <label>新 PIN</label>
            <input
              v-model="pinResetValue"
              type="password"
              required
              minlength="4"
              placeholder="至少 4 位"
            />
          </div>
          <button type="submit" class="btn-submit-order" :disabled="pinResetSubmitting">
            {{ pinResetSubmitting ? '提交中…' : '确认重置' }}
          </button>
        </form>
      </div>
    </div>
  </section>
</template>
