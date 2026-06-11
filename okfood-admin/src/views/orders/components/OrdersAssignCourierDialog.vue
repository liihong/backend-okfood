<script setup>
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  assignOpen,
  batchAssignMode,
  batchAssignOrders,
  assignOrder,
  assignCourierId,
  courierOptions,
  batchDispatchLoading,
  submitAssignCourier,
  onAssignDialogClosed,
} = useOrdersManageInject()
</script>

<template>
  <el-dialog
    v-model="assignOpen"
    :title="batchAssignMode ? '批量门店自配送 · 指派配送员' : '门店自配送 · 指派配送员'"
    width="420px"
    destroy-on-close
    @closed="onAssignDialogClosed"
  >
    <template v-if="batchAssignMode">
      <p class="orders-assign-hint">
        已选 {{ batchAssignOrders.length }} 笔待发货订单，将统一指派给所选配送员。
      </p>
    </template>
    <template v-else-if="assignOrder">
      <p class="orders-assign-hint">
        订单 #{{ assignOrder.id }} · {{ (assignOrder.member_name || '').trim() || '—' }}
      </p>
    </template>
    <el-select
      v-model="assignCourierId"
      filterable
      placeholder="选择系统内配送员"
      class="orders-assign-select"
    >
      <el-option
        v-for="c in courierOptions"
        :key="c.courier_id"
        :label="`${(c.name || '').trim() || c.courier_id}（${c.courier_id}）`"
        :value="c.courier_id"
        :disabled="c.is_active === false"
      />
    </el-select>
    <template #footer>
      <el-button @click="assignOpen = false">取消</el-button>
      <el-button type="primary" :loading="batchDispatchLoading" @click="submitAssignCourier">
        {{ batchAssignMode ? '批量确定' : '确定' }}
      </el-button>
    </template>
  </el-dialog>
</template>
