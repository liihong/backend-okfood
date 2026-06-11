<script setup>
import { AlertTriangle } from 'lucide-vue-next'
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
    width="440px"
    class="orders-refund-dialog"
    destroy-on-close
    align-center
    :close-on-click-modal="!refundLoadingId"
    :close-on-press-escape="!refundLoadingId"
    @closed="onRefundDialogClosed"
  >
    <template #header>
      <div class="orders-refund-header">
        <span class="orders-refund-header-icon" aria-hidden="true">
          <AlertTriangle :size="20" :stroke-width="2.25" />
        </span>
        <span class="orders-refund-header-title">微信原路退款</span>
      </div>
    </template>
    <div v-if="refundDialogMeta" class="orders-refund-body">
      <p class="orders-refund-lead">请确认以下退款信息后再提交</p>
      <dl class="orders-refund-card">
        <div class="orders-refund-row">
          <dt>订单类型</dt>
          <dd>{{ refundDialogMeta.orderType }}</dd>
        </div>
        <div class="orders-refund-row">
          <dt>订单编号</dt>
          <dd>#{{ refundDialogMeta.orderId }}</dd>
        </div>
        <div class="orders-refund-row orders-refund-row--amount">
          <dt>退款金额</dt>
          <dd>
            <span class="orders-refund-amount">¥ {{ refundDialogMeta.amountStr }}</span>
            <span class="orders-refund-amount-sub">{{ refundDialogMeta.sub }}</span>
          </dd>
        </div>
      </dl>
      <p class="orders-refund-tip">
        <AlertTriangle :size="14" :stroke-width="2.25" class="orders-refund-tip-icon" aria-hidden="true" />
        <span>{{ refundDialogMeta.tip }}</span>
      </p>
    </div>
    <template #footer>
      <div class="orders-refund-footer">
        <el-button :disabled="!!refundLoadingId" @click="refundOpen = false">取消</el-button>
        <el-button type="danger" :loading="!!refundLoadingId" @click="submitRefundWechat">
          确定退款
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>
