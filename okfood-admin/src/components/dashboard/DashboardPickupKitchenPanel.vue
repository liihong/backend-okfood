<script setup>
import { computed, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const props = defineProps({
  /** 营业锚定日 YYYY-MM-DD，与 dashboard-summary 一致 */
  businessDate: { type: String, default: '' },
  /** 锚定日次日 YYYY-MM-DD */
  tomorrowBusinessDate: { type: String, default: '' },
  /** 锚定日周菜单「日总份数」；null 表示未配置 */
  menuDayTotalStock: { type: Number, default: null },
  /** 锚定日次日周菜单「日总份数」；null 表示未配置 */
  menuDayTotalStockTomorrow: { type: Number, default: null },
  /** 服务端上海当日 YYYY-MM-DD；未来营业日不拉配送大表 */
  shanghaiToday: { type: String, default: '' },
  /** 顶卡概览加载中：与 dashboard-summary 串行，避免同屏争抢 DB */
  summaryLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['menu-day-stock-saved'])

/** @typedef {{ member_id: number, name: string, phone: string, balance: number, meal_quota_total: number, is_delivered: boolean }} PickupRow */

const pickupSearch = ref('')
const pickupLoading = ref(false)
/** @type {import('vue').Ref<PickupRow[]>} */
const pickupRows = ref([])
const markingMemberId = ref(null)

const kitchenInput = ref(0)
const kitchenInputTomorrow = ref(0)
const kitchenSaving = ref(false)

function syncKitchenInputFromStock(stock, targetRef) {
  if (stock != null && stock >= 0) {
    targetRef.value = stock
  } else {
    targetRef.value = 0
  }
}

/** 后厨输入框：读取本周菜单对应日「日总份数」 */
watch(
  () => [props.menuDayTotalStock, props.businessDate],
  () => {
    syncKitchenInputFromStock(props.menuDayTotalStock, kitchenInput)
  },
  { immediate: true },
)

watch(
  () => [props.menuDayTotalStockTomorrow, props.tomorrowBusinessDate],
  () => {
    syncKitchenInputFromStock(props.menuDayTotalStockTomorrow, kitchenInputTomorrow)
  },
  { immediate: true },
)

const pendingPickupCount = computed(() => pickupRows.value.filter((r) => !r.is_delivered).length)

const filteredPickupRows = computed(() => {
  const q = pickupSearch.value.trim().toLowerCase()
  if (!q) return pickupRows.value
  return pickupRows.value.filter((r) => {
    const name = String(r.name || '').toLowerCase()
    const phone = String(r.phone || '')
    return name.includes(q) || phone.includes(q)
  })
})

/** 卡包展示：有 quota 用 quota 作分母，否则仅展示 balance */
function formatQuotaDisplay(row) {
  const bal = Math.max(0, Math.trunc(Number(row.balance) || 0))
  const quota = Math.max(0, Math.trunc(Number(row.meal_quota_total) || 0))
  const total = quota > 0 ? quota : bal
  return { bal, total }
}

async function fetchPickupList() {
  if (!adminAccessToken.value || props.summaryLoading) return
  const d0 = (props.businessDate || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d0)) return
  const today = (props.shanghaiToday || '').trim()
  if (today && d0 > today) {
    pickupRows.value = []
    return
  }
  pickupLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/delivery-sheet?delivery_date=${encodeURIComponent(d0)}`,
      {},
      { auth: true },
    )
    const groups = Array.isArray(data?.groups) ? data.groups : []
    const pickupGroup = groups.find((g) => g?.area === '门店自提')
    /** @type {PickupRow[]} */
    const rows = []
    if (pickupGroup && Array.isArray(pickupGroup.stops)) {
      for (const st of pickupGroup.stops) {
        for (const m of st.members || []) {
          rows.push({
            member_id: Number(m.member_id),
            name: String(m.name ?? ''),
            phone: String(m.phone ?? ''),
            balance: Number(m.balance) || 0,
            meal_quota_total: Number(m.meal_quota_total) || 0,
            is_delivered: Boolean(m.is_delivered),
          })
        }
      }
    }
    pickupRows.value = rows
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    pickupRows.value = []
    showToast(e instanceof Error ? e.message : '加载自提列表失败', 'error')
  } finally {
    pickupLoading.value = false
  }
}

/** 单行自提核销（与智能配送大表 delivery-mark kind=pickup 一致） */
async function verifyPickup(row) {
  if (row.is_delivered || markingMemberId.value != null) return
  const d0 = (props.businessDate || '').trim()
  if (!d0) return
  markingMemberId.value = row.member_id
  try {
    await apiJson(
      '/api/admin/delivery-mark',
      {
        method: 'POST',
        body: JSON.stringify({
          member_id: Number(row.member_id),
          delivery_date: d0,
          kind: 'pickup',
        }),
      },
      { auth: true },
    )
    showToast(`客户 ${row.name}（${row.phone}）自提核销成功`, 'success')
    await fetchPickupList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '核销失败', 'error')
  } finally {
    markingMemberId.value = null
  }
}

async function saveKitchenPlanForDate(businessDate, plannedTotal) {
  await apiJson(
    '/api/admin/kitchen-plan',
    {
      method: 'PUT',
      body: JSON.stringify({ business_date: businessDate, planned_total: plannedTotal }),
    },
    { auth: true },
  )
}

/** 保存今日/明日日总份数，并通知顶卡刷新 dashboard-summary */
async function saveKitchenPlan() {
  if (kitchenSaving.value) return
  const d0 = (props.businessDate || '').trim()
  const d1 = (props.tomorrowBusinessDate || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d0)) {
    showToast('请先选择有效营业日', 'error')
    return
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d1)) {
    showToast('无法计算明日营业日，请刷新后重试', 'error')
    return
  }
  const valToday = Math.trunc(Number(kitchenInput.value))
  const valTomorrow = Math.trunc(Number(kitchenInputTomorrow.value))
  if (!Number.isFinite(valToday) || valToday < 0 || !Number.isFinite(valTomorrow) || valTomorrow < 0) {
    showToast('请输入正确的日总份数', 'error')
    return
  }
  kitchenSaving.value = true
  try {
    const results = await Promise.allSettled([
      saveKitchenPlanForDate(d0, valToday),
      saveKitchenPlanForDate(d1, valTomorrow),
    ])
    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length === 2) {
      const firstErr = failed[0].reason
      const status = firstErr && typeof firstErr.status === 'number' ? firstErr.status : 0
      if (status === 401) {
        alert('登录已过期，请重新登录')
        handleAdminLogout()
        return
      }
      showToast(firstErr instanceof Error ? firstErr.message : '保存后厨计划失败', 'error')
      return
    }
    if (failed.length === 1) {
      const err = failed[0].reason
      const status = err && typeof err.status === 'number' ? err.status : 0
      if (status === 401) {
        alert('登录已过期，请重新登录')
        handleAdminLogout()
        return
      }
      const failedLabel = results[0].status === 'rejected' ? '今日' : '明日'
      showToast(
        `${failedLabel}保存失败：${err instanceof Error ? err.message : '未知错误'}`,
        'error',
      )
      emit('menu-day-stock-saved', { today: valToday, tomorrow: valTomorrow })
      return
    }
    showToast(`今日 ${valToday} 份、明日 ${valTomorrow} 份已保存，本周菜单已同步`, 'success')
    emit('menu-day-stock-saved', { today: valToday, tomorrow: valTomorrow })
  } finally {
    kitchenSaving.value = false
  }
}

watch(
  () => [props.businessDate, props.summaryLoading, props.shanghaiToday],
  () => {
    if (props.summaryLoading) return
    void fetchPickupList()
  },
  { immediate: true },
)
</script>

<template>
  <section class="dpk-grid" aria-label="后厨计划与门店自提核销">
    <!-- 后厨计划管理（左） -->
    <article class="dpk-card dpk-card--kitchen">
      <div class="dpk-card-title dpk-card-title--blue">🍳 后厨计划管理</div>
      <div class="dpk-formula">
        保存后同步更新「本周菜单配置」与顶卡「后厨总生产 / 可卖数量」
      </div>
      <div class="dpk-form-row">
        <div class="dpk-form-group">
          <label class="dpk-form-label">今日日总份数</label>
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInput"
              type="number"
              class="dpk-form-control"
              min="0"
              max="99999"
              inputmode="numeric"
            />
            <span class="dpk-unit">份</span>
          </div>
        </div>
        <div class="dpk-form-group">
          <label class="dpk-form-label">明日日总份数</label>
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputTomorrow"
              type="number"
              class="dpk-form-control"
              min="0"
              max="99999"
              inputmode="numeric"
            />
            <span class="dpk-unit">份</span>
          </div>
        </div>
      </div>
      <button
        type="button"
        class="dpk-btn-save"
        :disabled="kitchenSaving"
        @click="saveKitchenPlan"
      >
        {{ kitchenSaving ? '保存中…' : '确定并保存日总份数' }}
      </button>
    </article>

    <!-- 门店自提快速核销舱（右） -->
    <article class="dpk-card">
      <div class="dpk-card-title">
        <span>🏪 门店自提快速核销舱</span>
        <span class="dpk-pending-label">待自提：{{ pendingPickupCount }} 份</span>
      </div>

      <div class="dpk-search-box">
        <Search :size="14" class="dpk-search-icon" aria-hidden="true" />
        <input
          v-model="pickupSearch"
          type="search"
          class="dpk-search-input"
          placeholder="输入自提客户姓名或手机号后四位模糊搜索..."
          autocomplete="off"
        />
      </div>

      <div class="dpk-scroll-wrap">
        <p v-if="pickupLoading" class="dpk-hint">正在加载自提列表…</p>
        <p v-else-if="!pickupRows.length" class="dpk-hint">当日暂无门店自提订阅会员</p>
        <table v-else class="dpk-table">
          <thead>
            <tr>
              <th>名称</th>
              <th>电话</th>
              <th>次数</th>
              <th>状态</th>
              <th class="dpk-th-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredPickupRows" :key="row.member_id">
              <td class="dpk-td-name">{{ row.name || '—' }}</td>
              <td class="dpk-td-phone">{{ row.phone || '—' }}</td>
              <td>
                <span
                  class="dpk-quota"
                  :class="{ 'dpk-quota--muted': row.is_delivered }"
                >
                  {{ formatQuotaDisplay(row).bal }} 次 / 共 {{ formatQuotaDisplay(row).total }} 次
                </span>
              </td>
              <td>
                <span
                  class="dpk-badge"
                  :class="row.is_delivered ? 'dpk-badge--done' : 'dpk-badge--pending'"
                >
                  {{ row.is_delivered ? '已完成自提' : '待自提' }}
                </span>
              </td>
              <td class="dpk-td-action">
                <button
                  type="button"
                  class="dpk-btn-verify"
                  :disabled="row.is_delivered || markingMemberId === row.member_id"
                  @click="verifyPickup(row)"
                >
                  {{ row.is_delivered ? '已核销' : markingMemberId === row.member_id ? '核销中…' : '核销完成' }}
                </button>
              </td>
            </tr>
            <tr v-if="pickupRows.length && !filteredPickupRows.length">
              <td colspan="5" class="dpk-empty-filter">无匹配客户，请调整搜索条件</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.dpk-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  margin-bottom: 1rem;
}

@media (min-width: 1024px) {
  .dpk-grid {
    grid-template-columns: 1.2fr 1.8fr;
    gap: 1.5rem;
  }
}

.dpk-card {
  background: #fff;
  border-radius: 28px;
  border: 1px solid #eaedf1;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 0;
}

.dpk-card--kitchen {
  border-color: #bfdbfe;
}

.dpk-card-title {
  font-size: 14.5px;
  font-weight: 900;
  color: #0f172a;
  border-left: 4px solid #0d5c46;
  padding-left: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dpk-card-title--blue {
  border-left-color: #3b82f6;
}

.dpk-pending-label {
  font-size: 11px;
  font-weight: 800;
  color: #0d5c46;
}

.dpk-search-box {
  position: relative;
  width: 100%;
}

.dpk-search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: #64748b;
  pointer-events: none;
}

.dpk-search-input {
  width: 100%;
  padding: 10px 16px 10px 38px;
  border-radius: 12px;
  border: 1px solid #eaedf1;
  background: #f8fafc;
  font-size: 12.5px;
  font-weight: 700;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.dpk-search-input:focus {
  border-color: #0d5c46;
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 92, 70, 0.05);
}

.dpk-scroll-wrap {
  max-height: 290px;
  overflow-y: auto;
  border: 1px solid #eaedf1;
  border-radius: 16px;
  background: #fafbfc;
}

.dpk-scroll-wrap::-webkit-scrollbar {
  width: 5px;
}

.dpk-scroll-wrap::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.25);
  border-radius: 10px;
}

.dpk-hint {
  margin: 0;
  padding: 1.25rem;
  font-size: 13px;
  color: #64748b;
  text-align: center;
}

.dpk-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.dpk-table th {
  background: #f1f5f9;
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 800;
  color: #64748b;
  position: sticky;
  top: 0;
  z-index: 1;
}

.dpk-th-action,
.dpk-td-action {
  text-align: right;
}

.dpk-table td {
  padding: 12px 14px;
  font-size: 12.5px;
  border-bottom: 1px solid #eaedf1;
  font-weight: 600;
  vertical-align: middle;
}

.dpk-table tbody tr:hover {
  background: rgba(241, 245, 249, 0.65);
}

.dpk-td-name {
  font-weight: 800;
  color: #0f172a;
}

.dpk-td-phone {
  font-family: ui-monospace, monospace;
  font-weight: 700;
  color: #64748b;
}

.dpk-quota {
  font-family: ui-monospace, monospace;
  font-weight: 900;
  color: #0d5c46;
}

.dpk-quota--muted {
  color: #64748b;
}

.dpk-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 10.5px;
  font-weight: 800;
}

.dpk-badge--pending {
  background: #fffbeb;
  color: #b45309;
}

.dpk-badge--done {
  background: #ecfdf5;
  color: #065f46;
}

.dpk-btn-verify {
  background: #0d5c46;
  color: #fff;
  border: none;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.2s;
}

.dpk-btn-verify:hover:not(:disabled) {
  background: #0a4635;
}

.dpk-btn-verify:disabled {
  background: #cbd5e1;
  color: #94a3b8;
  cursor: not-allowed;
}

.dpk-empty-filter {
  text-align: center;
  color: #64748b;
  font-size: 12px;
  padding: 1.5rem !important;
}

.dpk-formula {
  background: rgba(59, 130, 246, 0.06);
  border: 1px dashed rgba(59, 130, 246, 0.25);
  border-radius: 14px;
  padding: 12px;
  font-size: 11.5px;
  font-weight: 800;
  color: #1d4ed8;
  line-height: 1.5;
  text-align: center;
}

.dpk-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 4px;
}

.dpk-form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.dpk-form-label {
  color: #3b82f6;
  font-weight: 700;
  font-size: 12.5px;
}

.dpk-input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dpk-form-control {
  flex: 1;
  min-width: 0;
  max-width: 120px;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #eaedf1;
  font-size: 13.5px;
  font-weight: 800;
  outline: none;
  background: #f8fafc;
  text-align: center;
}

.dpk-form-control:focus {
  border-color: #3b82f6;
  background: #fff;
}

.dpk-unit {
  font-size: 13px;
  font-weight: 800;
  color: #64748b;
}

.dpk-btn-save {
  background: #3b82f6;
  color: #fff;
  border: none;
  padding: 12px 20px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: background 0.2s;
  text-align: center;
  margin-top: auto;
}

.dpk-btn-save:hover:not(:disabled) {
  background: #2563eb;
}

.dpk-btn-save:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
