<script setup>
/**
 * 兼容旧引用：转发到分模块的 TenantMiniProgramDrawer。
 * 新代码请直接 import ../tenants/TenantMiniProgramDrawer.vue
 */
import TenantMiniProgramDrawer from '../tenants/TenantMiniProgramDrawer.vue'

defineProps({
  visible: { type: Boolean, default: false },
  tenant: { type: Object, default: null },
  initialTab: { type: String, default: 'brand' },
})

defineEmits(['update:visible', 'saved'])
</script>

<template>
  <TenantMiniProgramDrawer
    :visible="visible"
    :tenant="tenant"
    :initial-tab="initialTab"
    @update:visible="$emit('update:visible', $event)"
    @saved="$emit('saved')"
  />
</template>
