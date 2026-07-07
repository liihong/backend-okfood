<script setup>
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  retailRemarkOpen,
  retailRemarkTarget,
  retailRemarkDraft,
  retailRemarkSaving,
  submitRetailRemark,
  onRetailRemarkDialogClosed,
} = useOrdersManageInject()
</script>

<template>
  <el-dialog
    v-model="retailRemarkOpen"
    width="440px"
    title="编辑备注"
    destroy-on-close
    align-center
    :close-on-click-modal="!retailRemarkSaving"
    :close-on-press-escape="!retailRemarkSaving"
    @closed="onRetailRemarkDialogClosed"
  >
    <div v-if="retailRemarkTarget" class="orders-remark-body">
      <p class="orders-remark-meta">订单 #{{ retailRemarkTarget.id }} · {{ retailRemarkTarget.product_title || '—' }}</p>
      <el-input
        v-model="retailRemarkDraft"
        type="textarea"
        :rows="4"
        maxlength="500"
        show-word-limit
        placeholder="后台备注，仅管理端可见"
      />
    </div>
    <template #footer>
      <el-button :disabled="retailRemarkSaving" @click="retailRemarkOpen = false">取消</el-button>
      <el-button type="primary" :loading="retailRemarkSaving" @click="submitRetailRemark">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.orders-remark-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.orders-remark-meta {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
