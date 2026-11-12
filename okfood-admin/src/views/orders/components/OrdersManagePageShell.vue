<script setup>
import { computed, provide } from 'vue'
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

/** 订单列表铺满主区：工具栏和表头不动，只滚表体 */
const fillLayout = computed(
  () => props.orderKind === 'single' || props.orderKind === 'retail' || props.orderKind === 'mall',
)
</script>

<template>
  <!-- 零售订单撑满主区：页头、汇总、分页固定，只滚表体 -->
  <section
    class="tab-content animate-up orders-manage-page"
    :class="{ 'members-view-fill': fillLayout }"
  >
    <div
      class="table-container"
      :class="{ 'table-container--members-fill': fillLayout }"
    >
      <OrdersManageToolbar />
      <slot />
      <OrdersPagination :float-bar="fillLayout" />
    </div>

    <OrdersRefundDialog />
    <OrdersAssignCourierDialog />
    <OrdersEditOrderDialog />
    <OrdersRetailRemarkDialog />
  </section>
</template>
