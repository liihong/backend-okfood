<script setup>
import { RefreshCw, Search } from 'lucide-vue-next'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  dateFilterLabel,
  orderDate,
  searchQuery,
  activeTab,
  syncDeliveryLoading,
  loading,
  fetchActive,
  onSyncDeliveryStatus,
} = useOrdersManageInject()
</script>

<template>
  <div class="table-header table-header--members table-header--couriers-row orders-manage-toolbar">
    <label v-if="activeTab !== 'retail'" class="orders-manage-date">
      <span class="orders-manage-date-label">{{ dateFilterLabel }}</span>
      <el-date-picker
        v-model="orderDate"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="选择日期"
        teleported
      />
    </label>
    <div class="search-box search-box--flex orders-manage-search">
      <Search :size="18" />
      <el-input
        v-model="searchQuery"
        clearable
        placeholder="手机前缀或会员姓名…"
        class="orders-manage-search-input"
      />
    </div>
    <button type="button" class="btn-sm orders-manage-refresh" @click="fetchActive">
      <RefreshCw :size="16" stroke-width="2" />
      刷新
    </button>
    <button
      v-if="activeTab === 'single' || activeTab === 'retail'"
      type="button"
      class="btn-sm orders-manage-sync-delivery"
      :disabled="syncDeliveryLoading || loading"
      @click="onSyncDeliveryStatus"
    >
      {{ syncDeliveryLoading ? '同步中…' : '同步订单状态' }}
    </button>
  </div>
</template>
