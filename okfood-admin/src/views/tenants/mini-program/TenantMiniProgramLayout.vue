<script setup>
/**
 * 租户小程序管理 · 公共布局（顶栏 + 三页 Tab 导航）
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import { TENANT_MINI_PROGRAM_PAGES } from './tenantMiniProgramNav.js'

const props = defineProps({
  tenantId: { type: Number, required: true },
  tenantName: { type: String, default: '' },
})

const emit = defineEmits(['back'])

const route = useRoute()
const router = useRouter()

const activeTab = computed(() => String(route.name || ''))

function tabRoute(name) {
  const query = props.tenantName ? { name: props.tenantName } : {}
  return {
    name,
    params: { tenantId: String(props.tenantId) },
    query,
  }
}

function onBack() {
  emit('back')
}
</script>

<template>
  <div class="mini-program-layout">
    <header class="mini-program-layout__head">
      <el-button link type="primary" class="back-btn" @click="onBack">
        <ArrowLeft :size="16" stroke-width="2" />
        返回租户列表
      </el-button>
      <h2 class="mini-program-layout__title">小程序管理：{{ tenantName || `租户 #${tenantId}` }}</h2>
    </header>

    <el-tabs
      :model-value="activeTab"
      class="mini-program-layout__tabs"
      @tab-change="(name) => router.push(tabRoute(String(name)))"
    >
      <el-tab-pane
        v-for="p in TENANT_MINI_PROGRAM_PAGES"
        :key="p.name"
        :label="p.label"
        :name="p.name"
      />
    </el-tabs>

    <div class="mini-program-layout__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.mini-program-layout {
  max-width: 920px;
}
.mini-program-layout__head {
  margin-bottom: 8px;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
  padding-left: 0;
}
.mini-program-layout__title {
  margin: 0 0 12px;
  font-size: 1.15rem;
  font-weight: 600;
  color: rgba(248, 250, 252, 0.95);
}
.mini-program-layout__tabs {
  margin-bottom: 16px;
}
.mini-program-layout__body {
  min-height: 360px;
}
</style>
