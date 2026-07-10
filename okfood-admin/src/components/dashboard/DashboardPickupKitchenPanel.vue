<script setup>
import { computed, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { isSubscriptionDeliveryDayIso } from '../../utils/deliveryCalendar.js'

const props = defineProps({
  /** 营业锚定日 YYYY-MM-DD，与 dashboard-summary 一致 */
  businessDate: { type: String, default: '' },
  /** 锚定日次日 YYYY-MM-DD */
  tomorrowBusinessDate: { type: String, default: '' },
  /** 锚定日后天 YYYY-MM-DD */
  dayAfterTomorrowBusinessDate: { type: String, default: '' },
  /** 锚定日午餐周菜单「日总份数」；与 menuDayTotalStockDinner 分餐段 */
  menuDayTotalStock: { type: Number, default: null },
  /** 锚定日次日午餐周菜单「日总份数」（meal_period=lunch） */
  menuDayTotalStockTomorrow: { type: Number, default: null },
  /** 锚定日后天午餐周菜单「日总份数」 */
  menuDayTotalStockDayAfterTomorrow: { type: Number, default: null },
  /** 锚定日晚餐周菜单「日总份数」；与 menuDayTotalStock 分餐段，互不影响 */
  menuDayTotalStockDinner: { type: Number, default: null },
  /** 锚定日次日晚餐周菜单「日总份数」 */
  menuDayTotalStockTomorrowDinner: { type: Number, default: null },
  /** 锚定日后天晚餐周菜单「日总份数」 */
  menuDayTotalStockDayAfterTomorrowDinner: { type: Number, default: null },
  /** 服务端上海当日 YYYY-MM-DD；未来营业日不拉配送大表 */
  shanghaiToday: { type: String, default: '' },
  /** 顶卡概览加载中：与 dashboard-summary 串行，避免同屏争抢 DB */
  summaryLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['menu-day-stock-saved'])

/** @typedef {{ kind: 'subscription', member_id: number, plan_type?: string | null, name: string, phone: string, daily_meal_units: number, balance: number, meal_quota_total: number, is_delivered: boolean }} SubscriptionPickupRow */
/** @typedef {{ kind: 'retail', order_id: number, name: string, phone: string, dish_title: string, quantity: number, is_delivered: boolean }} RetailPickupRow */
/** @typedef {SubscriptionPickupRow | RetailPickupRow} PickupRow */

const pickupSearch = ref('')
const pickupLoading = ref(false)
/** @type {import('vue').Ref<PickupRow[]>} */
const pickupRows = ref([])
/** 接口返回的待自提份数合计（订阅 daily_meal_units + 零售 quantity） */
const pickupPendingCount = ref(0)
/** 核销中行的唯一键：订阅 sub:{member_id}，零售 retail:{order_id} */
const markingKey = ref(null)

const kitchenInput = ref(0)
const kitchenInputTomorrow = ref(0)
const kitchenInputDayAfterTomorrow = ref(0)
const kitchenInputDinner = ref(0)
const kitchenInputTomorrowDinner = ref(0)
const kitchenInputDayAfterTomorrowDinner = ref(0)
const kitchenSaving = ref(false)

function syncKitchenInputFromStock(stock, targetRef) {
  if (stock != null && stock >= 0) {
    targetRef.value = stock
  } else {
    targetRef.value = 0
  }
}

/** 后厨输入框：午餐列 ← dashboard-summary.today_menu_day_total_stock（meal_period=lunch） */
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

watch(
  () => [props.menuDayTotalStockDayAfterTomorrow, props.dayAfterTomorrowBusinessDate],
  () => {
    syncKitchenInputFromStock(props.menuDayTotalStockDayAfterTomorrow, kitchenInputDayAfterTomorrow)
  },
  { immediate: true },
)

/** 后厨输入框：晚餐列 ← dashboard-summary.today_dinner_menu_day_total_stock（meal_period=dinner） */
watch(
  () => [props.menuDayTotalStockDinner, props.businessDate],
  () => {
    syncKitchenInputFromStock(props.menuDayTotalStockDinner, kitchenInputDinner)
  },
  { immediate: true },
)

watch(
  () => [props.menuDayTotalStockTomorrowDinner, props.tomorrowBusinessDate],
  () => {
    syncKitchenInputFromStock(props.menuDayTotalStockTomorrowDinner, kitchenInputTomorrowDinner)
  },
  { immediate: true },
)

watch(
  () => [props.menuDayTotalStockDayAfterTomorrowDinner, props.dayAfterTomorrowBusinessDate],
  () => {
    syncKitchenInputFromStock(
      props.menuDayTotalStockDayAfterTomorrowDinner,
      kitchenInputDayAfterTomorrowDinner,
    )
  },
  { immediate: true },
)

const pendingPickupCount = computed(() => pickupPendingCount.value)

/** 单行当日自提份数：订阅取 daily_meal_units，零售取 quantity */
function pickupPortionCount(row) {
  if (row.kind === 'retail') {
    return Math.max(1, Math.trunc(Number(row.quantity) || 1))
  }
  return Math.max(1, Math.trunc(Number(row.daily_meal_units) || 1))
}

function formatPickupPortionLabel(row) {
  const count = pickupPortionCount(row)
  if (row.kind === 'retail') {
    const dish = String(row.dish_title || '').trim()
    return dish ? `${dish} · ${count} 份` : `${count} 份`
  }
  return `${count} 份`
}

const filteredPickupRows = computed(() => {
  const q = pickupSearch.value.trim().toLowerCase()
  if (!q) return pickupRows.value
  return pickupRows.value.filter((r) => {
    const name = String(r.name || '').toLowerCase()
    const phone = String(r.phone || '')
    const refNo = pickupRefNo(r)
    const refText = refNo ? refNo.text.toLowerCase() : ''
    const refId = String(
      r.kind === 'retail' ? Math.trunc(Number(r.order_id) || 0) : Math.trunc(Number(r.member_id) || 0),
    )
    return name.includes(q) || phone.includes(q) || refText.includes(q) || refId.includes(q)
  })
})

/** 卡包展示：有 quota 用 quota 作分母，否则仅展示 balance */
function formatQuotaDisplay(row) {
  const bal = Math.max(0, Math.trunc(Number(row.balance) || 0))
  const quota = Math.max(0, Math.trunc(Number(row.meal_quota_total) || 0))
  const total = quota > 0 ? quota : bal
  return { bal, total }
}

function pickupRowKey(row) {
  return row.kind === 'retail' ? `retail:${row.order_id}` : `sub:${row.member_id}`
}

/** 单号列：零售为订单号，周/月卡为会员 ID */
function pickupRefNo(row) {
  if (row.kind === 'retail') {
    const id = Math.trunc(Number(row.order_id) || 0)
    return id > 0 ? { text: `#${id}`, title: `订单 #${id}` } : null
  }
  const plan = String(row.plan_type || '').trim()
  if (plan !== '周卡' && plan !== '月卡') return null
  const id = Math.trunc(Number(row.member_id) || 0)
  return id > 0 ? { text: `#${id}`, title: `会员ID #${id}` } : null
}

function pickupRowMarkKey(row) {
  return pickupRowKey(row)
}

async function fetchPickupList() {
  if (!adminAccessToken.value || props.summaryLoading) return
  const d0 = (props.businessDate || '').trim()
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d0)) return
  const today = (props.shanghaiToday || '').trim()
  if (today && d0 > today) {
    pickupRows.value = []
    pickupPendingCount.value = 0
    return
  }
  pickupLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/pickup-verification-list?delivery_date=${encodeURIComponent(d0)}`,
      {},
      { auth: true },
    )
    pickupRows.value = Array.isArray(data?.rows) ? data.rows : []
    pickupPendingCount.value = Math.max(0, Math.trunc(Number(data?.pending_count) || 0))
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    pickupRows.value = []
    pickupPendingCount.value = 0
    showToast(e instanceof Error ? e.message : '加载自提列表失败', 'error')
  } finally {
    pickupLoading.value = false
  }
}

/** 单行自提核销：订阅走 delivery-mark；单次零售走 mark-delivered */
async function verifyPickup(row) {
  if (row.is_delivered || markingKey.value != null) return
  const d0 = (props.businessDate || '').trim()
  if (!d0) return
  markingKey.value = pickupRowMarkKey(row)
  try {
    if (row.kind === 'retail') {
      await apiJson(
        `/api/admin/orders/single-meals/${row.order_id}/mark-delivered`,
        { method: 'POST' },
        { auth: true },
      )
    } else {
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
    }
    const label =
      row.kind === 'retail'
        ? `零售自提单 #${row.order_id}（${row.name || row.phone}）`
        : `客户 ${row.name}（${row.phone}）`
    showToast(`${label}核销成功`, 'success')
    await fetchPickupList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '核销失败', 'error')
  } finally {
    markingKey.value = null
  }
}

