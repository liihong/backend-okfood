<script setup>
import { provide } from 'vue'
import { ORDERS_MANAGE_KEY } from '../constants.js'
import { useOrdersManage } from '../composables/useOrdersManage.js'
import OrdersManageToolbar from './OrdersManageToolbar.vue'
import OrdersPagination from './OrdersPagination.vue'
import OrdersRefundDialog from './OrdersRefundDialog.vue'
import OrdersAssignCourierDialog from './OrdersAssignCourierDialog.vue'
import OrdersEditOrderDialog from './OrdersEditOrderDialog.vue'
import OrdersRetailRemarkDialog from './OrdersRetailRemarkDialog.vue'
import '../orders-manage.css'

/** @type {{ orderKind: 'single' | 'retail' | 'mall' }} */
const props = defineProps({
  /** 固定订单类型：零售 / 商城 / 卡包 */
  orderKind: {
    type: String,
    required: true,
    validator: (v) => v === 'single' || v === 'retail' || v === 'mall',
  },
})

const ordersManage = useOrdersManage(props.orderKind)
provide(ORDERS_MANAGE_KEY, ordersManage)
</script>

<template>
  <section class="tab-content animate-up orders-manage-page">
    <div class="table-container">
      <OrdersManageToolbar />
      <slot />
      <OrdersPagination />
    </div>

    <OrdersRefundDialog />
    <OrdersAssignCourierDialog />
    <OrdersEditOrderDialog />
    <OrdersRetailRemarkDialog />
  </section>
</template>
