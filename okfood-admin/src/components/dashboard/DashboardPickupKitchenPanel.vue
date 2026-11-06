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

/** 保存今日/明日/后天午餐+晚餐日总份数；保存完成后由父组件 await dashboard-summary 全量刷新 */
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
  // 是否订阅配送业务日由服务端 delivery_calendar 判定（含补班周日），前端不做周日一刀切
  const saveTargets = entries
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
      emit('menu-day-stock-saved')
      return
    }
    const savedText = saveTargets.map((e) => `${e.label} ${e.value} 份`).join('、')
    showToast(`${savedText}已保存，本周菜单已同步`, 'success')
    emit('menu-day-stock-saved')
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
      <div class="dpk-kitchen-grid">
        <!-- 标题行与下方输入列同一栅格：左标题 + 右「午餐 / 晚餐」列头 -->
        <div class="dpk-kitchen-grid__title-row">
          <div class="dpk-kitchen-grid__title-brand">🍳 后厨计划管理</div>
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
          <label class="dpk-kitchen-grid__row-label">{{ KITCHEN_DAY_LABELS[2] }}日总份数</label>
          <div class="dpk-input-row">
            <input
              v-model.number="kitchenInputDayAfterTomorrow"
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
              v-model.number="kitchenInputDayAfterTomorrowDinner"
              type="number"
              class="dpk-form-control dpk-form-control--dinner"
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

    <!-- 门店自提快速核销舱（右）：搜索框与标题同行（标题 ↔ 搜索 ↔ 待自提） -->
    <article class="dpk-card dpk-card--pickup">
      <div class="dpk-card-title dpk-card-title--pickup-row">
        <span class="dpk-card-title__pickup-brand">🏪 门店自提快速核销舱</span>
        <div class="dpk-search-box dpk-search-box--header">
          <Search :size="14" class="dpk-search-icon" aria-hidden="true" />
          <input
            v-model="pickupSearch"
            type="search"
            class="dpk-search-input"
            placeholder="输入姓名、手机号后四位或单号模糊搜索..."
            autocomplete="off"
          />
        </div>
        <span class="dpk-pending-label">待自提：{{ pendingPickupCount }} 份</span>
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
  gap: 0.9rem;
  margin-bottom: 1rem;
}

@media (min-width: 1024px) {
  .dpk-grid {
    grid-template-columns: 1.2fr 1.8fr;
    gap: 1rem;
  }
}

.dpk-card {
  background: rgba(255, 255, 255, 0.55);
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.72);
  padding: 1rem 1.15rem;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.5) inset,
    0 6px 22px rgba(25, 45, 55, 0.045);
  backdrop-filter: saturate(1.2) blur(14px);
  -webkit-backdrop-filter: saturate(1.2) blur(14px);
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  min-height: 0;
}

/* 与 KPI 卡一致：仅整圈浅描边 + 毛玻璃，无彩色顶线 */

/* 后厨卡：在「日总份数」表格与主按钮之间留出可呼吸间距，避免整卡内容贴顶贴底 */
.dpk-card--kitchen .dpk-btn-save {
  margin-top: 0.65rem;
}

.dpk-card--pickup {
  gap: 0.65rem;
}

.dpk-card-title {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  border: none;
  border-left: none;
  padding-left: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.dpk-card-title--blue {
  border-left: none;
}

/* 自提卡标题行：左标题 + 中间搜索（占满剩余宽度）+ 右待自提份数 */
.dpk-card-title--pickup-row {
  width: 100%;
  align-items: center;
  flex-wrap: wrap;
  row-gap: 0.5rem;
  justify-content: flex-start;
}

.dpk-card-title__pickup-brand {
  flex: 0 0 auto;
  min-width: 0;
}

.dpk-card-title--pickup-row .dpk-pending-label {
  flex: 0 0 auto;
  margin-left: auto;
}

.dpk-pending-label {
  font-size: 10.5px;
  font-weight: 700;
  color: var(--el-color-primary-dark-2, #047857);
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  background: color-mix(in srgb, var(--el-color-primary) 10%, rgba(255, 255, 255, 0.35));
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 22%, rgba(255, 255, 255, 0.5));
}

.dpk-search-box {
  position: relative;
  width: 100%;
}

.dpk-search-box--header {
  flex: 1 1 12rem;
  min-width: 8rem;
  max-width: 100%;
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
  padding: 8px 12px 8px 34px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 18%, rgba(148, 163, 184, 0.45));
  /* 与毛玻璃卡区分，保证输入区底色肉眼可见 */
  background: color-mix(in srgb, #f8fafc 92%, var(--el-color-primary) 8%);
  font-size: 12px;
  font-weight: 600;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.dpk-search-input:focus {
  border-color: color-mix(in srgb, var(--el-color-primary) 38%, rgba(148, 163, 184, 0.35));
  background: #ffffff;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--el-color-primary) 12%, transparent);
}

@media (max-width: 720px) {
  .dpk-card-title--pickup-row .dpk-search-box--header {
    flex: 1 1 100%;
    order: 3;
  }

  .dpk-card-title--pickup-row .dpk-pending-label {
    margin-left: 0;
  }
}

.dpk-scroll-wrap {
  max-height: 290px;
  overflow-y: auto;
  border: 1px solid rgba(255, 255, 255, 0.55);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.32);
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
  background: rgba(241, 245, 249, 0.55);
  padding: 8px 12px;
  font-size: 10.5px;
  font-weight: 700;
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
  padding: 10px 12px;
  font-size: 12px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.65);
  font-weight: 600;
  vertical-align: middle;
}

