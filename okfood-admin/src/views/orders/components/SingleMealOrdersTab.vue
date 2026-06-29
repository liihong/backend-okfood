<script setup>
import { ChevronDown } from 'lucide-vue-next'
import AdminTable from '../../../components/AdminTable.vue'
import {
  isMemberCardPaidSingleMeal,
  singleMealOrderAmountDisplay,
} from '../../../utils/singleMealOrderDisplay.js'
import { SINGLE_PAY_TABS } from '../constants.js'
import {
  formatIsoDateZh,
  orderCreatedAtParts,
  singleOrderDeliveryAddressTextOnly,
} from '../utils/orderFormatters.js'
import {
  canDispatchActions,
  canCancelOrder,
  canMarkOrderComplete,
  canModifyOrder,
  canRefundWechatSingle,
  isSfCancelledRedispatch,
  isSingleRowSelectable,
} from '../utils/orderPermissions.js'
import {
  resolveSingleOrderMemberDisplayName,
  singleOrderStatusClass,
  singleOrderStatusLabelZh,
  singlePayClass,
} from '../utils/orderDisplay.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  singlePayFilter,
  singleDeliveryFilter,
  singleItems,
  singleOrderBucketSummary,
  loading,
  activeTab,
  page,
  pageSize,
  singleTableRef,
  selectedSingleRows,
  batchDispatchLoading,
  batchMarkCompleteLoading,
  batchCancelLoading,
  batchActionBusy,
  selectedDispatchableRows,
  selectedCompletableRows,
  selectedCancellableRows,
  onSingleSelectionChange,
  onBatchPushSfRetail,
  openBatchAssignCourier,
  onBatchMarkComplete,
  onBatchCancelOrders,
  clearSingleSelection,
  singleRowActionLoading,
  onSingleRowMoreCommand,
} = useOrdersManageInject()
</script>

