<script setup>
import DeliveryRegionsPanel from '../components/DeliveryRegionsPanel.vue'
import { adminApiAuthenticated } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

function onDeliveryRegionToast(msg, kind = 'success') {
  showToast(msg, kind)
}
</script>

<template>
  <section class="tab-content animate-up">
    <DeliveryRegionsPanel :api-request="adminApiAuthenticated" @toast="onDeliveryRegionToast" />
  </section>
</template>
