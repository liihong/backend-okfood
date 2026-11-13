<script setup>
defineOptions({ name: 'WeeklyMenuView' })
import { computed, onMounted, ref } from 'vue'
import { apiJson, adminAccessToken, dishImageDisplayUrl, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import PrepMenuDialog from './prep/PrepMenuDialog.vue'
import WeeklySlotPackagingDialog from './packaging/WeeklySlotPackagingDialog.vue'
import { listSlotPackagingUsage } from '../api/packaging/recipe.js'

/** 午餐、晚餐双预览（一次加载两组餐段） */
const previewLunch = ref(null)
const previewDinner = ref(null)

const DAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

const loading = ref(false)
const savingSlot = ref(null)
const dishes = ref([])
const drinks = ref([])
const drinksLoading = ref(false)
/** 日总份本地草稿 key=`weekStart|slot` */
const totalStockDraft = ref(/** @type {Record<string, string>} */ ({}))

const dishOptions = computed(() =>
  (dishes.value || []).map((d) => {
    const priceStr =
      d.single_order_price_yuan != null && String(d.single_order_price_yuan).trim() !== ''
        ? `¥${String(d.single_order_price_yuan).trim()}`
        : ''
    const priceHint = priceStr ? `（${priceStr}）` : '（未定价，会员端显示待公布）'
    const name = d.is_enabled === false ? `${d.name}（已停用）` : d.name
    return {
      value: d.id,
      name,
      price: priceStr,
      image: dishImageDisplayUrl(d.image_url),
      label: `${name}${priceHint}`,
      disabled: d.is_enabled === false,
    }
  }),
)

/** 已选菜品：收起状态下按 id 取小图和菜名 */
const dishOptionById = computed(() =>
  Object.fromEntries(dishOptions.value.map((opt) => [opt.value, opt])),
)

/** 图片地址失效时收成灰块，避免裂图把下拉撑乱 */
function onDishThumbError(event) {
  const img = event.target
  if (!(img instanceof HTMLImageElement)) return
  img.removeAttribute('src')
}

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
    single_retail_paid_portions: bySlot[slot]?.single_retail_paid_portions ?? null,
    single_stock_remaining: bySlot[slot]?.single_stock_remaining ?? null,
    paired_drink_id: bySlot[slot]?.paired_drink_id ?? null,
    paired_drink_name: bySlot[slot]?.paired_drink_name ?? '',
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

/** @typedef {'this' | 'next'} WeekTabKey */

/** 当前查看的周：本周 / 下周 */
const activeWeekTab = ref(/** @type {WeekTabKey} */ ('this'))

/** 开菜单只读本周排菜，不回写日总份 */
const prepMenuOpen = ref(false)
/** 槽位是否已设用盒。加载失败时保持空，不挡住周菜单。 */
const slotBoxUsage = ref(/** @type {Record<string, boolean>} */ ({}))
const packagingDialog = ref({
  open: false,
  weekStart: '',
  slot: 1,
  mealPeriod: 'lunch',
  dishName: '',
})

/** 从预览中取指定周的行数据 */
function rowsForPreview(preview, weekKey = 'this') {
  if (!preview) return []
  const weekStart = weekKey === 'next' ? preview.next_week_start : preview.this_week_start
  const slotList = weekKey === 'next' ? preview.next_week : preview.this_week
  if (!weekStart) return []
  return slotsToRows(slotList, weekStart)
}

const lunchRows = computed(() => rowsForPreview(previewLunch.value, activeWeekTab.value))
const dinnerRows = computed(() => rowsForPreview(previewDinner.value, activeWeekTab.value))

/** 启用中的饮品；当前已选但已停用的仍留在列表里 */
const drinkOptions = computed(() => {
  const options = (drinks.value || [])
    .filter((drink) => drink.is_enabled !== false)
    .map((drink) => ({
      value: Number(drink.id),
      label: String(drink.name || '').trim() || `饮品 #${drink.id}`,
    }))
  const known = new Set(options.map((item) => item.value))
  for (const row of [...lunchRows.value, ...dinnerRows.value]) {
    const id = row.paired_drink_id
    if (id != null && !known.has(Number(id))) {
      known.add(Number(id))
      options.unshift({
        value: Number(id),
        label: row.paired_drink_name || `饮品 #${id}`,
      })
    }
  }
  return options
})

/** 当前 Tab 对应的 week_start（用于卡片日期徽章、开菜单） */
const activeWeekStart = computed(() => {
  const p = previewLunch.value || previewDinner.value
  if (!p) return ''
  return activeWeekTab.value === 'next' ? p.next_week_start || '' : p.this_week_start || ''
})

/**
 * 周一起始的 ISO 日期，按本地日历解析，避免时区把日期挤到前一天。
 * @param {string} iso
 * @returns {Date | null}
 */
function parseWeekStart(iso) {
  const matched = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || '').trim())
  if (!matched) return null
  return new Date(Number(matched[1]), Number(matched[2]) - 1, Number(matched[3]))
}

