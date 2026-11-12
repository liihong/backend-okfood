<script setup>
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  refundOpen,
  refundLoadingId,
  refundDialogMeta,
  submitRefundWechat,
  onRefundDialogClosed,
} = useOrdersManageInject()
</script>

<template>
  <el-dialog
    v-model="refundOpen"
    width="420px"
    class="orders-refund-dialog"
    append-to-body
    align-center
    destroy-on-close
    :close-on-click-modal="!refundLoadingId"
    :close-on-press-escape="!refundLoadingId"
    @closed="onRefundDialogClosed"
  >
    <template #header>
      <div class="orders-refund-head">
        <strong>微信原路退款</strong>
        <span v-if="refundDialogMeta">#{{ refundDialogMeta.orderId }} · {{ refundDialogMeta.orderType }}</span>
      </div>
    </template>
    <div v-if="refundDialogMeta" class="orders-refund-body">
      <section class="orders-refund-card">
        <p class="orders-refund-k">退款金额</p>
        <p class="orders-refund-amount">¥{{ refundDialogMeta.amountStr }}</p>
        <p class="orders-refund-sub">{{ refundDialogMeta.sub }}</p>
        <p v-if="refundDialogMeta.memberLine" class="orders-refund-member">{{ refundDialogMeta.memberLine }}</p>
      </section>
      <p class="orders-refund-tip">{{ refundDialogMeta.tip }}</p>
    </div>
    <template #footer>
      <el-button round :disabled="!!refundLoadingId" @click="refundOpen = false">取消</el-button>
      <el-button type="danger" round :loading="!!refundLoadingId" @click="submitRefundWechat">
        确定退款
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.orders-refund-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
  padding-right: 28px;
}

.orders-refund-head strong {
  font-size: 16px;
  font-weight: 800;
  color: #1d1f21;
}

.orders-refund-head span {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-color-primary-dark-2, #c75f48);
  white-space: nowrap;
}

.orders-refund-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.orders-refund-card {
  padding: 16px 14px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  text-align: center;
}

.orders-refund-k {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.orders-refund-amount {
  margin: 4px 0 0;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: #be123c;
  font-variant-numeric: tabular-nums;
}

.orders-refund-sub,
.orders-refund-member {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.orders-refund-member {
  margin-top: 8px;
  color: #1d1f21;
}

.orders-refund-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.45;
  color: #c2410c;
  text-align: center;
}
</style>

<style>
.orders-refund-dialog.el-dialog,
.el-overlay .orders-refund-dialog.el-dialog {
  border-radius: 16px;
  padding: 0;
  background: #f7fafb;
  max-width: calc(100vw - 32px);
}

.orders-refund-dialog .el-dialog__header,
.el-overlay .orders-refund-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 16px 16px 0 0;
}

.orders-refund-dialog .el-dialog__body,
.el-overlay .orders-refund-dialog .el-dialog__body {
  padding: 12px 14px;
  background: #f7fafb;
}

.orders-refund-dialog .el-dialog__footer,
.el-overlay .orders-refund-dialog .el-dialog__footer {
  padding: 10px 16px 14px;
  background: #fff;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 0 0 16px 16px;
}
</style>
