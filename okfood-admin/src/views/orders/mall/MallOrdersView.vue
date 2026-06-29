<script setup>
defineOptions({ name: 'MallOrdersView' })
import OrdersManagePageShell from '../components/OrdersManagePageShell.vue'
import RetailOrdersTab from '../components/RetailOrdersTab.vue'
</script>

<template>
  <OrdersManagePageShell order-kind="retail">
    <RetailOrdersTab />
  </OrdersManagePageShell>
</template>
