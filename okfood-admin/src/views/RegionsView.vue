<script setup>
defineOptions({ name: 'RegionsView' })
import DeliveryRegionsPanel from '../components/DeliveryRegionsPanel.vue'
import { adminApiAuthenticated } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

function onDeliveryRegionToast(msg, kind = 'success') {
  showToast(msg, kind)
}
</script>

<template>
  <!-- 与 AdminLayout main-body__router-host 配合纵向撑满，去掉底部空白 -->
  <section class="regions-view tab-content animate-up page-content-shell">
    <DeliveryRegionsPanel :api-request="adminApiAuthenticated" @toast="onDeliveryRegionToast" />
  </section>
</template>

<style scoped>
.regions-view {
  flex: 1;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* 兜底：侧栏 fixed 等场景下路由视区若无明确高度，grid 行高 1fr 会塌成内容高度 → 底部大白块 */
  min-height: calc(100vh - 10.5rem);
  min-height: calc(100dvh - 10.5rem);
}

.regions-view.page-content-shell {
  padding-bottom: 0;
}
</style>
