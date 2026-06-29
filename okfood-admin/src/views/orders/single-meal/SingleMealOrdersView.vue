<script setup>
defineOptions({ name: 'SingleMealOrdersView' })
import OrdersManagePageShell from '../components/OrdersManagePageShell.vue'
import SingleMealOrdersTab from '../components/SingleMealOrdersTab.vue'
</script>

<template>
  <OrdersManagePageShell order-kind="single">
    <SingleMealOrdersTab />
  </OrdersManagePageShell>
</template>
