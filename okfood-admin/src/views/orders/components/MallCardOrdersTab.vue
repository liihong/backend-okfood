<script setup>
import { ChevronDown } from 'lucide-vue-next'
import AdminTable from '../../../components/AdminTable.vue'
import { MALL_PAY_TABS } from '../constants.js'
import { orderCreatedAtParts } from '../utils/orderFormatters.js'
import { canRefundWechatMall } from '../utils/orderPermissions.js'
import { mallPayClass, mallSyncClass } from '../utils/orderDisplay.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  mallPayFilter,
  mallItems,
  loading,
  activeTab,
  page,
  pageSize,
  refundLoadingId,
  onMallRowMoreCommand,
} = useOrdersManageInject()
</script>

<template>
  <div class="orders-manage-tab-bar">
    <el-tabs v-model="mallPayFilter" class="orders-pay-tabs">
      <el-tab-pane
        v-for="tab in MALL_PAY_TABS"
        :key="tab.value"
        :label="tab.label"
        :name="tab.value"
      />
    </el-tabs>
  </div>
  <AdminTable
    variant="members"
    size="small"
    :data="mallItems"
    :loading="loading && activeTab === 'mall'"
    row-key="id"
    empty-text="当日暂无卡包订单"
  >
    <el-table-column label="序号" width="72" align="center" class-name="td-mono orders-idx-col">
      <template #default="{ $index }">
        <span class="orders-cell-pill orders-cell-pill--idx">{{
          (page - 1) * pageSize + $index + 1
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="下单时间" width="132" class-name="orders-created-at-col">
      <template #default="{ row }">
        <div class="orders-created-at">
          <span class="orders-created-at__date">{{
            orderCreatedAtParts(row.created_at).date
          }}</span>
          <span
            v-if="orderCreatedAtParts(row.created_at).time"
            class="orders-created-at__time"
            >{{ orderCreatedAtParts(row.created_at).time }}</span
          >
        </div>
      </template>
    </el-table-column>
    <el-table-column label="会员" min-width="132" class-name="orders-member-col">
      <template #default="{ row }">
        <div class="orders-m-cell">
          <span
            class="orders-cell-pill orders-cell-pill--member-name"
            :title="(row.member_name || '').trim() || '—'"
            >{{ (row.member_name || '').trim() || '—' }}</span
          >
          <span
            v-if="(row.member_phone || '').trim()"
            class="orders-cell-pill orders-cell-pill--member-phone td-mono"
            :title="row.member_phone || ''"
            >{{ (row.member_phone || '').trim() }}</span
          >
        </div>
      </template>
    </el-table-column>
    <el-table-column label="商品" min-width="140" show-overflow-tooltip class-name="orders-dish-col">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--dish">{{
          row.template_product_label || '—'
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="卡型" width="80" align="center" class-name="orders-qty-col">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--card-kind">{{
          row.card_kind || '—'
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="金额" width="116" align="center" class-name="td-mono orders-amount-col co-nowrap">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--amount">{{
          row.amount_yuan != null && row.amount_yuan !== '' ? row.amount_yuan : '—'
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="渠道" width="88" align="center" class-name="co-nowrap">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--channel">{{
          row.pay_channel || '—'
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="缴费" width="100" class-name="co-nowrap">
      <template #default="{ row }">
        <span :class="mallPayClass(row.pay_status)">{{ row.pay_status || '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="入账" width="100" class-name="co-nowrap">
      <template #default="{ row }">
        <span :class="mallSyncClass(row)">{{
          row.applied_to_member ? '已同步' : '未同步'
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="备注" min-width="140" show-overflow-tooltip class-name="td-remarks">
      <template #default="{ row }">{{
        (row.remark || '').trim() ? row.remark : '—'
      }}</template>
    </el-table-column>
    <el-table-column label="配送" width="108" align="center" class-name="co-nowrap">
      <template #default>
        <span class="orders-cell-pill orders-cell-pill--mall-tag">卡包无配送</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="92" fixed="right" align="center" class-name="orders-col-more">
      <template #default="{ row }">
        <el-dropdown trigger="click" @command="(cmd) => onMallRowMoreCommand(row, cmd)">
          <el-button
            type="primary"
            size="small"
            plain
            class="orders-more-trigger"
            :loading="refundLoadingId === row.id"
            aria-label="更多操作"
          >
            更多
            <ChevronDown :size="14" class="orders-more-chevron" aria-hidden="true" stroke-width="2.25" />
          </el-button>
          <template #dropdown>
            <el-dropdown-menu class="orders-more-menu">
              <el-dropdown-item command="refund" :disabled="!canRefundWechatMall(row)">
                微信退款
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </el-table-column>
  </AdminTable>
</template>
