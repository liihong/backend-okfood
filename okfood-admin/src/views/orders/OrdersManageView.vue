<script setup>
defineOptions({ name: 'OrdersManageView' })
import { provide } from 'vue'
import { ORDERS_MANAGE_KEY } from './constants.js'
import { useOrdersManage } from './composables/useOrdersManage.js'
import OrdersManageToolbar from './components/OrdersManageToolbar.vue'
import SingleMealOrdersTab from './components/SingleMealOrdersTab.vue'
import RetailOrdersTab from './components/RetailOrdersTab.vue'
import MallCardOrdersTab from './components/MallCardOrdersTab.vue'
import OrdersPagination from './components/OrdersPagination.vue'
import OrdersRefundDialog from './components/OrdersRefundDialog.vue'
import OrdersAssignCourierDialog from './components/OrdersAssignCourierDialog.vue'
import OrdersEditOrderDialog from './components/OrdersEditOrderDialog.vue'
import './orders-manage.css'

const ordersManage = useOrdersManage()
provide(ORDERS_MANAGE_KEY, ordersManage)

const { activeTab } = ordersManage
</script>

<template>
  <section class="tab-content animate-up orders-manage-page">
    <div class="table-container">
      <OrdersManageToolbar />

      <el-tabs v-model="activeTab" class="orders-manage-tabs">
        <el-tab-pane label="单次点餐" name="single">
          <SingleMealOrdersTab />
        </el-tab-pane>
        <el-tab-pane label="商城订单" name="retail">
          <RetailOrdersTab />
        </el-tab-pane>
        <el-tab-pane label="卡包订单" name="mall">
          <MallCardOrdersTab />
        </el-tab-pane>
      </el-tabs>

      <OrdersPagination />
    </div>

    <OrdersRefundDialog />
    <OrdersAssignCourierDialog />
    <OrdersEditOrderDialog />
  </section>
</template>
