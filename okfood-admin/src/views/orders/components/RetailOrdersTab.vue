<script setup>
import { ChevronDown } from 'lucide-vue-next'
import AdminTable from '../../../components/AdminTable.vue'
import { RETAIL_DELIVERY_TABS } from '../constants.js'
import {
  retailJuiceDurationBadge,
  singleOrderStatusClass,
  singleOrderStatusLabelZh,
} from '../utils/orderDisplay.js'
import { orderCreatedAtParts, singleOrderDeliveryAddressTextOnly } from '../utils/orderFormatters.js'
import {
  canAcceptRetailOrder,
  canDispatchActions,
  canCancelOrder,
  canMarkOrderComplete,
  canModifyRetailOrder,
  canRefundWechatRetail,
} from '../utils/orderPermissions.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  retailDeliveryFilter,
  retailItems,
  loading,
  activeTab,
  page,
  pageSize,
  onRetailRowMoreCommand,
} = useOrdersManageInject()
</script>

<template>
  <div class="orders-manage-tab-bar">
    <el-tabs v-model="retailDeliveryFilter" class="orders-pay-tabs">
      <el-tab-pane
        v-for="tab in RETAIL_DELIVERY_TABS"
        :key="'r-' + tab.value"
        :label="tab.label"
        :name="tab.value"
      />
    </el-tabs>
  </div>
  <AdminTable
    variant="members"
    size="small"
    :data="retailItems"
    :loading="loading && activeTab === 'retail'"
    row-key="id"
    empty-text="暂无商城订单"
  >
    <el-table-column label="序号" width="72" align="center">
      <template #default="{ $index }">
        {{ (page - 1) * pageSize + $index + 1 }}
      </template>
    </el-table-column>
    <el-table-column label="下单时间" width="132">
      <template #default="{ row }">
        {{ orderCreatedAtParts(row.created_at).date }}
        {{ orderCreatedAtParts(row.created_at).time }}
      </template>
    </el-table-column>
    <el-table-column label="会员" min-width="120">
      <template #default="{ row }">
        {{ (row.member_name || '').trim() || '—' }}
        <span v-if="row.member_phone" class="td-mono">{{ row.member_phone }}</span>
      </template>
    </el-table-column>
    <el-table-column label="商品" min-width="180">
      <template #default="{ row }">
        <div class="retail-product-cell">
          <template v-for="badge in [retailJuiceDurationBadge(row.product_title)]" :key="badge?.days ?? 'plain'">
            <span
              v-if="badge"
              class="retail-juice-duration-badge"
              :class="badge.className"
              :title="row.product_title"
            >
              {{ badge.badge }}
            </span>
            <span v-else class="retail-product-title">{{ row.product_title || '—' }}</span>
          </template>
        </div>
      </template>
    </el-table-column>
    <el-table-column label="数量" width="72" align="center">
      <template #default="{ row }">×{{ row.quantity || 1 }}</template>
    </el-table-column>
    <el-table-column label="金额" width="100" prop="amount_yuan" />
    <el-table-column label="支付" width="88">
      <template #default="{ row }">{{ row.pay_status || '—' }}</template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <span :class="singleOrderStatusClass(row)">{{ singleOrderStatusLabelZh(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="配送" min-width="120" show-overflow-tooltip>
      <template #default="{ row }">{{
        row.store_pickup ? '门店自提' : singleOrderDeliveryAddressTextOnly(row)
      }}</template>
    </el-table-column>
    <el-table-column label="备注" min-width="140" show-overflow-tooltip class-name="td-remarks">
      <template #default="{ row }">{{
        (row.remark || '').trim() ? row.remark : '—'
      }}</template>
    </el-table-column>
    <el-table-column label="操作" width="92" fixed="right" align="center">
      <template #default="{ row }">
        <el-dropdown trigger="click" @command="(cmd) => onRetailRowMoreCommand(row, cmd)">
          <el-button type="primary" size="small" plain class="orders-more-trigger">
            更多
            <ChevronDown :size="14" class="orders-more-chevron" />
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="modify" :disabled="!canModifyRetailOrder(row)">
                修改
              </el-dropdown-item>
              <el-dropdown-item command="accept" :disabled="!canAcceptRetailOrder(row)">
                接单
              </el-dropdown-item>
              <el-dropdown-item command="sf" :disabled="!canDispatchActions(row) || row.store_pickup">
                推送到顺丰
              </el-dropdown-item>
              <el-dropdown-item command="courier" :disabled="!canDispatchActions(row)">
                门店自配送
              </el-dropdown-item>
              <el-dropdown-item command="complete" :disabled="!canMarkOrderComplete(row)">
                完成
              </el-dropdown-item>
              <el-dropdown-item command="cancel" :disabled="!canCancelOrder(row)">
                取消
              </el-dropdown-item>
              <el-dropdown-item command="refund" divided :disabled="!canRefundWechatRetail(row)">
                退款
              </el-dropdown-item>
              <el-dropdown-item command="remark">编辑备注</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </el-table-column>
  </AdminTable>
</template>
