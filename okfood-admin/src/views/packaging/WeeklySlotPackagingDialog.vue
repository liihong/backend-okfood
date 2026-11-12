<script setup>
/**
 * 本周菜单某一餐的用盒。保存后写回菜品默认，下周同一道菜会带出来。
 * 不改日总份，也不改选菜接口。
 */
defineOptions({ name: 'WeeklySlotPackagingDialog' })
import { computed, ref, watch } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { listPackagingSkus } from '../../api/packaging/sku.js'
import { getSlotPackaging, saveSlotPackaging } from '../../api/packaging/recipe.js'
import PackagingLineEditor from './components/PackagingLineEditor.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  weekStart: { type: String, default: '' },
  slot: { type: Number, default: 1 },
  mealPeriod: { type: String, default: 'lunch' },
  dishName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const loading = ref(false)
const saving = ref(false)
const skus = ref([])
const lines = ref([])
const skuOptions = computed(() => skus.value.filter((item) => !item.is_meal_bag))
const fixedBagName = computed(() => {
  const bag = skus.value.find((item) => item.is_meal_bag)
  return bag?.name || '打包袋'
})
const title = computed(() => {
  const meal = props.mealPeriod === 'dinner' ? '晚餐' : '午餐'
  return `${meal}用盒${props.dishName ? ` · ${props.dishName}` : ''}`
})

watch(
  () => props.modelValue,
  (open) => {
    if (open) void load()
  },
)

async function load() {
  loading.value = true
  try {
    const [skuRows, slotRow] = await Promise.all([
      listPackagingSkus(),
      getSlotPackaging({
        week_start: props.weekStart,
        slot: props.slot,
        meal_period: props.mealPeriod,
      }),
    ])
    skus.value = skuRows || []
    lines.value = (slotRow?.lines || []).map((line) => ({
      sku_id: line.sku_id,
      qty_per_portion: line.qty_per_portion,
    }))
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载用盒失败', 'error')
  } finally {
    loading.value = false
  }
}

async function save() {
  const payload = lines.value
    .filter((line) => line.sku_id)
    .map((line) => ({ sku_id: line.sku_id, qty_per_portion: line.qty_per_portion || 1 }))
  saving.value = true
  try {
    await saveSlotPackaging({
      week_start: props.weekStart,
      slot: props.slot,
      meal_period: props.mealPeriod,
      lines: payload,
    })
    showToast('用盒已保存', 'success')
    emit('update:modelValue', false)
    emit('saved')
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="title"
    width="640px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div v-loading="loading">
      <el-alert
        title="没设用盒时，晚上仍会扣打包袋和每份标配，并在系统消息里写明这餐没设盒子。"
        type="info"
        show-icon
        :closable="false"
        class="pack-gap"
      />
      <PackagingLineEditor v-model="lines" :sku-options="skuOptions" :fixed-bag-name="fixedBagName" />
    </div>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
</style>
