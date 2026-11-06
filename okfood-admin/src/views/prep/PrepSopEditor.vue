<script setup>
defineOptions({ name: 'PrepSopEditor' })
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { showToast } from '../../composables/useToast.js'
import { handleAdminLogout } from '../../admin/core.js'
import { formatYield, getDishPrepSop, listPrepIngredients, saveDishPrepSop } from '../../api/prepMenu.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** @type {import('vue').PropType<Array<{ dishId: number, dishName: string, usages: string[] }>>} */
  dishes: { type: Array, default: () => [] },
  focusDishId: { default: null },
  ingredientTick: { type: Number, default: 0 },
})
const emit = defineEmits(['update:modelValue', 'saved', 'manage-ingredients'])

const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const selectedId = ref(/** @type {number | null} */ (null))
const savedCount = ref(0)
/** @type {import('vue').Ref<Array<{ id: number, name: string, unit: 'g' | 'piece', yield_rate: string }>>} */
const ingredients = ref([])
/** @type {import('vue').Ref<Array<{ key: string, ingredientId: number | null, qty: string }>>} */
const lines = ref([])
let keySeq = 0

const selectedDish = computed(() => props.dishes.find((item) => item.dishId === selectedId.value) || null)

function nextKey() {
  keySeq += 1
  return `line-${keySeq}`
}

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

async function loadIngredients() {
  const data = await listPrepIngredients()
  ingredients.value = Array.isArray(data) ? data : []
}

/** @param {number} dishId */
async function loadSop(dishId) {
  loading.value = true
  try {
    const data = await getDishPrepSop(dishId)
    const sopLines = Array.isArray(data?.lines) ? data.lines : []
    lines.value = sopLines.map((line) => ({
      key: nextKey(),
      ingredientId: Number(line.ingredient_id),
      qty: String(line.gross_qty_per_portion ?? ''),
    }))
    savedCount.value = sopLines.length
    dirty.value = false
  } catch (error) {
    report(error, '配方加载失败')
  } finally {
    loading.value = false
  }
}

/** @param {number} dishId @param {boolean} [force] */
async function selectDish(dishId, force = false) {
  if (dishId === selectedId.value && !force) return
  if (dirty.value && dishId !== selectedId.value) {
    try {
      await ElMessageBox.confirm('当前配方还没保存，切换菜品会丢掉修改。', '切换菜品', {
        type: 'warning',
        confirmButtonText: '切换',
        cancelButtonText: '留下',
      })
    } catch {
      return
    }
  }
  selectedId.value = dishId
  await loadSop(dishId)
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      dirty.value = false
      return
    }
    dirty.value = false
    selectedId.value = null
    lines.value = []
    void (async () => {
      try {
        await loadIngredients()
      } catch (error) {
        report(error, '食材加载失败')
      }
      const focus = props.focusDishId || props.dishes[0]?.dishId || null
      if (focus) await selectDish(focus, true)
    })()
  },
)

watch(
  () => props.focusDishId,
  (dishId) => {
    if (!props.modelValue || !dishId) return
    void selectDish(dishId)
  },
)

watch(
  () => props.ingredientTick,
  () => {
    if (!props.modelValue) return
    void loadIngredients().catch((error) => report(error, '食材加载失败'))
  },
)

function markDirty() {
  dirty.value = true
}

function addLine() {
  if (!ingredients.value.length) {
    showToast('请先维护食材与出成率', 'error')
    emit('manage-ingredients')
    return
  }
  lines.value = [...lines.value, { key: nextKey(), ingredientId: null, qty: '' }]
  markDirty()
}

/** @param {number} ingredientId @param {string} currentKey */
function ingredientDisabled(ingredientId, currentKey) {
  return lines.value.some((line) => line.key !== currentKey && line.ingredientId === ingredientId)
}

/** @param {number | null} ingredientId */
function ingredientOf(ingredientId) {
  return ingredients.value.find((item) => item.id === ingredientId) || null
}

