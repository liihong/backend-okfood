<script setup>
defineOptions({ name: 'WeeklyMenuView' })
import { computed, onMounted, ref, watch } from 'vue'
import { CornerDownRight, Info, X } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { useDayStockAdjustments } from '../composables/useDayStockAdjustments.js'
import DayStockAdjustmentModal from '../components/dashboard/DayStockAdjustmentModal.vue'

const mealPeriodTab = ref(/** @type {'lunch'|'dinner'} */ ('lunch'))

const DAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

/** 上海日历日 YYYY-MM-DD（与配送/财务业务日一致） */
function ymdInShanghai(date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)
  const map = Object.fromEntries(parts.filter((p) => p.type !== 'literal').map((p) => [p.type, p.value]))
  return `${map.year}-${map.month}-${map.day}`
}

function todayShanghaiYmd() {
  return ymdInShanghai(new Date())
}

/** week_start 当周周一 + (slot-1) 天 → 该槽位日历日 */
function slotCalendarYmd(row) {
  const raw = String(row.weekStart || '').trim().match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!raw) return todayShanghaiYmd()
  const base = new Date(`${raw[1]}-${raw[2]}-${raw[3]}T12:00:00+08:00`)
  const ms = base.getTime() + (Number(row.slot) - 1) * 86400000
  return ymdInShanghai(new Date(ms))
}

/** 早于今日（上海）的行不可改菜品、日总份（仍可查看） */
function isSlotRowPast(row) {
  return slotCalendarYmd(row) < todayShanghaiYmd()
}

const loading = ref(false)
const savingSlot = ref(null)
const cloning = ref(false)
const preview = ref(null)
const dishes = ref([])
/** 顶部说明横条是否展示 */
const bannerVisible = ref(true)
/** 日总份本地草稿 key=`weekStart|slot` */
const totalStockDraft = ref(/** @type {Record<string, string>} */ ({}))

const dishOptions = computed(() =>
  (dishes.value || []).map((d) => {
    const priceStr =
      d.single_order_price_yuan != null && String(d.single_order_price_yuan).trim() !== ''
        ? `¥${String(d.single_order_price_yuan).trim()}`
        : ''
    const priceHint = priceStr ? `（${priceStr}）` : '（未定价，会员端显示待公布）'
    return {
      value: d.id,
      label: d.is_enabled === false ? `${d.name}（已停用）` : `${d.name}${priceHint}`,
      disabled: d.is_enabled === false,
    }
  }),
)

function slotsToRows(slotList, weekStartIso) {
  const bySlot = Object.fromEntries((slotList || []).map((s) => [s.slot, s]))
  return [1, 2, 3, 4, 5, 6, 7].map((slot) => ({
    slot,
    weekday: DAY_LABELS[slot - 1],
    weekStart: weekStartIso,
    dish_id: bySlot[slot]?.dish_id ?? null,
    name: bySlot[slot]?.name ?? '',
    single_order_price_yuan: bySlot[slot]?.single_order_price_yuan ?? null,
    total_stock: bySlot[slot]?.total_stock ?? null,
    subscription_meals_for_day: bySlot[slot]?.subscription_meals_for_day ?? null,
    single_retail_paid_portions: bySlot[slot]?.single_retail_paid_portions ?? null,
    single_stock_remaining: bySlot[slot]?.single_stock_remaining ?? null,
    waste_total: bySlot[slot]?.waste_total ?? null,
  }))
}

