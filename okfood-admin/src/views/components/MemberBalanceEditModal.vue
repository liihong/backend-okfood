<script setup>
import { computed, ref, watch, onActivated } from 'vue'
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
/** 已预约、下一配送日生效的午餐份数；仅作提示，输入框仍展示当日生效份数 */
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

function normalizeBalance(v) {
  return Math.max(0, Math.min(999999, Math.floor(Number(v) || 0)))
}

function normalizeUnits(v) {
  return Math.max(1, Math.min(50, Math.floor(Number(v) || 1)))
}

/**
 * @param {Record<string, unknown>} row
 * @param {Record<string, unknown> | null | undefined} raw
 */
function pendingUnitsOrNull(rawPending, currentUnits) {
  const pendingNum = rawPending == null || rawPending === '' ? null : Math.floor(Number(rawPending))
  return pendingNum != null && pendingNum >= 1 && pendingNum !== currentUnits ? pendingNum : null
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
  pendingUnits.value = pendingUnitsOrNull(raw?.daily_meal_units_pending, units)
  pendingDinnerUnits.value = pendingUnitsOrNull(
    row?.dinner_daily_meal_units_pending ?? raw?.dinner_daily_meal_units_pending,
    dinnerUnits,
  )
  profile.value = row
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
    if (dinnerUnitsVal !== initial.value.dinner_daily_meal_units) {
      payload.dinner_daily_meal_units = dinnerUnitsVal
    }
    const dinnerBalanceVal = normalizeBalance(form.value.dinner_balance)
    if (dinnerBalanceVal !== initial.value.dinner_balance) {
      payload.dinner_balance = dinnerBalanceVal
    }
  }
  if (unitsVal !== initial.value.daily_meal_units) payload.daily_meal_units = unitsVal
  if (balanceVal !== initial.value.balance) payload.balance = balanceVal
  if (Object.keys(payload).length === 1) {
    showToast('未修改剩余次数或每日份数', 'error')
    return
  }
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
    const savedMsg =
      changedBalance && changedUnits
        ? '剩余次数与每日份数已更新'
        : changedBalance
          ? '剩余次数已更新'
          : '每日份数已更新'
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
          <template v-if="pendingUnits != null">已预约次日改为 {{ pendingUnits }} 份。</template>
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
          <template v-if="pendingDinnerUnits != null">已预约次日改为 {{ pendingDinnerUnits }} 份。</template>
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

