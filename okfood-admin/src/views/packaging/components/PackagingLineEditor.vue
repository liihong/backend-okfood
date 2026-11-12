<script setup>
/**
 * 用盒和标配共用的耗材行编辑器。
 * 打包袋只在第一行展示，不进可编辑列表，避免和每餐一只重复扣。
 */
defineOptions({ name: 'PackagingLineEditor' })

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  skuOptions: { type: Array, default: () => [] },
  /** 每餐自动扣的打包袋名称。有值就固定在第一行，不可改、不可删。 */
  fixedBagName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

function update(next) {
  emit('update:modelValue', next)
}

function addLine() {
  update([...(props.modelValue || []), { sku_id: null, qty_per_portion: 1 }])
}

function removeLine(index) {
  update((props.modelValue || []).filter((_, i) => i !== index))
}
</script>

<template>
  <div class="pack-lines">
    <div v-if="fixedBagName" class="pack-lines__row pack-lines__row--fixed">
      <el-input :model-value="fixedBagName" disabled class="pack-lines__sku" />
      <el-input-number :model-value="1" disabled :min="1" :step="1" :precision="0" />
      <span class="pack-lines__unit">每份</span>
      <span class="pack-lines__fixed">自动扣</span>
    </div>
    <div v-for="(line, index) in modelValue" :key="index" class="pack-lines__row">
      <el-select v-model="line.sku_id" filterable clearable placeholder="选择耗材" class="pack-lines__sku">
        <el-option
          v-for="opt in skuOptions"
          :key="opt.id"
          :label="opt.name"
          :value="opt.id"
          :disabled="!opt.is_active"
        />
      </el-select>
      <el-input-number v-model="line.qty_per_portion" :min="1" :step="1" :precision="0" />
      <span class="pack-lines__unit">每份</span>
      <el-button type="danger" link @click="removeLine(index)">移除</el-button>
    </div>
      <el-button round @click="addLine">添加耗材</el-button>
  </div>
</template>

<style scoped>
.pack-lines__row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.pack-lines__sku {
  width: 240px;
}
.pack-lines__unit {
  color: var(--el-text-color-secondary);
}
.pack-lines__row--fixed :deep(.el-input__wrapper),
.pack-lines__row--fixed :deep(.el-input-number) {
  cursor: not-allowed;
}
.pack-lines__fixed {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  white-space: nowrap;
}
</style>