/** @param {unknown} v */
function formatSlotPrice(v) {
  if (v == null) return '—'
  const s = String(v).trim()
  if (s === '') return '—'
  const n = Number(s)
  if (Number.isFinite(n)) {
    return `¥ ${n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }
  return `¥ ${s}`
}

const thisWeekRows = computed(() => {
  const p = preview.value
  if (!p || !p.this_week_start) return []
  return slotsToRows(p.this_week, p.this_week_start)
})

const nextWeekRows = computed(() => {
  const p = preview.value
  if (!p || !p.next_week_start) return []
  return slotsToRows(p.next_week, p.next_week_start)
})

/** @param {{ weekStart: string, slot: number }} row */
function totalStockKey(row) {
  return `${row.weekStart}|${row.slot}`
}

/**
 * @param {{ weekStart: string, slot: number, total_stock?: unknown }} row
 * @returns {string}
 */
function totalStockFieldValue(row) {
  const k = totalStockKey(row)
  if (Object.prototype.hasOwnProperty.call(totalStockDraft.value, k)) {
    return totalStockDraft.value[k] ?? ''
  }
  if (row.total_stock == null || row.total_stock === '') return ''
  return String(row.total_stock)
}

/**
 * @param {{ weekStart: string, slot: number }} row
 * @param {string} val
 */
function setTotalStockDraft(row, val) {
  const k = totalStockKey(row)
  totalStockDraft.value = { ...totalStockDraft.value, [k]: val }
}

/** 单次余展示文案 */
function remainingDisplay(row) {
  if (!row.dish_id) return '—'
  if (totalStockFieldValue(row) === '') return '0'
  const rem = row.single_stock_remaining
  if (rem == null || rem === '') return '0'
  return String(rem)
}

/** 单次余徽章样式：未配置 / 有余 / 售罄 */
function remainingBadgeClass(row) {
  if (!row.dish_id) return 'wmenu-remain--none'
  if (totalStockFieldValue(row) === '') return 'wmenu-remain--warn'
  const rem = row.single_stock_remaining
  if (rem == null || rem === '') return 'wmenu-remain--warn'
  const n = Number(rem)
  if (!Number.isFinite(n)) return 'wmenu-remain--none'
  if (n <= 0) return 'wmenu-remain--warn'
  return 'wmenu-remain--ok'
}

function deliverDisplay(row) {
  if (!row.dish_id) return '—'
  const v = row.subscription_meals_for_day
  if (v == null || v === '') return '—'
  return String(v)
}

/** 单次零售（已支付）份数展示 */
function singleRetailDisplay(row) {
  if (!row.dish_id) return '—'
  const v = row.single_retail_paid_portions
  if (v == null || v === '') return '—'
  return String(v)
}

/** 单次零售徽章：有单时高亮，便于核对避免漏单 */
function singleRetailBadgeClass(row) {
  if (!row.dish_id) return 'wmenu-retail--none'
  const v = row.single_retail_paid_portions
  if (v == null || v === '') return 'wmenu-retail--none'
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return 'wmenu-retail--zero'
  return 'wmenu-retail--active'
}

async function fetchDishes() {
  if (!adminAccessToken.value) return
  try {
    const data = await apiJson('/api/admin/dishes?lite=1', {}, { auth: true })
    dishes.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载菜品失败', 'error')
  }
}

async function loadPreview() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const qs = `?meal_period=${encodeURIComponent(mealPeriodTab.value)}`
    preview.value = await apiJson(`/api/admin/menu/weekly-slots${qs}`, {}, { auth: true })
    totalStockDraft.value = {}
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载周菜单失败', 'error')
    preview.value = null
  } finally {
    loading.value = false
  }
}

/**
 * @param {Record<string, unknown> & { weekStart: string, slot: number }} row
 * @param {unknown} dishId
 * @param {{ silent?: boolean }} [opts]
 */
async function onDishChange(row, dishId, opts = {}) {
  if (isSlotRowPast(row)) {
    if (!opts.silent) showToast('历史日期不可修改菜品', 'info')
    return
  }
  const key = `${row.weekStart}-${row.slot}`
  savingSlot.value = key
  try {
    await apiJson(
      '/api/admin/menu/weekly-slot',
      {
        method: 'POST',
        body: JSON.stringify({
          week_start: row.weekStart,
          slot: row.slot,
          dish_id: dishId == null || dishId === '' ? null : Number(dishId),
          meal_period: mealPeriodTab.value,
        }),
      },
      { auth: true },
    )
    if (!opts.silent) showToast('槽位已保存', 'success')
    if (!opts.silent) await loadPreview()
  } catch (e) {
    if (!opts.silent) showToast(e instanceof Error ? e.message : '保存失败', 'error')
    await loadPreview()
    throw e
  } finally {
    savingSlot.value = null
  }
}

/**
 * @param {Record<string, unknown> & { weekStart: string, slot: number, dish_id?: unknown, total_stock?: unknown }} row
 * @param {{ silent?: boolean, stockOverride?: string | null }} [opts]
 */
function buildTotalStockBody(row, opts = {}) {
  const s =
    opts.stockOverride !== undefined
      ? String(opts.stockOverride ?? '').trim()
      : String(totalStockFieldValue(row) ?? '').trim()
  const body = { week_start: row.weekStart, slot: row.slot, total_stock: null, meal_period: mealPeriodTab.value }
  if (s !== '' && s !== '—') {
    const n = Math.floor(Number(s))
    if (!Number.isFinite(n) || n < 0) return { error: '请输入非负整数或留空（不限）' }
    body.total_stock = n
  }
  return { body }
}

/**
 * 失焦或回车时提交日总份
 * @param {Record<string, unknown> & { weekStart: string, slot: number, dish_id?: unknown, total_stock?: unknown }} row
 * @param {{ silent?: boolean, stockOverride?: string | null }} [opts]
 */
async function onTotalStockCommit(row, opts = {}) {
  if (isSlotRowPast(row)) return
  if (!row.dish_id) {
    if (!opts.silent) showToast('请先选择菜品', 'error')
    return
  }
  const built = buildTotalStockBody(row, opts)
  if (built.error) {
    if (!opts.silent) showToast(built.error, 'error')
    return
  }
  const { body } = built
  const server = row.total_stock
  if (body.total_stock == null && (server == null || server === '')) return
  if (body.total_stock != null && server != null && Number(server) === body.total_stock) return

  const key = `${row.weekStart}-stock-${row.slot}`
  savingSlot.value = key
  try {
    await apiJson('/api/admin/menu/day-total-stock', { method: 'POST', body: JSON.stringify(body) }, { auth: true })
    if (!opts.silent) showToast('日总份数已保存', 'success')
    if (!opts.silent) await loadPreview()
  } catch (e) {
    if (!opts.silent) showToast(e instanceof Error ? e.message : '保存失败', 'error')
    await loadPreview()
    throw e
  } finally {
    savingSlot.value = null
  }
}

/** 读取本周槽位对应的日总份字符串（含草稿） */
function resolveTotalStockString(src) {
  if (Object.prototype.hasOwnProperty.call(totalStockDraft.value, totalStockKey(src))) {
    return totalStockFieldValue(src)
  }
  if (src.total_stock == null || src.total_stock === '') return ''
  return String(src.total_stock)
}

/** 一键将本周菜品与日总份复制到下周 */
async function cloneThisWeekToNext() {
  const srcRows = thisWeekRows.value
  const dstRows = nextWeekRows.value
  if (!srcRows.length || !dstRows.length) {
    showToast('菜单数据未就绪', 'error')
    return
  }
  if (!window.confirm('将本周一至周日的菜品与日总份复制到下周？已有下周配置会被覆盖。')) return

  cloning.value = true
  try {
    for (let i = 0; i < 7; i++) {
      const src = srcRows[i]
      const dst = dstRows[i]
      if (!src || !dst) continue

      await onDishChange(dst, src.dish_id, { silent: true })

      const stockStr = resolveTotalStockString(src)
      if (src.dish_id) {
        const built = buildTotalStockBody(dst, { stockOverride: stockStr })
        if (built.error) throw new Error(built.error)
        await apiJson(
          '/api/admin/menu/day-total-stock',
          { method: 'POST', body: JSON.stringify(built.body) },
          { auth: true },
        )
      }
    }
    await loadPreview()
    showToast('已成功将本周排程复制至下周', 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '复制失败', 'error')
    await loadPreview()
  } finally {
    cloning.value = false
    savingSlot.value = null
  }
}

function isRowBusy(row) {
  const k1 = `${row.weekStart}-${row.slot}`
  const k2 = `${row.weekStart}-stock-${row.slot}`
  return savingSlot.value === k1 || savingSlot.value === k2 || cloning.value
}

onMounted(() => {
  void fetchDishes()
  void loadPreview()
})

watch(mealPeriodTab, () => {
  void loadPreview()
})

const {
  modalOpen,
  modalMealPeriod,
  modalBusinessDate,
  modalDelta,
  modalReason,
  modalRemark,
  submitting: adjustSubmitting,
  openAdjustModal,
  submitAdjustment,
} = useDayStockAdjustments({ onSuccess: () => loadPreview() })

/** @param {{ weekStart: string, slot: number }} row */
function openRowAdjust(row) {
  openAdjustModal({ businessDate: slotCalendarYmd(row), mealPeriod: mealPeriodTab.value })
}
</script>

<template>
  <div class="wmenu-page tab-content animate-up page-content-shell" v-loading="loading">
    <!-- 提示横条：固定不随表格滚动 -->
    <div v-show="bannerVisible" class="wmenu-alert">
      <div class="wmenu-alert-content">
        <Info :size="18" stroke-width="2.5" aria-hidden="true" />
        <span>
          维护每周一至周日的固定槽位菜品（可与按日排期重复安排同一道菜）。日总份数：留空则单次卡不可售；填写后，单次可售
          = 总份数 − 应配送（订阅）− 单次零售（已支付）。「单次零售」列单独统计当日已付单次点餐份数，便于核对、避免漏单混淆。
          <strong>早于今日（上海时区）的日期已锁定，仅可查看。</strong>
        </span>
      </div>
      <button type="button" class="wmenu-alert-close" aria-label="关闭提示" @click="bannerVisible = false">
        <X :size="16" stroke-width="2.5" />
      </button>
    </div>

    <nav class="wmenu-period-tabs" aria-label="餐段切换">
      <button
        type="button"
        class="wmenu-period-tab"
        :class="{ 'wmenu-period-tab--active': mealPeriodTab === 'lunch' }"
        @click="mealPeriodTab = 'lunch'"
      >
        午餐
      </button>
      <button
        type="button"
        class="wmenu-period-tab"
        :class="{ 'wmenu-period-tab--active': mealPeriodTab === 'dinner' }"
        @click="mealPeriodTab = 'dinner'"
      >
        晚餐
      </button>
    </nav>

    <div v-if="preview" class="wmenu-schedule-scroll">
      <div class="wmenu-schedule-grid">
      <!-- 本周 -->
      <div class="wmenu-week-card">
        <div class="wmenu-week-card-header">
          <h3 class="wmenu-week-title">本周菜单配置</h3>
          <div class="wmenu-date-badge">
            起：<span>{{ preview.this_week_start }}</span>
          </div>
        </div>
        <div class="wmenu-table-scroll">
          <table class="wmenu-table">
            <thead>
              <tr>
                <th>星期</th>
                <th>单点价</th>
                <th>日总份数</th>
                <th>单次零售</th>
                <th>应配送</th>
                <th>损耗</th>
                <th>剩余</th>
                <th>操作</th>
                <th>菜品</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in thisWeekRows"
                :key="`this-${row.slot}`"
                :class="{ 'wmenu-row--past': isSlotRowPast(row) }"
              >
                <td>
                  <span
                    class="wmenu-day-label"
                    :class="[
                      `wmenu-day-tone--${row.slot}`,
                      { 'wmenu-day-label--past': isSlotRowPast(row) },
                    ]"
                  >
                    {{ row.weekday }}
                  </span>
                </td>
                <td>
                  <span
                    class="wmenu-price"
                    :class="{
                      'wmenu-price--missing':
                        row.dish_id &&
                        (!row.single_order_price_yuan || !String(row.single_order_price_yuan).trim()),
                    }"
                  >
                    {{ row.dish_id ? formatSlotPrice(row.single_order_price_yuan) : '—' }}
                  </span>
                </td>
                <td>
                  <input
                    v-if="row.dish_id"
                    type="number"
                    min="0"
                    class="wmenu-total-input"
                    placeholder="留空=不限"
                    :value="totalStockFieldValue(row)"
                    :disabled="isRowBusy(row) || isSlotRowPast(row)"
                    @input="(e) => setTotalStockDraft(row, (e.target).value)"
                    @blur="() => onTotalStockCommit(row)"
                  />
                  <span v-else class="wmenu-dash">—</span>
                </td>
                <td>
                  <span class="wmenu-retail-badge" :class="singleRetailBadgeClass(row)">
                    {{ singleRetailDisplay(row) }}
                  </span>
                </td>
                <td>
                  <span class="wmenu-deliver-badge">{{ deliverDisplay(row) }}</span>
                </td>
                <td>{{ row.waste_total != null ? row.waste_total : '—' }}</td>
                <td>
                  <span class="wmenu-remain-badge" :class="remainingBadgeClass(row)">
                    {{ remainingDisplay(row) }}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    class="wmenu-adjust-btn"
                    :disabled="!row.dish_id || isSlotRowPast(row)"
                    @click="openRowAdjust(row)"
                  >
                    报损耗
                  </button>
                </td>
                <td>
                  <el-select
                    :model-value="row.dish_id"
                    filterable
                    clearable
                    placeholder="选择菜品"
                    class="wmenu-dish-select"
                    :loading="savingSlot === `${row.weekStart}-${row.slot}`"
                    :disabled="isRowBusy(row) || isSlotRowPast(row)"
                    @update:model-value="(v) => onDishChange(row, v)"
                  >
                    <el-option
                      v-for="opt in dishOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                      :disabled="opt.disabled"
                    />
                  </el-select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 下周 -->
      <div class="wmenu-week-card">
        <div class="wmenu-week-card-header">
          <h3 class="wmenu-week-title">下周菜单配置</h3>
          <div class="wmenu-week-header-actions">
            <button
              type="button"
              class="wmenu-btn-sync"
              :disabled="loading || cloning || !thisWeekRows.length"
              @click="cloneThisWeekToNext"
            >
              <CornerDownRight :size="14" stroke-width="2.5" aria-hidden="true" />
              {{ cloning ? '复制中…' : '一键复制本周菜单' }}
            </button>
            <div class="wmenu-date-badge">
              起：<span>{{ preview.next_week_start }}</span>
            </div>
          </div>
        </div>
        <div class="wmenu-table-scroll">
          <table class="wmenu-table">
            <thead>
              <tr>
                <th>星期</th>
                <th>单点价</th>
                <th>日总份数</th>
                <th>单次零售</th>
                <th>应配送</th>
                <th>损耗</th>
                <th>剩余</th>
                <th>操作</th>
                <th>菜品</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in nextWeekRows"
                :key="`next-${row.slot}`"
                :class="{ 'wmenu-row--past': isSlotRowPast(row) }"
              >
                <td>
                  <span
                    class="wmenu-day-label"
                    :class="[
                      `wmenu-day-tone--${row.slot}`,
                      { 'wmenu-day-label--past': isSlotRowPast(row) },
                    ]"
                  >
                    {{ row.weekday }}
                  </span>
                </td>
                <td>
                  <span
                    class="wmenu-price"
                    :class="{
                      'wmenu-price--missing':
                        row.dish_id &&
                        (!row.single_order_price_yuan || !String(row.single_order_price_yuan).trim()),
                    }"
                  >
                    {{ row.dish_id ? formatSlotPrice(row.single_order_price_yuan) : '—' }}
                  </span>
                </td>
                <td>
                  <input
                    v-if="row.dish_id"
                    type="number"
                    min="0"
                    class="wmenu-total-input"
                    placeholder="留空=不限"
                    :value="totalStockFieldValue(row)"
                    :disabled="isRowBusy(row) || isSlotRowPast(row)"
                    @input="(e) => setTotalStockDraft(row, (e.target).value)"
                    @blur="() => onTotalStockCommit(row)"
                  />
                  <span v-else class="wmenu-dash">—</span>
                </td>
                <td>
                  <span class="wmenu-retail-badge" :class="singleRetailBadgeClass(row)">
                    {{ singleRetailDisplay(row) }}
                  </span>
                </td>
                <td>
                  <span class="wmenu-deliver-badge">{{ deliverDisplay(row) }}</span>
                </td>
                <td>{{ row.waste_total != null ? row.waste_total : '—' }}</td>
                <td>
                  <span class="wmenu-remain-badge" :class="remainingBadgeClass(row)">
                    {{ remainingDisplay(row) }}
                  </span>
                </td>
                <td>
                  <button
                    type="button"
                    class="wmenu-adjust-btn"
                    :disabled="!row.dish_id || isSlotRowPast(row)"
                    @click="openRowAdjust(row)"
                  >
                    报损耗
                  </button>
                </td>
                <td>
                  <el-select
                    :model-value="row.dish_id"
                    filterable
                    clearable
                    placeholder="选择菜品"
                    class="wmenu-dish-select"
                    :loading="savingSlot === `${row.weekStart}-${row.slot}`"
                    :disabled="isRowBusy(row) || isSlotRowPast(row)"
                    @update:model-value="(v) => onDishChange(row, v)"
                  >
                    <el-option
                      v-for="opt in dishOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                      :disabled="opt.disabled"
                    />
                  </el-select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      </div>
    </div>
  </div>

  <DayStockAdjustmentModal
    :open="modalOpen"
    :meal-period="modalMealPeriod"
    :business-date="modalBusinessDate"
    :delta="modalDelta"
    :reason="modalReason"
    :remark="modalRemark"
    :submitting="adjustSubmitting"
    @update:open="(v) => (modalOpen = v)"
    @update:delta="(v) => (modalDelta = v)"
    @update:reason="(v) => (modalReason = v)"
    @update:remark="(v) => (modalRemark = v)"
    @submit="submitAdjustment"
  />
</template>

<style scoped>
.wmenu-page.page-content-shell {
  /* 抵消 main-body 水平 padding，双表尽量沾满内容区宽度 */
  margin-left: -1rem;
  margin-right: -1rem;
  width: calc(100% + 2rem);
  box-sizing: border-box;
  padding-bottom: 0.75rem;
}

@media (max-width: 900px) {
  .wmenu-page.page-content-shell {
    margin-left: 0;
    margin-right: 0;
    width: 100%;
  }
}

.wmenu-page {
  --wmenu-primary: #0d5c46;
  --wmenu-primary-hover: #0a4635;
  --wmenu-border: #eaedf1;
  --wmenu-muted: #64748b;
  --wmenu-info-bg: #f0fdf4;
  --wmenu-info-text: #166534;
  --wmenu-info-border: #bbf7d0;
  --wmenu-danger-bg: #fef2f2;
  --wmenu-danger-text: #ef4444;
  --wmenu-blue: #3b82f6;
  --wmenu-blue-bg: #eff6ff;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wmenu-alert {
  background: var(--wmenu-info-bg);
  border: 1px solid var(--wmenu-info-border);
  border-radius: 20px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.wmenu-alert-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--wmenu-info-text);
  line-height: 1.6;
}

.wmenu-alert-content svg {
  flex-shrink: 0;
  color: var(--wmenu-primary);
  margin-top: 2px;
}

.wmenu-alert-close {
  background: transparent;
  border: none;
  color: var(--wmenu-muted);
  cursor: pointer;
  padding: 4px;
  opacity: 0.5;
  flex-shrink: 0;
}

.wmenu-alert-close:hover {
  opacity: 1;
}

/* 本周/下周整块：仅占满剩余视口的滚动区（提示横条不参与滚动） */
.wmenu-schedule-scroll {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding-right: 4px;
}

.wmenu-schedule-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 1300px) {
  .wmenu-schedule-grid {
    grid-template-columns: 1fr;
  }
}

.wmenu-week-card {
  background: #fff;
  border-radius: 32px;
  border: 1px solid var(--wmenu-border);
  padding: 24px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.wmenu-week-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--wmenu-border);
}

.wmenu-week-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}

.wmenu-week-header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.wmenu-date-badge {
  background: #f1f5f9;
  border: 1px solid var(--wmenu-border);
  border-radius: 12px;
  padding: 6px 14px;
  font-size: 11px;
  font-weight: 800;
  color: var(--wmenu-muted);
  white-space: nowrap;
}

.wmenu-date-badge span {
  color: #0f172a;
}

.wmenu-btn-sync {
  background: var(--wmenu-blue-bg);
  color: var(--wmenu-blue);
  border: 1px solid rgba(59, 130, 246, 0.2);
  padding: 8px 16px;
  border-radius: 12px;
  font-size: 11.5px;
  font-weight: 800;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}

.wmenu-btn-sync:hover:not(:disabled) {
  background: var(--wmenu-blue);
  color: #fff;
  box-shadow: 0 4px 10px -2px rgba(59, 130, 246, 0.25);
}

.wmenu-btn-sync:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.wmenu-table-scroll {
  width: 100%;
  overflow-x: auto;
}

.wmenu-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.wmenu-table th {
  color: var(--wmenu-muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 12px 14px;
  border-bottom: 2px solid var(--wmenu-border);
  white-space: nowrap;
}

.wmenu-table td {
  padding: 14px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--wmenu-border);
  vertical-align: middle;
  color: #0f172a;
}

.wmenu-table tbody tr:hover {
  background: #f8fafc;
}

.wmenu-day-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: #f1f5f9;
  font-size: 12.5px;
  font-weight: 800;
}

.wmenu-day-label--alt {
  background: #e2e8f0;
}

.wmenu-price {
  font-family: var(--okfood-font-number);
  font-size: 13.5px;
  font-weight: 700;
}

.wmenu-price--missing {
  color: var(--wmenu-danger-text);
}

.wmenu-total-input {
  width: 84px;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid var(--wmenu-border);
  background: #f8fafc;
  text-align: center;
  font-weight: 700;
  font-size: 13px;
  outline: none;
  transition: all 0.2s;
}

.wmenu-total-input:focus {
  border-color: var(--wmenu-primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 92, 70, 0.06);
}

.wmenu-total-input::placeholder {
  color: #cbd5e1;
  font-size: 11px;
}

.wmenu-total-input:disabled {
  opacity: 0.65;
}

.wmenu-dash {
  color: var(--wmenu-muted);
}

.wmenu-deliver-badge {
  background: #f1f5f9;
  color: #0f172a;
  font-family: var(--okfood-font-number);
  font-weight: 700;
  padding: 6px 12px;
  border-radius: 8px;
  display: inline-block;
  min-width: 44px;
  text-align: center;
}

.wmenu-retail-badge {
  font-family: var(--okfood-font-number);
  font-weight: 800;
  padding: 6px 12px;
  border-radius: 8px;
  display: inline-block;
  min-width: 44px;
  text-align: center;
}

.wmenu-retail--none {
  background: #f1f5f9;
  color: var(--wmenu-muted);
}

.wmenu-retail--zero {
  background: #f8fafc;
  color: #94a3b8;
  border: 1px solid var(--wmenu-border);
}

.wmenu-retail--active {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid rgba(249, 115, 22, 0.2);
}

.wmenu-remain-badge {
  font-family: var(--okfood-font-number);
  font-weight: 800;
  padding: 6px 12px;
  border-radius: 8px;
  display: inline-block;
  min-width: 44px;
  text-align: center;
}

.wmenu-remain--none {
  background: #f1f5f9;
  color: var(--wmenu-muted);
  border: 1px solid transparent;
}

.wmenu-remain--ok {
  background: #ecfdf5;
  color: var(--wmenu-primary);
  border: 1px solid rgba(16, 185, 129, 0.15);
}

.wmenu-remain--warn {
  background: var(--wmenu-danger-bg);
  color: var(--wmenu-danger-text);
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.wmenu-dish-select {
  width: 100%;
  min-width: 170px;
}

.wmenu-dish-select :deep(.el-select__wrapper) {
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid var(--wmenu-border);
  background: #f8fafc;
  font-size: 12.5px;
  font-weight: 700;
  box-shadow: none;
  min-height: 40px;
}

.wmenu-dish-select :deep(.el-select__wrapper.is-focused) {
  border-color: var(--wmenu-primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 92, 70, 0.06);
}

.wmenu-dish-select :deep(.el-select__placeholder) {
  color: #94a3b8;
  font-weight: 700;
}

.wmenu-period-tabs {
  display: flex;
  gap: 8px;
  margin: 12px 1rem 0;
}
.wmenu-period-tab {
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 999px;
  padding: 6px 16px;
  font-size: 13px;
  cursor: pointer;
}
.wmenu-period-tab--active {
  background: #059669;
  border-color: #059669;
  color: #fff;
}
.wmenu-adjust-btn {
  border: 1px solid #fecaca;
  background: #fff7ed;
  color: #c2410c;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}
.wmenu-adjust-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
