<script setup>
defineOptions({ name: 'CardPackOrdersView' })
import OrdersManagePageShell from '../components/OrdersManagePageShell.vue'
import MallCardOrdersTab from '../components/MallCardOrdersTab.vue'
</script>

<template>
  <OrdersManagePageShell order-kind="mall">
    <MallCardOrdersTab />
  </OrdersManagePageShell>
</template>
