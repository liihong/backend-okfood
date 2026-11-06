<script setup>
defineOptions({ name: 'PrepMenuDialog' })
import { computed, ref, watch } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { handleAdminLogout } from '../../admin/core.js'
import { estimatePrepMenu, formatGrossAmount, formatNetAmount } from '../../api/prepMenu.js'
import PrepIngredientDialog from './PrepIngredientDialog.vue'
import PrepMealPane from './PrepMealPane.vue'
import PrepSopEditor from './PrepSopEditor.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  weekStart: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const booting = ref(false)
const refreshing = ref(false)
const activeTab = ref('lunch')
const ingredientOpen = ref(false)
const sopOpen = ref(false)
const sopDishId = ref(/** @type {number | null} */ (null))
const ingredientTick = ref(0)
/** @type {import('vue').Ref<Record<string, string>>} */
const drafts = ref({})
/** @type {import('vue').Ref<Record<string, boolean>>} */
const dirty = ref({})
/** @type {import('vue').Ref<null | { week_start: string, meals: MealEstimate[], week_ingredient_summary: SummaryRow[] }>} */
const estimate = ref(null)
let requestSeq = 0
let debounceTimer = 0

/**
 * @typedef {Object} PrepLine
 * @property {number} ingredient_id
 * @property {string} name
 * @property {'g' | 'piece'} unit
 * @property {string} per_portion_gross
 * @property {string | null} yield_rate
 * @property {string | null} gross_jin
 * @property {string | null} net_jin
 * @property {string | null} gross_count
 * @typedef {Object} PrepDay
 * @property {number} slot
 * @property {string} weekday
 * @property {string} menu_date
 * @property {number | null} dish_id
 * @property {string | null} dish_name
 * @property {number | null} portions
 * @property {'total_stock' | 'override' | 'missing'} portions_source
 * @property {'ok' | 'no_dish' | 'no_portions' | 'no_sop'} status
 * @property {boolean} has_sop
 * @property {PrepLine[]} lines
 * @typedef {Object} SummaryRow
 * @property {number} ingredient_id
 * @property {string} name
 * @property {'g' | 'piece'} unit
 * @property {string | null} [gross_jin]
 * @property {string | null} [net_jin]
 * @property {string | null} [gross_count]
 * @typedef {Object} MealEstimate
 * @property {'lunch' | 'dinner'} meal_period
 * @property {PrepDay[]} days
 * @property {SummaryRow[]} ingredient_summary
 */

const lunchMeal = computed(() => (estimate.value?.meals || []).find((meal) => meal.meal_period === 'lunch') || null)
const dinnerMeal = computed(() => (estimate.value?.meals || []).find((meal) => meal.meal_period === 'dinner') || null)

const weekDishes = computed(() => {
  /** @type {Map<number, { dishId: number, dishName: string, usages: string[] }>} */
  const map = new Map()
  for (const meal of estimate.value?.meals || []) {
    const label = meal.meal_period === 'dinner' ? '晚餐' : '午餐'
    for (const day of meal.days || []) {
      if (!day.dish_id) continue
      const usage = `${label}${day.weekday}`
      const prev = map.get(day.dish_id)
      if (!prev) {
        map.set(day.dish_id, { dishId: day.dish_id, dishName: day.dish_name || '未命名', usages: [usage] })
      } else if (!prev.usages.includes(usage)) {
        prev.usages.push(usage)
      }
    }
  }
  return [...map.values()]
})

/** @param {unknown} error @param {string} fallback */
function report(error, fallback) {
  const status = error && typeof error === 'object' && 'status' in error ? Number(error.status) : 0
  if (status === 401) {
    alert('登录已过期，请重新登录')
    handleAdminLogout()
    return
  }
  showToast(error instanceof Error ? error.message : fallback, 'error')
}

/** @param {string} mealPeriod @param {number} slot */
function draftKey(mealPeriod, slot) {
  return `${mealPeriod}|${slot}`
}

/** @param {string} mealPeriod @param {number} slot */
function portionDraft(mealPeriod, slot) {
  return drafts.value[draftKey(mealPeriod, slot)] ?? ''
}

function buildOverrides() {
  /** @type {{ meal_period: string, slot: number, portions: number | null }[]} */
  const list = []
  for (const key of Object.keys(dirty.value)) {
    if (!dirty.value[key]) continue
    const [mealPeriod, slotText] = key.split('|')
    const text = String(drafts.value[key] ?? '').trim()
    if (text !== '' && !/^\d+$/.test(text)) continue
    list.push({
      meal_period: mealPeriod,
      slot: Number(slotText),
      portions: text === '' ? null : Number(text),
    })
  }
  return list
}

/** @param {{ meals?: MealEstimate[] }} data */
function syncDrafts(data) {
  const next = { ...drafts.value }
  for (const meal of data.meals || []) {
    for (const day of meal.days || []) {
      const key = draftKey(meal.meal_period, day.slot)
      if (dirty.value[key]) continue
      next[key] = day.portions == null ? '' : String(day.portions)
    }
  }
  drafts.value = next
}

