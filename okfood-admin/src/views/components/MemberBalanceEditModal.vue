<script setup>
import { computed, ref, watch, onActivated } from 'vue'
import { ElMessageBox } from 'element-plus'
import { apiJson, handleAdminLogout, mapAdminUserToRow, memberShowsDinnerRemain } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import OkfoodAdminDialogShell from '../../components/OkfoodAdminDialogShell.vue'
import MemberOperationContext from '../../components/MemberOperationContext.vue'

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  /** mapAdminUserToRow 行；弹窗打开时应非空 */
  member: { type: Object, default: null },
})

const emit = defineEmits(['saved'])

const saving = ref(false)
const loading = ref(false)
/** 丢弃过期的档案请求，避免连续打开不同会员时旧响应覆盖新表单 */
let loadSeq = 0
/** 打开后拉到的最新档案，用于判断是否展示晚餐次数池 */
const profile = ref(null)
/** 打开时的剩余次数与每日份数；仅与此不同才提交，避免把未改字段整单覆盖 */
const initial = ref({
  balance: 0,
  dinner_balance: 0,
  daily_meal_units: 1,
  dinner_daily_meal_units: 1,
})
/** 打开时是否存在午餐 / 晚餐份数预约（用于取消预约与提交判断） */
const initialPendingLunch = ref(null)
const initialPendingDinner = ref(null)
/** 已预约、下一配送日生效的午餐份数；输入框仍展示当日生效份数 */
const pendingUnits = ref(null)
/** 已预约、下一配送日生效的晚餐份数；与午餐预约互不影响 */
const pendingDinnerUnits = ref(null)
const form = ref({
  balance: 0,
  dinner_balance: 0,
  daily_meal_units: 1,
  dinner_daily_meal_units: 1,
})

const showDinnerRemain = computed(() => memberShowsDinnerRemain(profile.value || props.member))

const displayMember = computed(() => profile.value || props.member)

/** 午餐份数预约说明文案 */
const lunchPendingBannerText = computed(() => {
  if (pendingUnits.value == null) return ''
  const current = initial.value.daily_meal_units
  const label = showDinnerRemain.value ? '午餐' : ''
  return `已预约从下一配送日起 ${label}每配送日改为 ${pendingUnits.value} 份（当日仍为 ${current} 份）。保存为 ${current} 份可取消预约。`
})

const dinnerPendingBannerText = computed(() => {
  if (pendingDinnerUnits.value == null) return ''
  const current = initial.value.dinner_daily_meal_units
  return `已预约从下一配送日起晚餐每配送日改为 ${pendingDinnerUnits.value} 份（当日仍为 ${current} 份）。保存为 ${current} 份可取消预约。`
})

function normalizeBalance(v) {
  return Math.max(0, Math.min(999999, Math.floor(Number(v) || 0)))
}

function normalizeUnits(v) {
  return Math.max(1, Math.min(50, Math.floor(Number(v) || 1)))
}

/** @param {unknown} rawPending @param {number} currentUnits */
function pendingUnitsOrNull(rawPending, currentUnits) {
  const pendingNum = rawPending == null || rawPending === '' ? null : Math.floor(Number(rawPending))
  return pendingNum != null && pendingNum >= 1 && pendingNum !== currentUnits ? pendingNum : null
}

/** 从列表行或接口原始项解析午餐 pending */
function resolveLunchPendingRaw(row, raw) {
  if (raw && typeof raw === 'object' && raw.daily_meal_units_pending != null) {
    return raw.daily_meal_units_pending
  }
  return row?.daily_meal_units_pending
}

