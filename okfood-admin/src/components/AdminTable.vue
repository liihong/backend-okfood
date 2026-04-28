<script setup>
import { computed, useAttrs, ref } from 'vue'

/**
 * 后台统一表格：封装 el-table，默认斑马纹与边框，并按 variant 套用 admin-ui 风格。
 */
defineOptions({ inheritAttrs: false })

const props = defineProps({
  /** 行数据 */
  data: { type: Array, default: () => [] },
  /** 是否显示加载遮罩（v-loading） */
  loading: { type: Boolean, default: false },
  /**
   * 视觉变体，与 admin-ui 中原 data-table / delivery-table 等对齐
   * @type {'default' | 'members' | 'delivery' | 'weekly'}
   */
  variant: {
    type: String,
    default: 'default',
    validator: (v) => ['default', 'members', 'delivery', 'weekly'].includes(v),
  },
  stripe: { type: Boolean, default: true },
  border: { type: Boolean, default: true },
  /** 无数据时文案（未使用 #empty 插槽时生效） */
  emptyText: { type: String, default: '暂无数据' },
})

const attrs = useAttrs()

const rootClass = computed(() => {
  const map = {
    default: 'admin-table admin-table--default',
    members: 'admin-table admin-table--members',
    delivery: 'admin-table admin-table--delivery',
    weekly: 'admin-table admin-table--weekly',
  }
  return [map[props.variant] || map.default, attrs.class].filter(Boolean)
})

const passthroughAttrs = computed(() => {
  const { class: _c, ...rest } = attrs
  return rest
})

const tableRef = ref(null)

function clearSelection() {
  tableRef.value?.clearSelection()
}

defineExpose({ clearSelection })
</script>

<template>
  <el-table
    ref="tableRef"
    v-loading="loading"
    :data="data"
    :stripe="stripe"
    :border="border"
    :empty-text="emptyText"
    :class="rootClass"
    v-bind="passthroughAttrs"
  >
    <template v-if="$slots.empty" #empty>
      <slot name="empty" />
    </template>
    <template v-if="$slots.append" #append>
      <slot name="append" />
    </template>
    <slot />
  </el-table>
</template>