/** @param {boolean} first */
async function load(first) {
  const week = String(props.weekStart || '').trim()
  if (!week) {
    showToast('还没有周起始日期', 'error')
    return
  }
  const token = ++requestSeq
  if (first) booting.value = true
  else refreshing.value = true
  try {
    const data = await estimatePrepMenu({
      week_start: week,
      portion_overrides: buildOverrides(),
    })
    if (token !== requestSeq) return
    estimate.value = data
    syncDrafts(data)
  } catch (error) {
    if (token !== requestSeq) return
    report(error, '开菜单加载失败')
  } finally {
    if (token === requestSeq) {
      booting.value = false
      refreshing.value = false
    }
  }
}

function scheduleLoad() {
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    void load(false)
  }, 350)
}

/** @param {string} mealPeriod @param {number} slot @param {string} raw */
function onPortionInput(mealPeriod, slot, raw) {
  const key = draftKey(mealPeriod, slot)
  dirty.value = { ...dirty.value, [key]: true }
  drafts.value = { ...drafts.value, [key]: raw }
  const text = String(raw ?? '').trim()
  if (text !== '' && !/^\d+$/.test(text)) return
  scheduleLoad()
}

/** @param {number | null} [dishId] */
function openSop(dishId) {
  const target = dishId || weekDishes.value[0]?.dishId || null
  if (!target) {
    showToast('本周还没有排菜', 'error')
    return
  }
  sopDishId.value = target
  sopOpen.value = true
}

function onIngredientsChanged() {
  ingredientTick.value += 1
  void load(false)
}

watch(
  () => [props.modelValue, props.weekStart],
  (current, previous) => {
    const open = current[0]
    if (!open) return
    const justOpened = !previous || previous[0] !== true
    const weekChanged = !previous || previous[1] !== current[1]
    if (justOpened || weekChanged) {
      dirty.value = {}
      drafts.value = {}
      activeTab.value = 'lunch'
      void load(true)
      return
    }
  },
)
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    width="1040px"
    top="4vh"
    append-to-body
    class="prep-menu-dialog"
    @update:model-value="(open) => emit('update:modelValue', open)"
  >
    <template #header>
      <div class="prep-menu-head">
        <div>
          <div class="prep-menu-title">开菜单</div>
          <div class="prep-menu-sub">
            周起始 {{ weekStart || '—' }}。单份克数按毛菜计，净菜 = 毛菜 × 出成率，1 斤 = 500 克。这里改份数不会写回本周菜单。
          </div>
        </div>
        <div class="prep-menu-actions">
          <el-button @click="ingredientOpen = true">食材与出成率</el-button>
          <el-button type="primary" plain @click="openSop()">本周菜品配方</el-button>
        </div>
      </div>
    </template>

    <div v-loading="booting" class="prep-menu-body">
      <div v-if="refreshing" class="prep-menu-refresh">正在按新份数计算…</div>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="午餐" name="lunch">
          <PrepMealPane
            v-if="lunchMeal"
            :meal="lunchMeal"
            :portion-draft="portionDraft"
            @portion="onPortionInput"
            @configure="openSop"
          />
        </el-tab-pane>
        <el-tab-pane label="晚餐" name="dinner">
          <PrepMealPane
            v-if="dinnerMeal"
            :meal="dinnerMeal"
            :portion-draft="portionDraft"
            @portion="onPortionInput"
            @configure="openSop"
          />
        </el-tab-pane>
        <el-tab-pane label="本周采购汇总" name="summary">
          <el-table
            :data="estimate?.week_ingredient_summary || []"
            empty-text="还没有可汇总的配菜。请先排菜、填写份数并配置配方。"
          >
            <el-table-column prop="name" label="食材" min-width="160" />
            <el-table-column label="毛菜" min-width="140">
              <template #default="{ row }">{{ formatGrossAmount(row) }}</template>
            </el-table-column>
            <el-table-column label="净菜" min-width="140">
              <template #default="{ row }">{{ formatNetAmount(row) }}</template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-dialog>

  <PrepIngredientDialog v-model="ingredientOpen" @changed="onIngredientsChanged" />
  <PrepSopEditor
    v-model="sopOpen"
    :dishes="weekDishes"
    :focus-dish-id="sopDishId"
    :ingredient-tick="ingredientTick"
    @saved="load(false)"
    @manage-ingredients="ingredientOpen = true"
  />
</template>

<style scoped>
.prep-menu-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-right: 28px;
}
.prep-menu-title {
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
}
.prep-menu-sub {
  margin-top: 4px;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 500;
}
.prep-menu-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.prep-menu-body {
  max-height: calc(100vh - 220px);
  overflow: auto;
  padding-right: 4px;
}
.prep-menu-refresh {
  color: #0d5c46;
  font-size: 12px;
  margin-bottom: 8px;
}
@media (max-width: 800px) {
  .prep-menu-head {
    flex-direction: column;
  }
}
</style>