/**
 * 供餐周固定周一到周日，结尾是起始日加 6 天。
 * @param {string} weekStart
 * @returns {{ start: Date, end: Date } | null}
 */
function weekRange(weekStart) {
  const start = parseWeekStart(weekStart)
  if (!start) return null
  const end = new Date(start.getTime())
  end.setDate(end.getDate() + 6)
  return { start, end }
}

/** @param {Date} date */
function formatMonthDay(date) {
  return `${date.getMonth() + 1}月${date.getDate()}日`
}

/** 卡片标题行：11月9日 - 11月15日 */
function weekCardRangeText(weekStart) {
  const range = weekRange(weekStart)
  if (!range) return ''
  return `${formatMonthDay(range.start)} - ${formatMonthDay(range.end)}`
}

/** 只有当前选中的那一周把日期写进按钮，另一周只留名称 */
const weekTabOptions = computed(() => {
  const p = previewLunch.value || previewDinner.value
  const tabs = [
    { key: /** @type {WeekTabKey} */ ('this'), label: '本周菜单', weekStart: p?.this_week_start || '' },
    { key: /** @type {WeekTabKey} */ ('next'), label: '下周菜单', weekStart: p?.next_week_start || '' },
  ]
  return tabs.map((tab) => {
    if (tab.key !== activeWeekTab.value) return tab
    const range = weekCardRangeText(tab.weekStart)
    return range ? { ...tab, label: `${tab.label} ${range}` } : tab
  })
})

/** @param {{ weekStart: string, slot: number }} row @param {'lunch'|'dinner'} mealPeriod */
function totalStockKey(row, mealPeriod) {
  return `${mealPeriod}|${row.weekStart}|${row.slot}`
}

/**
 * @param {{ weekStart: string, slot: number, total_stock?: unknown }} row
 * @returns {string}
 */
/** @param {'lunch'|'dinner'} mealPeriod */
function totalStockFieldValue(row, mealPeriod) {
  const k = totalStockKey(row, mealPeriod)
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
/** @param {'lunch'|'dinner'} mealPeriod */
function setTotalStockDraft(row, val, mealPeriod) {
  const k = totalStockKey(row, mealPeriod)
  totalStockDraft.value = { ...totalStockDraft.value, [k]: val }
}

/** 单次余展示文案 @param {'lunch'|'dinner'} mealPeriod */
function remainingDisplay(row, mealPeriod) {
  if (!row.dish_id) return '—'
  if (totalStockFieldValue(row, mealPeriod) === '') return '0'
  const rem = row.single_stock_remaining
  if (rem == null || rem === '') return '0'
  return String(rem)
}

/** 单次余徽章样式：未配置 / 有余 / 售罄 @param {'lunch'|'dinner'} mealPeriod */
function remainingBadgeClass(row, mealPeriod) {
  if (!row.dish_id) return 'wmenu-remain--none'
  if (totalStockFieldValue(row, mealPeriod) === '') return 'wmenu-remain--warn'
  const rem = row.single_stock_remaining
  if (rem == null || rem === '') return 'wmenu-remain--warn'
  const n = Number(rem)
  if (!Number.isFinite(n)) return 'wmenu-remain--none'
  if (n <= 0) return 'wmenu-remain--warn'
  return 'wmenu-remain--ok'
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
    // 不用 lite：当前接口的精简列表不带图片地址，下拉缩略图需要 image_url
    const data = await apiJson('/api/admin/dishes', {}, { auth: true })
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

async function fetchDrinks() {
  if (!adminAccessToken.value) return
  drinksLoading.value = true
  try {
    const data = await apiJson('/api/admin/drinks', {}, { auth: true })
    drinks.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    drinks.value = []
    showToast(e instanceof Error ? e.message : '加载饮品失败', 'error')
  } finally {
    drinksLoading.value = false
  }
}

async function loadPreview() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const [lunch, dinner] = await Promise.all([
      apiJson('/api/admin/menu/weekly-slots?meal_period=lunch', {}, { auth: true }),
      apiJson('/api/admin/menu/weekly-slots?meal_period=dinner', {}, { auth: true }),
    ])
    previewLunch.value = lunch
    previewDinner.value = dinner
    totalStockDraft.value = {}
    await loadSlotBoxUsage()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载周菜单失败', 'error')
    previewLunch.value = null
    previewDinner.value = null
  } finally {
    loading.value = false
  }
}