function applySnapshot(row, raw) {
  const units = normalizeUnits(row?.daily_meal_units)
  const dinnerUnits = normalizeUnits(row?.dinner_daily_meal_units)
  const balance = normalizeBalance(row?.balance)
  const dinnerBalance = normalizeBalance(row?.dinner_balance)
  form.value = {
    balance,
    dinner_balance: dinnerBalance,
    daily_meal_units: units,
    dinner_daily_meal_units: dinnerUnits,
  }
  initial.value = {
    balance,
    dinner_balance: dinnerBalance,
    daily_meal_units: units,
    dinner_daily_meal_units: dinnerUnits,
  }
  const lunchPending = pendingUnitsOrNull(resolveLunchPendingRaw(row, raw), units)
  pendingUnits.value = lunchPending
  initialPendingLunch.value = lunchPending
  const dinnerPending = pendingUnitsOrNull(
    row?.dinner_daily_meal_units_pending ?? raw?.dinner_daily_meal_units_pending,
    dinnerUnits,
  )
  pendingDinnerUnits.value = dinnerPending
  initialPendingDinner.value = dinnerPending
  profile.value = row
}

/** 当日份数未改但存在预约时，仍需提交当日值以清空 pending 或改预约 */
function lunchUnitsNeedsSubmit(unitsVal) {
  if (unitsVal !== initial.value.daily_meal_units) return true
  return initialPendingLunch.value != null && unitsVal === initial.value.daily_meal_units
}

function dinnerUnitsNeedsSubmit(dinnerUnitsVal) {
  if (dinnerUnitsVal !== initial.value.dinner_daily_meal_units) return true
  return initialPendingDinner.value != null && dinnerUnitsVal === initial.value.dinner_daily_meal_units
}

