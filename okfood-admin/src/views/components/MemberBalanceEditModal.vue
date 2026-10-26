<script setup>
import { computed, ref, watch, onActivated } from 'vue'
import { apiJson, handleAdminLogout, mapAdminUserToRow, memberShowsDinnerRemain } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

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
/** 打开时的次数与份数；仅与此不同才提交，避免未改动也写余额流水 */
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
  const balance = normalizeBalance(row?.balance)
  const dinnerBalance = normalizeBalance(row?.dinner_balance)
  const units = normalizeUnits(row?.daily_meal_units)
  const dinnerUnits = normalizeUnits(row?.dinner_daily_meal_units)
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
  const balanceVal = normalizeBalance(form.value.balance)
  const unitsVal = normalizeUnits(form.value.daily_meal_units)
  /** @type {Record<string, unknown>} */
  const payload = { phone }
  if (balanceVal !== initial.value.balance) payload.balance = balanceVal
  if (showDinnerRemain.value) {
    const dinnerVal = normalizeBalance(form.value.dinner_balance)
    if (dinnerVal !== initial.value.dinner_balance) payload.dinner_balance = dinnerVal
    // 晚餐份数单独提交；午餐份数仍只在 daily_meal_units 变化时提交
    const dinnerUnitsVal = normalizeUnits(form.value.dinner_daily_meal_units)
    if (dinnerUnitsVal !== initial.value.dinner_daily_meal_units) {
      payload.dinner_daily_meal_units = dinnerUnitsVal
    }
  }
  if (unitsVal !== initial.value.daily_meal_units) payload.daily_meal_units = unitsVal
  if (Object.keys(payload).length === 1) {
    showToast('未修改剩余次数或每日份数', 'error')
    return
  }
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
    showToast('次数与每日份数已更新', 'success')
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
  <el-dialog
    v-model="open"
    class="member-balance-dialog"
    width="480px"
    align-center
    destroy-on-close
    :close-on-click-modal="!saving"
    :close-on-press-escape="!saving"
    :show-close="!saving"
    title="修改次数"
  >
    <p v-if="profile || member" class="balance-who">
      {{ (profile || member).name || '—' }} · {{ (profile || member).phone || '' }}
      <span v-if="(profile || member).plan"> · {{ (profile || member).plan }}</span>
    </p>
    <el-form v-loading="loading" label-position="top" class="balance-form" @submit.prevent="submit">
      <el-form-item :label="showDinnerRemain ? '午餐剩余' : '剩余次数'">
        <div class="balance-affix">
          <el-input-number
            v-model="form.balance"
            :min="0"
            :max="999999"
            :step="1"
            :disabled="loading || saving"
            controls-position="right"
          />
          <span class="balance-suf">次</span>
        </div>
        <p class="balance-hint">
          {{
            showDinnerRemain
              ? '只改午餐次数池。直接修改会写入余额流水，常规续卡请走开卡工单。'
              : '直接修改会写入余额流水，常规续卡请走开卡工单。'
          }}
        </p>
      </el-form-item>
      <el-form-item v-if="showDinnerRemain" label="晚餐剩余">
        <div class="balance-affix">
          <el-input-number
            v-model="form.dinner_balance"
            :min="0"
            :max="999999"
            :step="1"
            :disabled="loading || saving"
            controls-position="right"
          />
          <span class="balance-suf">次</span>
        </div>
        <p class="balance-hint">只改晚餐次数池，与午餐分开记账。</p>
      </el-form-item>
      <el-form-item :label="showDinnerRemain ? '午餐每配送日份数' : '每配送日份数'">
        <div class="balance-affix">
          <el-input-number
            v-model="form.daily_meal_units"
            :min="1"
            :max="50"
            :step="1"
            :disabled="loading || saving"
            controls-position="right"
          />
          <span class="balance-suf">份</span>
        </div>
        <p class="balance-hint">
          {{
            showDinnerRemain
              ? '只改午餐份数。当日午餐大表已推单时，从下一配送日起生效。'
              : '当日大表已推单时，修改从下一配送日起生效，当日备餐份数不变。'
          }}
          <template v-if="pendingUnits != null">已预约次日改为 {{ pendingUnits }} 份。</template>
        </p>
      </el-form-item>
      <el-form-item v-if="showDinnerRemain" label="晚餐每配送日份数">
        <div class="balance-affix">
          <el-input-number
            v-model="form.dinner_daily_meal_units"
            :min="1"
            :max="50"
            :step="1"
            :disabled="loading || saving"
            controls-position="right"
          />
          <span class="balance-suf">份</span>
        </div>
        <p class="balance-hint">
          只改晚餐份数，不影响午餐。当日晚餐大表已推单时，从下一配送日起生效。
          <template v-if="pendingDinnerUnits != null">已预约次日改为 {{ pendingDinnerUnits }} 份。</template>
        </p>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button :disabled="saving" @click="close">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="submit">
        {{ loading ? '同步次数中…' : '确认保存' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.balance-who {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
}

.balance-affix {
  display: flex;
  align-items: center;
  gap: 8px;
}

.balance-affix :deep(.el-input-number) {
  width: 180px;
}

.balance-suf {
  font-size: 13px;
  color: #94a3b8;
}

.balance-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: #94a3b8;
}
</style>
