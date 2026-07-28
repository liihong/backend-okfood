<script setup>
/**
 * 兼容旧引用：打开时跳转到独立管理页，不再使用抽屉。
 * 新代码请使用 tenantMiniProgramRoute + router.push。
 */
import { watch } from 'vue'
import { useRouter } from 'vue-router'
import { MINI_PROGRAM_TABS } from './tenantMiniProgramConstants.js'
import { tenantMiniProgramRoute } from './mini-program/tenantMiniProgramNav.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  tenant: { type: Object, default: null },
  initialTab: { type: String, default: MINI_PROGRAM_TABS.brand },
})

const emit = defineEmits(['update:visible', 'saved'])

const router = useRouter()

const tabToRoute = {
  [MINI_PROGRAM_TABS.brand]: 'tenant-mini-brand',
  [MINI_PROGRAM_TABS.authorizer]: 'tenant-mini-authorizer',
  [MINI_PROGRAM_TABS.publish]: 'tenant-mini-publish',
}

watch(
  () => [props.visible, props.tenant?.id],
  ([vis, tid]) => {
    if (!vis || tid == null) return
    const pageName = tabToRoute[props.initialTab] || 'tenant-mini-brand'
    emit('update:visible', false)
    void router.push(tenantMiniProgramRoute(pageName, tid, props.tenant?.name))
  },
)
</script>

<template>
  <span v-if="false" />
</template>