/**
 * @param {Record<string, unknown> & { weekStart: string, slot: number }} row
 * @param {unknown} dishId
 * @param {'lunch'|'dinner'} mealPeriod
 * @param {{ silent?: boolean }} [opts]
 */
async function onDishChange(row, dishId, mealPeriod, opts = {}) {
  const key = `${mealPeriod}-${row.weekStart}-${row.slot}`
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
          meal_period: mealPeriod,
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
 * 给这一天这一餐配随餐饮。不改菜品。
 * 保存请求返回并写回当前格之后再提示，不再整页重拉周菜单。
 * @param {Record<string, unknown> & { weekStart: string, slot: number, dish_id?: unknown }} row
 * @param {unknown} drinkId
 * @param {'lunch'|'dinner'} mealPeriod
 */
async function onDrinkChange(row, drinkId, mealPeriod) {
  if (!row.dish_id) {
    showToast('请先选择菜品', 'error')
    return
  }
  const key = `${mealPeriod}-${row.weekStart}-${row.slot}`
  const nextId = drinkId == null || drinkId === '' ? null : Number(drinkId)
  savingSlot.value = key
  try {
    await apiJson(
      '/api/admin/menu/weekly-slot',
      {
        method: 'POST',
        body: JSON.stringify({
          week_start: row.weekStart,
          slot: row.slot,
          dish_id: Number(row.dish_id),
          meal_period: mealPeriod,
          paired_drink_id: nextId,
        }),
      },
      { auth: true },
    )
    applySlotDrink(row, mealPeriod, nextId)
    showToast('随餐饮已保存', 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存随餐饮失败', 'error')
  } finally {
    savingSlot.value = null
  }
}

/** 把刚保存的饮品写回当前周的这一格，避免再请求整周库存。 */
function applySlotDrink(row, mealPeriod, drinkId) {
  const preview = mealPeriod === 'dinner' ? previewDinner : previewLunch
  const data = preview.value
  if (!data) return
  const listKey = activeWeekTab.value === 'next' ? 'next_week' : 'this_week'
  const list = Array.isArray(data[listKey]) ? data[listKey] : []
  const slot = list.find((item) => Number(item.slot) === Number(row.slot))
  if (!slot) return
  const opt = drinkOptions.value.find((item) => item.value === drinkId)
  slot.paired_drink_id = drinkId
  slot.paired_drink_name = drinkId == null ? '' : opt?.label || ''
}

/**
 * @param {Record<string, unknown> & { weekStart: string, slot: number, dish_id?: unknown, total_stock?: unknown }} row
 * @param {'lunch'|'dinner'} mealPeriod
 * @param {{ silent?: boolean, stockOverride?: string | null }} [opts]
 */
function buildTotalStockBody(row, mealPeriod, opts = {}) {
  const s =
    opts.stockOverride !== undefined
      ? String(opts.stockOverride ?? '').trim()
      : String(totalStockFieldValue(row, mealPeriod) ?? '').trim()
  const body = {
    week_start: row.weekStart,
    slot: row.slot,
    total_stock: null,
    // 必传：lunch=午餐槽 / dinner=晚餐槽；与营业概览 today_menu_day_total_stock / today_dinner_menu_day_total_stock 一一对应
    meal_period: mealPeriod,
  }
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
 * @param {'lunch'|'dinner'} mealPeriod
 * @param {{ silent?: boolean, stockOverride?: string | null }} [opts]
 */
async function onTotalStockCommit(row, mealPeriod, opts = {}) {
  if (!row.dish_id) {
    if (!opts.silent) showToast('请先选择菜品', 'error')
    return
  }
  const built = buildTotalStockBody(row, mealPeriod, opts)
  if (built.error) {
    if (!opts.silent) showToast(built.error, 'error')
    return
  }
  const { body } = built
  const server = row.total_stock
  if (body.total_stock == null && (server == null || server === '')) return
  if (body.total_stock != null && server != null && Number(server) === body.total_stock) return

  const key = `${mealPeriod}-${row.weekStart}-stock-${row.slot}`
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

/** @param {'lunch'|'dinner'} mealPeriod */
function isRowBusy(row, mealPeriod) {
  const k1 = `${mealPeriod}-${row.weekStart}-${row.slot}`
  const k2 = `${mealPeriod}-${row.weekStart}-stock-${row.slot}`
  return savingSlot.value === k1 || savingSlot.value === k2
}

async function loadSlotBoxUsage() {
  const preview = previewLunch.value || previewDinner.value
  const starts = [preview?.this_week_start, preview?.next_week_start].filter(Boolean)
  if (!starts.length) {
    slotBoxUsage.value = {}
    return
  }
  const next = {}
  for (const weekStart of starts) {
    try {
      const rows = await listSlotPackagingUsage(weekStart)
      for (const row of rows || []) {
        next[`${row.meal_period}|${weekStart}|${row.slot}`] = !!row.has_boxes
      }
    } catch {
      /* 用盒接口不可用时，周菜单仍按原样展示 */
    }
  }
  slotBoxUsage.value = next
}

function slotHasBoxes(row, mealPeriod) {
  return !!slotBoxUsage.value[`${mealPeriod}|${row.weekStart}|${row.slot}`]
}

function openSlotPackaging(row, mealPeriod) {
  if (!row.dish_id) {
    showToast('请先选择菜品', 'error')
    return
  }
  packagingDialog.value = {
    open: true,
    weekStart: row.weekStart,
    slot: row.slot,
    mealPeriod,
    dishName: row.name || '',
  }
}

onMounted(() => {
  void fetchDishes()
  void fetchDrinks()
  void loadPreview()
})

/** 一天一张卡片。平时只排周一到周六；周日已经有菜时才补出来，避免空卡片。 */
const dayCards = computed(() => {
  const lunchBySlot = new Map(lunchRows.value.map((row) => [row.slot, row]))
  const dinnerBySlot = new Map(dinnerRows.value.map((row) => [row.slot, row]))
  const cards = [1, 2, 3, 4, 5, 6, 7]
    .map((slot) => {
      const lunch = lunchBySlot.get(slot)
      const dinner = dinnerBySlot.get(slot)
      const sample = lunch || dinner
      if (!sample) return null
      const meals = [
        lunch ? { key: 'lunch', label: '午餐', mealPeriod: 'lunch', row: lunch } : null,
        dinner ? { key: 'dinner', label: '晚餐', mealPeriod: 'dinner', row: dinner } : null,
      ].filter(Boolean)
      return { slot, weekday: sample.weekday, meals }
    })
    .filter(Boolean)
  return cards.filter((day) => day.slot <= 6 || day.meals.some((meal) => meal.row?.dish_id))
})

const hasPreview = computed(() => previewLunch.value != null || previewDinner.value != null)
</script>

<template>
  <section class="mkt-page wmenu-page tab-content animate-up page-content-shell" v-loading="loading">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">菜单管理</p>
        <h1 class="mkt-title">本周菜单</h1>
        <p class="mkt-intro">周一到周六各一张卡片，卡片里排午餐和晚餐。开菜单里改的份数不会写回这里。</p>
      </div>
      <el-button type="primary" round @click="prepMenuOpen = true">开菜单</el-button>
    </header>
    <div v-if="hasPreview" class="wmenu-pills-row">
      <div class="wmenu-pills">
        <button
          v-for="tab in weekTabOptions"
          :key="tab.key"
          type="button"
          class="wmenu-pill"
          :class="{ 'is-on': activeWeekTab === tab.key }"
          @click="activeWeekTab = tab.key"
        >
          <span class="wmenu-pill__text">{{ tab.label }}</span>
        </button>
      </div>
    </div>
    <PrepMenuDialog v-model="prepMenuOpen" :week-start="activeWeekStart" />
    <WeeklySlotPackagingDialog
      v-model="packagingDialog.open"
      :week-start="packagingDialog.weekStart"
      :slot="packagingDialog.slot"
      :meal-period="packagingDialog.mealPeriod"
      :dish-name="packagingDialog.dishName"
      @saved="loadSlotBoxUsage"
    />
    <div v-if="hasPreview" class="wmenu-schedule-scroll">
      <div class="wmenu-day-grid">
        <article v-for="day in dayCards" :key="day.slot" class="wmenu-day-card">
          <header class="wmenu-day-card__head">
            <h3 class="wmenu-day-card__title">{{ day.weekday }}</h3>
          </header>
          <section
            v-for="meal in day.meals"
            :key="`${day.slot}-${meal.key}`"
            class="wmenu-meal"
          >
            <div class="wmenu-meal__head">
              <span class="wmenu-meal-tag" :class="`wmenu-meal-tag--${meal.key}`">{{ meal.label }}</span>
              <span
                class="wmenu-price"
                :class="{
                  'wmenu-price--missing':
                    meal.row.dish_id &&
                    (!meal.row.single_order_price_yuan || !String(meal.row.single_order_price_yuan).trim()),
                }"
              >
                {{ meal.row.dish_id ? formatSlotPrice(meal.row.single_order_price_yuan) : '—' }}
              </span>
              <span class="wmenu-meal__stats">
                <span class="wmenu-meta-label">零售</span>
                <span class="wmenu-retail-badge" :class="singleRetailBadgeClass(meal.row)">
                  {{ singleRetailDisplay(meal.row) }}
                </span>
                <span class="wmenu-meta-label">剩余</span>
                <span class="wmenu-remain-badge" :class="remainingBadgeClass(meal.row, meal.mealPeriod)">
                  {{ remainingDisplay(meal.row, meal.mealPeriod) }}
                </span>
              </span>
              <el-button
                v-if="meal.row.dish_id"
                link
                class="wmenu-box-flag"
                :type="slotHasBoxes(meal.row, meal.mealPeriod) ? 'primary' : 'danger'"
                @click="openSlotPackaging(meal.row, meal.mealPeriod)"
              >
                {{ slotHasBoxes(meal.row, meal.mealPeriod) ? '用盒' : '未设用盒' }}
              </el-button>
            </div>
            <div class="wmenu-meal__body">
            <div class="wmenu-dish-cell">
                      <el-select
                        :model-value="meal.row.dish_id"
                        filterable
                        clearable
                        placeholder="选择菜品"
                        class="wmenu-dish-select"
                        popper-class="wmenu-dish-popper"
                        :fit-input-width="false"
                        :loading="savingSlot === `${meal.mealPeriod}-${meal.row.weekStart}-${meal.row.slot}`"
                        :disabled="isRowBusy(meal.row, meal.mealPeriod)"
                        @update:model-value="(v) => onDishChange(meal.row, v, meal.mealPeriod)"
                      >
                        <template #label="{ value }">
                          <span class="wmenu-dish-picked">
                            <img
                              v-if="dishOptionById[value]?.image"
                              :src="dishOptionById[value].image"
                              alt=""
                              class="wmenu-dish-picked__img"
                              @error="onDishThumbError"
                            />
                            <span v-else class="wmenu-dish-picked__img wmenu-dish-picked__img--empty" />
                            <span class="wmenu-dish-picked__name">{{ dishOptionById[value]?.name || '' }}</span>
                          </span>
                        </template>
                        <el-option
                          v-for="opt in dishOptions"
                          :key="opt.value"
                          :label="opt.label"
                          :value="opt.value"
                          :disabled="opt.disabled"
                        >
                          <div class="wmenu-dish-opt">
                            <img
                              v-if="opt.image"
                              :src="opt.image"
                              alt=""
                              class="wmenu-dish-opt__img"
                              @error="onDishThumbError"
                            />
                            <span v-else class="wmenu-dish-opt__img wmenu-dish-opt__img--empty" />
                            <span class="wmenu-dish-opt__name">{{ opt.name }}</span>
                            <span v-if="opt.price" class="wmenu-dish-opt__price">{{ opt.price }}</span>
                          </div>
                        </el-option>
                      </el-select>
                    </div>
            <label class="wmenu-stock">
                <input
                  v-if="meal.row.dish_id"
                  type="number"
                  min="0"
                  class="wmenu-total-input"
                  placeholder="不限"
                  :value="totalStockFieldValue(meal.row, meal.mealPeriod)"
                  :disabled="isRowBusy(meal.row, meal.mealPeriod)"
                  @input="(e) => setTotalStockDraft(meal.row, (e.target).value, meal.mealPeriod)"
                  @blur="() => onTotalStockCommit(meal.row, meal.mealPeriod)"
                />
                <span v-else class="wmenu-dash">—</span>
              </label>
              <el-select
                v-if="meal.row.dish_id"
                :model-value="meal.row.paired_drink_id"
                filterable
                clearable
                placeholder="随餐饮"
                class="wmenu-drink-select"
                :loading="isRowBusy(meal.row, meal.mealPeriod)"
                :disabled="isRowBusy(meal.row, meal.mealPeriod)"
                @update:model-value="(v) => onDrinkChange(meal.row, v, meal.mealPeriod)"
              >
                <el-option
                  v-for="opt in drinkOptions"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <span v-else class="wmenu-dash">—</span>
            </div>
          </section>
        </article>
      </div>
    </div>
  </section>
</template>

<style scoped>
.wmenu-page.mkt-page {
  max-width: none;
}
.wmenu-page.page-content-shell {
  /* 保持在主内容滚动区内。负边距会超出 overflow 裁切，标题左侧和右侧「开菜单」会被挡住 */
  margin-left: 0;
  margin-right: 0;
  width: 100%;
  box-sizing: border-box;
  padding-bottom: 0.75rem;
}
.wmenu-pills-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.wmenu-pills {
  display: flex;
  flex-wrap: nowrap;
  gap: 10px;
  overflow-x: auto;
}
.wmenu-pill {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  flex: 0 0 auto;
  border: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(255, 255, 255, 0.86);
  border-radius: 999px;
  padding: 7px 14px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  color: #1d1f21;
  white-space: nowrap;
}
.wmenu-pill__text {
  white-space: nowrap;
}
.wmenu-pill.is-on {
  color: #fff;
  background: var(--el-color-primary);
  border-color: transparent;
}

.wmenu-week-tabs {
  flex-shrink: 0;
  padding: 0 4px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.wmenu-week-tabs-el {
  flex: 1;
  min-width: 0;
}

.wmenu-prep-open {
  margin-bottom: 12px;
  flex-shrink: 0;
}

.wmenu-week-tabs-el :deep(.el-tabs__header) {
  margin: 0 0 12px;
}

.wmenu-week-tabs-el :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: var(--wmenu-border, #eaedf1);
}

.wmenu-week-tabs-el :deep(.el-tabs__item) {
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  font-weight: 700;
  color: var(--wmenu-muted, #64748b);
  padding: 0 18px;
}

.wmenu-week-tabs-el :deep(.el-tabs__item.is-active) {
  color: var(--wmenu-primary, #0d5c46);
}

.wmenu-week-tabs-el :deep(.el-tabs__active-bar) {
  background-color: var(--wmenu-primary, #0d5c46);
}

.wmenu-week-tab-label {
  margin-right: 6px;
}

.wmenu-week-tab-date {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
}

.wmenu-week-tabs-el :deep(.el-tabs__item.is-active) .wmenu-week-tab-date {
  color: #059669;
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

.wmenu-day-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  align-items: start;
}

.wmenu-day-card {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--wmenu-border);
  background: #fff;
}

.wmenu-day-card__title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
}

.wmenu-meal {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 8px;
  border-radius: 12px;
  background: #f8fafc;
}

.wmenu-meal__head {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.wmenu-meal__stats {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  margin-left: auto;
}

.wmenu-meta-label {
  font-size: 11px;
  font-weight: 700;
  color: var(--wmenu-muted);
}

.wmenu-meal__body {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(108px, 0.9fr);
  grid-template-rows: auto auto;
  gap: 8px;
  align-items: stretch;
}

.wmenu-meal__body .wmenu-dish-cell {
  grid-row: 1 / span 2;
  width: 100%;
  max-width: 100%;
  align-self: stretch;
}

.wmenu-meal__body .wmenu-stock,
.wmenu-meal__body .wmenu-drink-select,
.wmenu-meal__body > .wmenu-dash {
  width: 100%;
  min-width: 0;
}

.wmenu-stock {
  display: flex;
  align-items: center;
  gap: 6px;
  box-sizing: border-box;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

@media (max-width: 1200px) {
  .wmenu-day-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .wmenu-day-grid {
    grid-template-columns: 1fr;
  }
  .wmenu-meal__stats {
    margin-left: 0;
  }
  .wmenu-meal__body {
    grid-template-columns: minmax(0, 1fr) minmax(96px, 0.85fr);
  }
}

.wmenu-schedule-grid {
  display: block;
}

.wmenu-week-card {
  background: #fff;
  border-radius: 20px;
  border: 1px solid var(--wmenu-border);
  padding: 16px 16px 12px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.wmenu-week-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: nowrap;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--wmenu-border);
}

.wmenu-week-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  white-space: nowrap;
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
  overflow-x: hidden;
}

.wmenu-table {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  text-align: left;
}

.wmenu-col-day { width: 64px; }
.wmenu-col-meal { width: 56px; }
.wmenu-col-price { width: 84px; }
.wmenu-col-stock { width: 88px; }
.wmenu-col-retail { width: 72px; }
.wmenu-col-remain { width: 64px; }
.wmenu-col-drink { width: 168px; }
.wmenu-col-box { width: 84px; }

.wmenu-table th {
  color: #fff;
  background: var(--el-color-primary);
  font-size: 12px;
  font-weight: 800;
  padding: 8px 8px;
  border-bottom: 0;
  white-space: nowrap;
}
.wmenu-table thead th:first-child {
  border-top-left-radius: 12px;
}
.wmenu-table thead th:last-child {
  border-top-right-radius: 12px;
}

.wmenu-table td {
  padding: 6px 8px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid transparent;
  vertical-align: middle;
  color: #0f172a;
}

.wmenu-row-day-end td {
  border-bottom-color: var(--wmenu-border);
}

.wmenu-day-cell {
  text-align: center;
  border-bottom-color: var(--wmenu-border);
}

.wmenu-price-cell {
  white-space: nowrap;
}

.wmenu-table tbody tr:hover {
  background: #f8fafc;
}

.wmenu-day-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #f1f5f9;
  font-size: 12px;
  font-weight: 800;
}

.wmenu-meal-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  line-height: 1.4;
}

.wmenu-meal-tag--lunch {
  color: #9a3412;
  background: #fff7ed;
}

.wmenu-meal-tag--dinner {
  color: #1e3a8a;
  background: #eff6ff;
}

.wmenu-day-label--alt {
  background: #e2e8f0;
}

.wmenu-price {
  font-family: var(--okfood-font-number);
  font-size: 13.5px;
  font-weight: 700;
  white-space: nowrap;
}

.wmenu-price--missing {
  color: var(--wmenu-danger-text);
}

.wmenu-total-input {
  width: auto;
  flex: 1 1 auto;
  min-width: 0;
  padding: 4px 6px;
  border-radius: 8px;
  border: 1px solid var(--wmenu-border);
  background: #f8fafc;
  text-align: center;
  font-weight: 700;
  font-size: 12px;
  line-height: 1.2;
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
  -moz-appearance: textfield;
  appearance: textfield;
}

.wmenu-total-input:focus {
  border-color: var(--wmenu-primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 92, 70, 0.06);
}

.wmenu-total-input::-webkit-outer-spin-button,
.wmenu-total-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.wmenu-total-input::placeholder {
  color: #cbd5e1;
  font-size: 10px;
}

.wmenu-total-input:disabled {
  opacity: 0.65;
}

.wmenu-dash {
  color: var(--wmenu-muted);
}

.wmenu-retail-badge {
  font-family: var(--okfood-font-number);
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 8px;
  display: inline-block;
  min-width: 0;
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
  padding: 2px 6px;
  border-radius: 8px;
  display: inline-block;
  min-width: 0;
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

.wmenu-dish-cell {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  width: 100%;
  max-width: 100%;
  min-width: 0;
}
.wmenu-meal .wmenu-dish-select.el-select {
  width: 100%;
  height: 100%;
}
.wmenu-meal .wmenu-drink-select.el-select {
  width: 100%;
  min-width: 0;
  max-width: 100%;
}
.wmenu-box-flag {
  flex: 0 0 auto;
  margin-left: 0;
  white-space: nowrap;
  padding: 0;
}

.wmenu-dish-select :deep(.el-select__wrapper),
.wmenu-drink-select :deep(.el-select__wrapper) {
  padding: 6px 12px;
  border-radius: 12px;
  border: 1px solid var(--wmenu-border);
  background: #f8fafc;
  font-size: 12.5px;
  font-weight: 700;
  box-shadow: none;
  min-height: 32px;
}

.wmenu-dish-select :deep(.el-select__wrapper.is-focused),
.wmenu-drink-select :deep(.el-select__wrapper.is-focused) {
  border-color: var(--wmenu-primary);
  background: #fff;
  box-shadow: 0 0 0 3px rgba(13, 92, 70, 0.06);
}

.wmenu-dish-select :deep(.el-select__placeholder),
.wmenu-drink-select :deep(.el-select__placeholder) {
  color: #94a3b8;
  font-weight: 700;
}

.wmenu-dish-select :deep(.el-select__wrapper) {
  height: 100%;
  min-height: 76px;
  padding: 6px 10px;
}

.wmenu-dish-select :deep(.el-select__selected-item) {
  display: flex;
  align-items: center;
  max-width: 100%;
  line-height: 1;
}

/* 卡片里的菜品图比下拉项大，方便认菜 */
.wmenu-dish-picked {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  max-width: 100%;
}

.wmenu-dish-picked__img {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  flex: 0 0 auto;
  background: #f1f5f9;
}

.wmenu-dish-picked__img--empty {
  display: inline-block;
}

.wmenu-dish-picked__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 下拉项在本组件模板里，缩略图样式可以留在 scoped */
.wmenu-dish-opt {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.wmenu-dish-opt__img {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  object-fit: cover;
  flex: 0 0 auto;
  background: #f1f5f9;
}

.wmenu-dish-opt__img--empty {
  display: inline-block;
}

.wmenu-dish-opt__name {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 700;
}

.wmenu-dish-opt__price {
  flex: 0 0 auto;
  font-size: 12px;
  font-weight: 700;
  color: #8b949e;
  font-family: var(--okfood-font-number);
}

</style>

<style>
/* 下拉挂到 body，行高和宽度写在这里，避免 28px 小图被默认 34px 行高裁切 */
.wmenu-dish-popper.el-popper {
  min-width: 280px;
}

.wmenu-dish-popper .el-select-dropdown__item {
  height: auto;
  line-height: 1.2;
  padding-top: 4px;
  padding-bottom: 4px;
}
</style>