.dpk-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.38);
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
  font-weight: 800;
  color: #0f172a;
  background: rgba(241, 245, 249, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.45);
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
  font-weight: 800;
  font-size: 12.5px;
  color: var(--el-color-primary-dark-2, #0d5c46);
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
  background: linear-gradient(
    145deg,
    color-mix(in srgb, var(--el-color-primary) 92%, #ffffff) 0%,
    var(--el-color-primary) 100%
  );
  color: #fff;
  border: 1px solid color-mix(in srgb, var(--el-color-primary) 35%, rgba(255, 255, 255, 0.5));
  padding: 5px 11px;
  border-radius: 9px;
  font-size: 10.5px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.35) inset;
}

.dpk-btn-verify:hover:not(:disabled) {
  box-shadow: 0 2px 10px color-mix(in srgb, var(--el-color-primary) 22%, transparent);
}

.dpk-btn-verify:disabled {
  background: rgba(203, 213, 225, 0.65);
  border-color: rgba(203, 213, 225, 0.85);
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
  gap: 0.55rem;
}

.dpk-kitchen-grid__title-row,
.dpk-kitchen-grid__row {
  display: grid;
  grid-template-columns: minmax(88px, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 0.75rem;
  align-items: center;
}

.dpk-kitchen-grid__title-row {
  /* 标题区与「今日日总份数」行之间多留一点呼吸感，避免头重脚轻 */
  /* padding-bottom 加大：横线（border-bottom）随之下移，与「午餐/晚餐」更分开 */
  padding-bottom: 0.58rem;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22);
  margin-bottom: 0.55rem;
}

.dpk-kitchen-grid__title-brand {
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.35;
  min-width: 0;
}

.dpk-kitchen-grid__col {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.06em;
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
  padding: 8px 10px;
  border-radius: 10px;
  /* 实底 + 清晰描边：避免与白底毛玻璃融成一团、看不出是可编辑数字 */
  border: 1px solid color-mix(in srgb, #64748b 32%, rgba(255, 255, 255, 0.55));
  font-size: 13px;
  font-weight: 800;
  font-family: var(--okfood-font-number, ui-sans-serif, system-ui, sans-serif);
  outline: none;
  background: color-mix(in srgb, #ffffff 94%, #3b82f6 6%);
  color: #0f172a;
  text-align: center;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.75) inset;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

/* 数字框：统一展示上下调节柄区域的可点击感（WebKit） */
.dpk-form-control::-webkit-outer-spin-button,
.dpk-form-control::-webkit-inner-spin-button {
  opacity: 0.85;
  height: 2rem;
}

.dpk-form-control:focus {
  border-color: color-mix(in srgb, #3b82f6 55%, #94a3b8);
  background: #ffffff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.85) inset,
    0 0 0 2px color-mix(in srgb, #3b82f6 18%, transparent);
}

.dpk-form-control--dinner {
  border-color: color-mix(in srgb, #7c3aed 28%, #94a3b8);
  background: color-mix(in srgb, #ffffff 94%, #7c3aed 6%);
}

.dpk-form-control--dinner:focus {
  border-color: color-mix(in srgb, #7c3aed 52%, #94a3b8);
  background: #ffffff;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.85) inset,
    0 0 0 2px color-mix(in srgb, #7c3aed 16%, transparent);
}

.dpk-unit {
  font-size: 13px;
  font-weight: 800;
  color: #64748b;
}

.dpk-btn-save {
  background: linear-gradient(
    145deg,
    color-mix(in srgb, #3b82f6 85%, #ffffff) 0%,
    #2563eb 100%
  );
  color: #fff;
  border: 1px solid rgba(191, 219, 254, 0.55);
  padding: 10px 18px;
  border-radius: 12px;
  font-size: 12.5px;
  font-weight: 700;
  cursor: pointer;
  transition: box-shadow 0.2s, opacity 0.2s;
  text-align: center;
  margin-top: auto;
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.35) inset,
    0 6px 18px rgba(37, 99, 235, 0.18);
}

.dpk-btn-save:hover:not(:disabled) {
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.45) inset,
    0 8px 22px rgba(37, 99, 235, 0.26);
}

.dpk-btn-save:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