/** 打开时拉最新档案，避免列表缓存的剩余次数被整单覆盖 */
async function refreshFromServer(u) {
  if (!u || typeof u !== 'object') return
  const seq = ++loadSeq
  applySnapshot(u, null)
  const phone = String(u.phone || '').trim()
  if (!phone) return
  loading.value = true
  try {
    const params = new URLSearchParams({ q: phone, page: '1', page_size: '1' })
    const data = await apiJson(`/api/admin/users?${params}`, {}, { auth: true })
    if (seq !== loadSeq) return
    const rawItems = Array.isArray(data?.items) ? data.items : []
    const raw = rawItems[0]
    const fresh = raw ? mapAdminUserToRow(raw, 0) : u
    applySnapshot(fresh, raw && typeof raw === 'object' ? raw : null)
  } catch (e) {
    if (seq !== loadSeq) return
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载最新次数失败，已使用列表数据', 'error')
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

watch(
  [open, () => props.member],
  ([isOpen, m]) => {
    if (isOpen && m && typeof m === 'object') void refreshFromServer(m)
  },
  { flush: 'sync' },
)

onActivated(() => {
  if (open.value && props.member) void refreshFromServer(props.member)
})

function close() {
  if (saving.value) return
  open.value = false
}

/**
 * @param {Record<string, unknown>} payload
 * @param {{ clearingLunchPending?: boolean, clearingDinnerPending?: boolean }} opts
 */
async function postProfilePatch(payload, opts = {}) {
  const changedBalance = 'balance' in payload || 'dinner_balance' in payload
  const changedUnits = 'daily_meal_units' in payload || 'dinner_daily_meal_units' in payload
  saving.value = true
  try {
    await apiJson(
      '/api/admin/member/profile',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      { auth: true },
    )
    open.value = false
    let savedMsg = '每日份数已更新'
    if (opts.clearingLunchPending || opts.clearingDinnerPending) {
      savedMsg = '份数预约已取消'
    } else if (changedBalance && changedUnits) {
      savedMsg = '剩余次数与每日份数已更新'
    } else if (changedBalance) {
      savedMsg = '剩余次数已更新'
    }
    showToast(savedMsg, 'success')
    emit('saved')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function cancelPendingLunch() {
  if (loading.value || saving.value || pendingUnits.value == null) return
  const row = profile.value || props.member
  const phone = String(row?.phone || '').trim()
  if (!phone) return
  const keep = initial.value.daily_meal_units
  try {
    await ElMessageBox.confirm(
      `下一配送日将改为 ${pendingUnits.value} 份。确认取消预约，继续按每配送日 ${keep} 份？`,
      '取消份数预约',
      { confirmButtonText: '取消预约', cancelButtonText: '返回', type: 'warning' },
    )
  } catch {
    return
  }
  form.value.daily_meal_units = keep
  await postProfilePatch({ phone, daily_meal_units: keep }, { clearingLunchPending: true })
}

async function cancelPendingDinner() {
  if (loading.value || saving.value || pendingDinnerUnits.value == null) return
  const row = profile.value || props.member
  const phone = String(row?.phone || '').trim()
  if (!phone) return
  const keep = initial.value.dinner_daily_meal_units
  try {
    await ElMessageBox.confirm(
      `下一配送日晚餐将改为 ${pendingDinnerUnits.value} 份。确认取消预约，继续按每配送日 ${keep} 份？`,
      '取消晚餐份数预约',
      { confirmButtonText: '取消预约', cancelButtonText: '返回', type: 'warning' },
    )
  } catch {
    return
  }
  form.value.dinner_daily_meal_units = keep
  await postProfilePatch({ phone, dinner_daily_meal_units: keep }, { clearingDinnerPending: true })
}

async function submit() {
  const row = profile.value || props.member
  const phone = String(row?.phone || '').trim()
  if (!phone || loading.value || saving.value) return
  const unitsVal = normalizeUnits(form.value.daily_meal_units)
  const balanceVal = normalizeBalance(form.value.balance)
  /** @type {Record<string, unknown>} */
  const payload = { phone }
  if (showDinnerRemain.value) {
    // 晚餐次数与份数单独提交；午餐字段仍只在自身变化时提交
    const dinnerUnitsVal = normalizeUnits(form.value.dinner_daily_meal_units)
    if (dinnerUnitsNeedsSubmit(dinnerUnitsVal)) {
      payload.dinner_daily_meal_units = dinnerUnitsVal
    }
    const dinnerBalanceVal = normalizeBalance(form.value.dinner_balance)
    if (dinnerBalanceVal !== initial.value.dinner_balance) {
      payload.dinner_balance = dinnerBalanceVal
    }
  }
  if (lunchUnitsNeedsSubmit(unitsVal)) payload.daily_meal_units = unitsVal
  if (balanceVal !== initial.value.balance) payload.balance = balanceVal
  if (Object.keys(payload).length === 1) {
    showToast('未修改剩余次数或每日份数', 'error')
    return
  }
  const clearingLunchPending =
    'daily_meal_units' in payload &&
    payload.daily_meal_units === initial.value.daily_meal_units &&
    initialPendingLunch.value != null
  const clearingDinnerPending =
    'dinner_daily_meal_units' in payload &&
    payload.dinner_daily_meal_units === initial.value.dinner_daily_meal_units &&
    initialPendingDinner.value != null
  await postProfilePatch(payload, { clearingLunchPending, clearingDinnerPending })
}
</script>

<template>
  <OkfoodAdminDialogShell
    v-model:open="open"
    title="修改次数"
    size="md"
    :close-disabled="saving"
    :close-on-backdrop="!saving"
  >
    <template v-if="displayMember" #operation-context>
      <MemberOperationContext
        :name="displayMember.name"
        :phone="displayMember.phone"
        :plan="displayMember.plan"
      />
    </template>
    <div v-loading="loading">
      <div class="form-group">
        <label for="member-balance-lunch">{{ showDinnerRemain ? '午餐剩余次数' : '剩余次数' }}</label>
        <el-input-number
          id="member-balance-lunch"
          v-model="form.balance"
          :min="0"
          :max="999999"
          :step="1"
          :precision="0"
          :disabled="loading || saving"
          controls-position="right"
          class="okfood-dlg-input-number"
        />
        <p class="okfood-dlg-field-hint balance-hint">
          保存后立即覆盖该会员当前还能配送的{{ showDinnerRemain ? '午餐' : '' }}次数，差额写入次数流水。
        </p>
      </div>
      <div class="form-group">
        <label for="member-units-lunch">{{ showDinnerRemain ? '午餐每配送日份数' : '每配送日份数' }}</label>
        <div
          v-if="pendingUnits != null"
          class="okfood-dlg-hint-block member-balance-pending-banner"
          role="status"
        >
          <span class="okfood-dlg-hint-block__label">份数预约</span>
          <p class="okfood-dlg-hint-block__text">{{ lunchPendingBannerText }}</p>
          <el-button
            round
            size="small"
            :disabled="loading || saving"
            class="member-balance-pending-banner__btn"
            @click="cancelPendingLunch"
          >
            取消预约（改回 {{ initial.daily_meal_units }} 份）
          </el-button>
        </div>
        <el-input-number
          id="member-units-lunch"
          v-model="form.daily_meal_units"
          :min="1"
          :max="50"
          :step="1"
          :disabled="loading || saving"
          controls-position="right"
          class="okfood-dlg-input-number"
        />
        <p class="okfood-dlg-field-hint balance-hint">
          {{
            showDinnerRemain
              ? '只改午餐份数。当日午餐大表已推单时，从下一配送日起生效。'
              : '当日大表已推单时，修改从下一配送日起生效，当日备餐份数不变。'
          }}
        </p>
      </div>
      <div v-if="showDinnerRemain" class="form-group">
        <label for="member-balance-dinner">晚餐剩余次数</label>
        <el-input-number
          id="member-balance-dinner"
          v-model="form.dinner_balance"
          :min="0"
          :max="999999"
          :step="1"
          :precision="0"
          :disabled="loading || saving"
          controls-position="right"
          class="okfood-dlg-input-number"
        />
        <p class="okfood-dlg-field-hint balance-hint">
          保存后立即覆盖该会员当前还能配送的晚餐次数，差额写入晚餐次数流水。
        </p>
      </div>
      <div v-if="showDinnerRemain" class="form-group">
        <label for="member-units-dinner">晚餐每配送日份数</label>
        <div
          v-if="pendingDinnerUnits != null"
          class="okfood-dlg-hint-block member-balance-pending-banner"
          role="status"
        >
          <span class="okfood-dlg-hint-block__label">晚餐份数预约</span>
          <p class="okfood-dlg-hint-block__text">{{ dinnerPendingBannerText }}</p>
          <el-button
            round
            size="small"
            :disabled="loading || saving"
            class="member-balance-pending-banner__btn"
            @click="cancelPendingDinner"
          >
            取消预约（改回 {{ initial.dinner_daily_meal_units }} 份）
          </el-button>
        </div>
        <el-input-number
          id="member-units-dinner"
          v-model="form.dinner_daily_meal_units"
          :min="1"
          :max="50"
          :step="1"
          :disabled="loading || saving"
          controls-position="right"
          class="okfood-dlg-input-number"
        />
        <p class="okfood-dlg-field-hint balance-hint">
          只改晚餐份数，不影响午餐。当日晚餐大表已推单时，从下一配送日起生效。
        </p>
      </div>
    </div>
    <template #footer>
      <el-button round :disabled="saving" @click="close">取消</el-button>
      <el-button round type="primary" :loading="saving" :disabled="loading" @click="submit">
        {{ loading ? '同步次数中…' : '确认保存' }}
      </el-button>
    </template>
  </OkfoodAdminDialogShell>
</template>

<style scoped>
.member-balance-pending-banner {
  margin-bottom: 10px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--el-color-warning-light-9, #fdf6ec);
  border: 1px solid var(--el-color-warning-light-5, #f5dab1);
}

.member-balance-pending-banner__btn {
  margin-top: 8px;
}
</style>