<template>
  <div class="orders-manage-tab-bar orders-manage-tab-bar--filters">
    <el-tabs v-model="singlePayFilter" class="orders-pay-tabs">
      <el-tab-pane
        v-for="tab in SINGLE_PAY_TABS"
        :key="tab.value"
        :label="tab.label"
        :name="tab.value"
      />
    </el-tabs>
    <div class="orders-manage-tab-bar__row">
      <div class="orders-manage-tab-bar__filters">
        <div class="orders-filter-el">
          <span class="orders-filter-el-label">配送</span>
          <el-select
            v-model="singleDeliveryFilter"
            placeholder="全部"
            clearable
            class="orders-filter-el-select orders-filter-el-select--wide"
          >
            <el-option label="全部" value="" />
            <el-option label="待配送" value="awaiting" />
            <el-option label="已配送" value="delivered" />
          </el-select>
        </div>
      </div>
      <div class="orders-batch-bar__actions">
        <span v-if="selectedSingleRows.length" class="orders-batch-bar__count">
          已选 {{ selectedSingleRows.length }} 笔
        </span>
        <el-button
          type="primary"
          size="small"
          :loading="batchDispatchLoading"
          :disabled="!selectedDispatchableRows.length || batchActionBusy"
          @click="onBatchPushSfRetail"
        >
          推送顺丰
        </el-button>
        <el-button
          type="primary"
          size="small"
          plain
          :loading="batchDispatchLoading"
          :disabled="!selectedSingleRows.some((r) => canDispatchActions(r)) || batchActionBusy"
          @click="openBatchAssignCourier"
        >
          门店配送
        </el-button>
        <el-button
          type="success"
          size="small"
          plain
          :loading="batchMarkCompleteLoading"
          :disabled="!selectedCompletableRows.length || batchActionBusy"
          @click="onBatchMarkComplete"
        >
          批量完成
        </el-button>
        <el-button
          type="danger"
          size="small"
          plain
          :loading="batchCancelLoading"
          :disabled="!selectedCancellableRows.length || batchActionBusy"
          @click="onBatchCancelOrders"
        >
          批量取消
        </el-button>
        <el-button
          size="small"
          :disabled="!selectedSingleRows.length || batchActionBusy"
          @click="clearSingleSelection"
        >
          清空选择
        </el-button>
      </div>
    </div>
  </div>
  <p
    v-if="singleOrderBucketSummary"
    class="orders-manage-stats-line"
    role="status"
    aria-live="polite"
  >
    <span class="orders-manage-stats-line__label">汇总</span>
    已支付
    <strong class="orders-manage-stats-line__num orders-manage-stats-line__num--paid">{{
      singleOrderBucketSummary.paid
    }}</strong>
    <span class="orders-manage-stats-line__sep">·</span>
    待发货
    <strong class="orders-manage-stats-line__num orders-manage-stats-line__num--pending">{{
      singleOrderBucketSummary.pending_ship
    }}</strong>
    <span class="orders-manage-stats-line__sep">·</span>
    未支付
    <strong class="orders-manage-stats-line__num orders-manage-stats-line__num--unpaid">{{
      singleOrderBucketSummary.unpaid
    }}</strong>
    <span class="orders-manage-stats-line__sep">·</span>
    已取消
    <strong class="orders-manage-stats-line__num orders-manage-stats-line__num--cancelled">{{
      singleOrderBucketSummary.cancelled
    }}</strong>
    <span class="orders-manage-stats-line__sep">·</span>
    占用库存
    <strong class="orders-manage-stats-line__num">{{
      singleOrderBucketSummary.retail_inventory_portions
    }}</strong>
    份
    <span class="orders-manage-stats-line__hint"
      >（与供餐日、搜索、配送筛选一致；不含支付 Tab；待发货含门店自提「待自提」；占用库存=已支付未取消
      {{ singleOrderBucketSummary.paid_portions }} 份 + 待支付
      {{ singleOrderBucketSummary.pending_unpaid_portions }} 份，已取消不计入）</span
    >
  </p>
  <AdminTable
    ref="singleTableRef"
    variant="members"
    size="small"
    :data="singleItems"
    :loading="loading && activeTab === 'single'"
    row-key="id"
    empty-text="该供餐日暂无零售订单"
    @selection-change="onSingleSelectionChange"
  >
    <el-table-column type="selection" width="42" :selectable="isSingleRowSelectable" />
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
            :title="resolveSingleOrderMemberDisplayName(row)"
            >{{ resolveSingleOrderMemberDisplayName(row) }}</span
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
    <el-table-column label="餐品" min-width="140" show-overflow-tooltip class-name="orders-dish-col">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--dish">{{ row.dish_title || '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="份数" width="80" align="center" class-name="orders-qty-col">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--qty">{{ row.quantity ?? '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="供餐日" width="132" class-name="co-nowrap orders-meal-date-col">
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--date">{{
          formatIsoDateZh(row.delivery_date)
        }}</span>
      </template>
    </el-table-column>
    <el-table-column label="金额" width="116" align="center" class-name="td-mono orders-amount-col co-nowrap">
      <template #default="{ row }">
        <span
          class="orders-cell-pill orders-cell-pill--amount"
          :class="{ 'orders-cell-pill--member-card': isMemberCardPaidSingleMeal(row) }"
        >
          {{ singleMealOrderAmountDisplay(row) }}
        </span>
      </template>
    </el-table-column>
    <el-table-column label="支付" width="100" class-name="co-nowrap">
      <template #default="{ row }">
        <span :class="singlePayClass(row.pay_status)">{{ row.pay_status || '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="订单状态" width="120" class-name="co-nowrap">
      <template #default="{ row }">
        <span :class="singleOrderStatusClass(row)">{{ singleOrderStatusLabelZh(row) }}</span>
      </template>
    </el-table-column>
    <el-table-column
      label="配送/自提"
      header-align="left"
      align="left"
      min-width="480"
      :show-overflow-tooltip="false"
      class-name="orders-single-addr-col"
    >
      <template #default="{ row }">
        <div class="orders-addr-text">
          <template v-if="row.store_pickup">门店自提</template>
          <template v-else>{{ singleOrderDeliveryAddressTextOnly(row) }}</template>
        </div>
      </template>
    </el-table-column>
    <el-table-column label="地址备注" min-width="140" show-overflow-tooltip class-name="td-remarks">
      <template #default="{ row }">
        <template v-if="row.store_pickup">—</template>
        <template v-else>{{ (row.address_remarks || '').trim() || '—' }}</template>
      </template>
    </el-table-column>
    <el-table-column label="单号" width="120" class-name="td-mono orders-trade-no-col" show-overflow-tooltip>
      <template #default="{ row }">
        <span class="orders-cell-pill orders-cell-pill--trade-no">{{ row.out_trade_no || '—' }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="92" fixed="right" align="center" class-name="orders-col-more">
      <template #default="{ row }">
        <el-dropdown trigger="click" @command="(cmd) => onSingleRowMoreCommand(row, cmd)">
          <el-button
            type="primary"
            size="small"
            plain
            class="orders-more-trigger"
            :loading="singleRowActionLoading(row)"
            aria-label="更多操作"
          >
            更多
            <ChevronDown :size="14" class="orders-more-chevron" aria-hidden="true" stroke-width="2.25" />
          </el-button>
          <template #dropdown>
            <el-dropdown-menu class="orders-more-menu">
              <el-dropdown-item command="modify" :disabled="!canModifyOrder(row)">
                修改
              </el-dropdown-item>
              <el-dropdown-item
                command="sf"
                divided
                :disabled="!canDispatchActions(row) || row.store_pickup"
              >
                {{ isSfCancelledRedispatch(row) ? '重新推送到顺丰' : '推送到顺丰' }}
              </el-dropdown-item>
              <el-dropdown-item command="uu" :disabled="!canDispatchActions(row)">
                推送到 UU
              </el-dropdown-item>
              <el-dropdown-item command="courier" :disabled="!canDispatchActions(row)">
                门店自配送
              </el-dropdown-item>
              <el-dropdown-item command="complete" divided :disabled="!canMarkOrderComplete(row)">
                完成
              </el-dropdown-item>
              <el-dropdown-item command="cancel" :disabled="!canCancelOrder(row)">
                取消
              </el-dropdown-item>
              <el-dropdown-item command="refund" divided :disabled="!canRefundWechatSingle(row)">
                退款
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </el-table-column>
  </AdminTable>
</template>
