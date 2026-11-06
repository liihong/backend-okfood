<script setup>
defineOptions({ name: 'DashboardView' })
import DeliveryRegionsOverviewPanel from '../components/dashboard/DeliveryRegionsOverviewPanel.vue'
</script>

<template>
  <section class="dashboard-view tab-content animate-up page-content-shell">
    <DeliveryRegionsOverviewPanel />
  </section>
</template>
