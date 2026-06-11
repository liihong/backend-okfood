<script setup>
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  adminAccessToken,
  page,
  pageSize,
  totalPages,
  activeTabTotal,
  goPrev,
  goNext,
} = useOrdersManageInject()
</script>

<template>
  <div v-if="adminAccessToken" class="members-pagination">
    <div class="orders-page-size">
      <span>每页</span>
      <el-select v-model="pageSize" class="orders-page-size-select">
        <el-option :value="10" label="10" />
        <el-option :value="20" label="20" />
        <el-option :value="50" label="50" />
      </el-select>
      <span>条</span>
    </div>
    <button type="button" class="btn-sm" :disabled="page <= 1" @click="goPrev">上一页</button>
    <span class="members-page-meta">第 {{ page }} / {{ totalPages }} 页 · 共 {{ activeTabTotal }} 条</span>
    <button type="button" class="btn-sm" :disabled="page >= totalPages" @click="goNext">
      下一页
    </button>
  </div>
</template>