/** @param {{ key: string, ingredientId: number | null }} line */
async function removeLine(line) {
  const name = ingredientOf(line.ingredientId)?.name || '这一行'
  try {
    await ElMessageBox.confirm(`确定去掉「${name}」？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  lines.value = lines.value.filter((item) => item.key !== line.key)
  markDirty()
}

async function save() {
  if (!selectedId.value) {
    showToast('请先选择菜品', 'error')
    return
  }
  const payload = []
  const seen = new Set()
  for (const line of lines.value) {
    if (!line.ingredientId) {
      showToast('还有配菜没有选择食材', 'error')
      return
    }
    if (seen.has(line.ingredientId)) {
      showToast('同一食材只能出现一次', 'error')
      return
    }
    seen.add(line.ingredientId)
    const qty = String(line.qty ?? '').trim()
    if (!/^\d+(\.\d{1,3})?$/.test(qty) || Number(qty) <= 0) {
      showToast('单份毛菜须为大于 0 的数字，最多 3 位小数', 'error')
      return
    }
    payload.push({ ingredient_id: line.ingredientId, gross_qty_per_portion: qty })
  }
  if (!payload.length && savedCount.value > 0) {
    try {
      await ElMessageBox.confirm('将清空该菜品的配菜配方。', '清空确认', {
        type: 'warning',
        confirmButtonText: '清空',
        cancelButtonText: '取消',
      })
    } catch {
      return
    }
  }
  saving.value = true
  try {
    await saveDishPrepSop(selectedId.value, payload)
    showToast('配菜已保存', 'success')
    savedCount.value = payload.length
    dirty.value = false
    emit('saved')
  } catch (error) {
    report(error, '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="本周菜品配方"
    width="920px"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="(open) => emit('update:modelValue', open)"
  >
    <p class="prep-sop-tip">这里填的是单份毛菜。克重会按食材出成率折成净菜，个数只乘份数。</p>
    <div v-if="!dishes.length" class="prep-sop-empty">本周还没有排菜，先在菜单里选择菜品。</div>
    <div v-else class="prep-sop-layout" v-loading="loading">
      <div class="prep-sop-dishes">
        <button
          v-for="dish in dishes"
          :key="dish.dishId"
          type="button"
          class="prep-sop-dish"
          :class="{ 'is-active': dish.dishId === selectedId }"
          @click="selectDish(dish.dishId)"
        >
          <span class="prep-sop-dish-name">{{ dish.dishName }}</span>
          <span class="prep-sop-dish-usage">{{ dish.usages.join('、') }}</span>
        </button>
      </div>
      <div class="prep-sop-editor">
        <div class="prep-sop-editor-head">
          <strong>{{ selectedDish?.dishName || '选择左侧菜品' }}</strong>
          <div>
            <el-button @click="emit('manage-ingredients')">食材与出成率</el-button>
            <el-button type="primary" plain @click="addLine">添加配菜</el-button>
          </div>
        </div>
        <el-table :data="lines" empty-text="还没有配菜">
          <el-table-column label="食材" min-width="180">
            <template #default="{ row }">
              <el-select
                v-model="row.ingredientId"
                filterable
                placeholder="选择食材"
                style="width: 100%"
                @change="markDirty"
              >
                <el-option
                  v-for="item in ingredients"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                  :disabled="ingredientDisabled(item.id, row.key)"
                />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="单份毛菜" width="160">
            <template #default="{ row }">
              <el-input
                v-model="row.qty"
                :placeholder="ingredientOf(row.ingredientId)?.unit === 'piece' ? '个数' : '克'"
                @update:model-value="markDirty"
              />
            </template>
          </el-table-column>
          <el-table-column label="单位" width="70">
            <template #default="{ row }">
              {{ ingredientOf(row.ingredientId)?.unit === 'piece' ? '个' : ingredientOf(row.ingredientId) ? '克' : '—' }}
            </template>
          </el-table-column>
          <el-table-column label="出成率" width="90">
            <template #default="{ row }">
              {{ formatYield(ingredientOf(row.ingredientId)?.yield_rate, ingredientOf(row.ingredientId)?.unit) }}
            </template>
          </el-table-column>
          <el-table-column label="" width="70" align="center">
            <template #default="{ row }">
              <el-button link type="danger" @click="removeLine(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">关闭</el-button>
      <el-button type="primary" :loading="saving" :disabled="!selectedId" @click="save">保存配方</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.prep-sop-tip {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 13px;
}
.prep-sop-empty {
  color: #64748b;
  padding: 24px 0;
}
.prep-sop-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  min-height: 280px;
}
.prep-sop-dishes {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 420px;
  overflow: auto;
}
.prep-sop-dish {
  text-align: left;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
}
.prep-sop-dish.is-active {
  border-color: #0d5c46;
  background: #f0fdf4;
}
.prep-sop-dish-name {
  display: block;
  font-weight: 700;
  color: #0f172a;
}
.prep-sop-dish-usage {
  display: block;
  margin-top: 2px;
  color: #64748b;
  font-size: 12px;
}
.prep-sop-editor-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
@media (max-width: 800px) {
  .prep-sop-layout {
    grid-template-columns: 1fr;
  }
}
</style>