async function saveKitchenPlanForDate(businessDate, plannedTotal, mealPeriod = 'lunch') {
  await apiJson(
    '/api/admin/kitchen-plan',
    {
      method: 'PUT',
      body: JSON.stringify({
        business_date: businessDate,
        planned_total: plannedTotal,
        meal_period: mealPeriod,
      }),
    },
    { auth: true },
  )
}

const KITCHEN_DAY_LABELS = ['今日', '明日', '后天']

const dayAfterTomorrowIsBusinessDay = computed(() =>
  isSubscriptionDeliveryDayIso(props.dayAfterTomorrowBusinessDate),
)

/** 保存今日/明日/后天午餐+晚餐日总份数，并通知顶卡刷新 dashboard-summary */
async function saveKitchenPlan() {
  if (kitchenSaving.value) return
  const entries = [
    {
      label: '今日午餐',
      date: (props.businessDate || '').trim(),
      value: Math.trunc(Number(kitchenInput.value)),
      mealPeriod: 'lunch',
    },
    {
      label: '今日晚餐',
      date: (props.businessDate || '').trim(),
      value: Math.trunc(Number(kitchenInputDinner.value)),
      mealPeriod: 'dinner',
    },
    {
      label: '明日午餐',
      date: (props.tomorrowBusinessDate || '').trim(),
      value: Math.trunc(Number(kitchenInputTomorrow.value)),
      mealPeriod: 'lunch',
    },
    {
      label: '明日晚餐',
      date: (props.tomorrowBusinessDate || '').trim(),
      value: Math.trunc(Number(kitchenInputTomorrowDinner.value)),
      mealPeriod: 'dinner',
    },
    {
      label: '后天午餐',
      date: (props.dayAfterTomorrowBusinessDate || '').trim(),
      value: Math.trunc(Number(kitchenInputDayAfterTomorrow.value)),
      mealPeriod: 'lunch',
    },
    {
      label: '后天晚餐',
      date: (props.dayAfterTomorrowBusinessDate || '').trim(),
      value: Math.trunc(Number(kitchenInputDayAfterTomorrowDinner.value)),
      mealPeriod: 'dinner',
    },
  ]
  if (!/^\d{4}-\d{2}-\d{2}$/.test(entries[0].date)) {
    showToast('请先选择有效营业日', 'error')
    return
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(entries[2].date)) {
    showToast('无法计算明日营业日，请刷新后重试', 'error')
    return
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(entries[4].date)) {
    showToast('无法计算后天营业日，请刷新后重试', 'error')
    return
  }
  if (entries.some((e) => !Number.isFinite(e.value) || e.value < 0)) {
    showToast('请输入正确的日总份数', 'error')
    return
  }
  const saveTargets = entries.filter((e) => isSubscriptionDeliveryDayIso(e.date))
  if (!saveTargets.length) {
    showToast('所选日期均为非营业日，无需保存日总份数', 'error')
    return
  }
  kitchenSaving.value = true
  try {
    const results = await Promise.allSettled(
      saveTargets.map((e) => saveKitchenPlanForDate(e.date, e.value, e.mealPeriod)),
    )
    const failed = results
      .map((r, i) => ({ r, entry: saveTargets[i] }))
      .filter(({ r }) => r.status === 'rejected')
    const payload = {
      today: entries[0].value,
      todayDinner: entries[1].value,
      tomorrow: entries[2].value,
      tomorrowDinner: entries[3].value,
      dayAfterTomorrow: entries[4].value,
      dayAfterTomorrowDinner: entries[5].value,
    }
    if (failed.length === saveTargets.length) {
      const firstErr = failed[0].r.reason
      const status = firstErr && typeof firstErr.status === 'number' ? firstErr.status : 0
      if (status === 401) {
        alert('登录已过期，请重新登录')
        handleAdminLogout()
        return
      }
      showToast(firstErr instanceof Error ? firstErr.message : '保存后厨计划失败', 'error')
      return
    }
    if (failed.length > 0) {
      const { r: failResult, entry } = failed[0]
      const err = failResult.reason
      const status = err && typeof err.status === 'number' ? err.status : 0
      if (status === 401) {
        alert('登录已过期，请重新登录')
        handleAdminLogout()
        return
      }
      showToast(
        `${entry.label}保存失败：${err instanceof Error ? err.message : '未知错误'}`,
        'error',
      )
      emit('menu-day-stock-saved', payload)
      return
    }
    const savedText = saveTargets.map((e) => `${e.label} ${e.value} 份`).join('、')
    const skipped = entries.filter((e) => !isSubscriptionDeliveryDayIso(e.date))
    const skipHint =
      skipped.length > 0 ? `（${skipped.map((e) => e.label).join('、')}为非营业日已跳过）` : ''
    showToast(`${savedText}已保存，本周菜单已同步${skipHint}`, 'success')
    emit('menu-day-stock-saved', payload)
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

      <div class="dpk-kitchen-grid">
        <div class="dpk-kitchen-grid__head">
          <span class="dpk-kitchen-grid__corner" />
          <span class="dpk-kitchen-grid__col">午餐</span>
          <span class="dpk-kitchen-grid__col dpk-kitchen-grid__col--dinner">晚餐</span>
        </div>
        <div class="dpk-kitchen-grid__row">
          <label class="dpk-kitchen-grid__row-label">{{ KITCHEN_DAY_LABELS[0] }}日总份数</label>
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
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputDinner"
              type="number"
              class="dpk-form-control dpk-form-control--dinner"
              min="0"
              max="99999"
              inputmode="numeric"
            />
            <span class="dpk-unit">份</span>
          </div>
        </div>
        <div class="dpk-kitchen-grid__row">
          <label class="dpk-kitchen-grid__row-label">{{ KITCHEN_DAY_LABELS[1] }}日总份数</label>
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
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputTomorrowDinner"
              type="number"
              class="dpk-form-control dpk-form-control--dinner"
              min="0"
              max="99999"
              inputmode="numeric"
            />
            <span class="dpk-unit">份</span>
          </div>
        </div>
        <div class="dpk-kitchen-grid__row">
          <label class="dpk-kitchen-grid__row-label">
            {{ KITCHEN_DAY_LABELS[2] }}日
            <span v-if="!dayAfterTomorrowIsBusinessDay" class="dpk-nonbiz-hint">（非营业日）</span>
          </label>
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputDayAfterTomorrow"
              type="number"
              class="dpk-form-control"
              min="0"
              max="99999"
              inputmode="numeric"
              :disabled="!dayAfterTomorrowIsBusinessDay"
            />
            <span class="dpk-unit">份</span>
          </div>
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputDayAfterTomorrowDinner"
              type="number"
              class="dpk-form-control dpk-form-control--dinner"
              min="0"
              max="99999"
              inputmode="numeric"
              :disabled="!dayAfterTomorrowIsBusinessDay"
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
          placeholder="输入姓名、手机号后四位或单号模糊搜索..."
          autocomplete="off"
        />
      </div>

      <div class="dpk-scroll-wrap">
        <p v-if="pickupLoading" class="dpk-hint">正在加载自提列表…</p>
        <p v-else-if="!pickupRows.length" class="dpk-hint">当日暂无门店自提客户（含订阅与零售）</p>
        <table v-else class="dpk-table">
          <thead>
            <tr>
              <th class="dpk-th-ref">会员ID/单号</th>
              <th>名称</th>
              <th>自提份数</th>
              <th>状态</th>
              <th class="dpk-th-action">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredPickupRows" :key="pickupRowKey(row)">
              <td class="dpk-td-ref">
                <template v-if="pickupRefNo(row)">
                  <span class="dpk-ref-no" :title="pickupRefNo(row).title">
                    {{ pickupRefNo(row).text }}
                  </span>
                </template>
                <span v-else class="dpk-ref-empty">—</span>
              </td>
              <td class="dpk-td-name">
                {{ row.name || '—' }}
                <span v-if="row.kind === 'retail'" class="dpk-retail-tag">零售</span>
              </td>
              <td>
                <span
                  class="dpk-portion"
                  :class="{ 'dpk-portion--muted': row.is_delivered }"
                >
                  {{ formatPickupPortionLabel(row) }}
                </span>
                <span
                  v-if="row.kind === 'subscription'"
                  class="dpk-balance-hint"
                  :class="{ 'dpk-balance-hint--muted': row.is_delivered }"
                >
                  卡包 {{ formatQuotaDisplay(row).bal }} / {{ formatQuotaDisplay(row).total }} 次
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
                  :disabled="row.is_delivered || markingKey === pickupRowMarkKey(row)"
                  @click="verifyPickup(row)"
                >
                  {{
                    row.is_delivered
                      ? '已核销'
                      : markingKey === pickupRowMarkKey(row)
                        ? '核销中…'
                        : '核销完成'
                  }}
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

.dpk-th-ref,
.dpk-td-ref {
  width: 88px;
  text-align: center;
  white-space: nowrap;
}

.dpk-ref-no {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 48px;
  padding: 2px 8px;
  border-radius: 6px;
  font-family: var(--okfood-font-number);
  font-size: 12px;
  font-weight: 900;
  color: #0f172a;
  background: #f1f5f9;
}

.dpk-ref-empty {
  color: #cbd5e1;
  font-weight: 700;
}

.dpk-retail-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 800;
  color: #b45309;
  background: #fffbeb;
  vertical-align: middle;
}

.dpk-portion {
  display: block;
  font-family: var(--okfood-font-number);
  font-weight: 900;
  font-size: 13px;
  color: #0d5c46;
}

.dpk-portion--muted {
  color: #64748b;
}

.dpk-balance-hint {
  display: block;
  margin-top: 2px;
  font-size: 10.5px;
  font-weight: 700;
  color: #94a3b8;
}

.dpk-balance-hint--muted {
  color: #cbd5e1;
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

.dpk-kitchen-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dpk-kitchen-grid__head,
.dpk-kitchen-grid__row {
  display: grid;
  grid-template-columns: minmax(88px, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: center;
}

.dpk-kitchen-grid__head {
  margin-bottom: 0.15rem;
}

.dpk-kitchen-grid__col {
  font-size: 12px;
  font-weight: 800;
  color: #3b82f6;
  text-align: center;
}

.dpk-kitchen-grid__col--dinner {
  color: #7c3aed;
}

.dpk-kitchen-grid__row-label {
  font-size: 12px;
  font-weight: 700;
  color: #475569;
  line-height: 1.35;
}

.dpk-form-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.75rem;
  margin-top: 4px;
}

@media (max-width: 640px) {
  .dpk-form-row {
    grid-template-columns: 1fr;
  }
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

.dpk-nonbiz-hint {
  margin-left: 4px;
  color: #94a3b8;
  font-weight: 600;
  font-size: 11px;
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

.dpk-form-control--dinner:focus {
  border-color: #7c3aed;
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
