<script setup>
import { ChevronDown } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import AdminTable from '../../../components/AdminTable.vue'
import {
  isMemberCardPaidSingleMeal,
  singleMealOrderAmountDisplay,
} from '../../../utils/singleMealOrderDisplay.js'
import { SINGLE_FULFILLMENT_TABS } from '../constants.js'
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

const MOBILE_MEDIA = '(max-width: 768px)'

const {
  singleFulfillmentFilter,
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

/** 窄屏（手机）使用卡片列表，桌面保留表格 */
const isNarrowScreen = ref(
  typeof window !== 'undefined' && window.matchMedia(MOBILE_MEDIA).matches,
)

let mobileMediaQuery = null

function syncNarrowScreen() {
  if (!mobileMediaQuery) return
  isNarrowScreen.value = mobileMediaQuery.matches
}

onMounted(() => {
  if (typeof window === 'undefined') return
  mobileMediaQuery = window.matchMedia(MOBILE_MEDIA)
  syncNarrowScreen()
  mobileMediaQuery.addEventListener('change', syncNarrowScreen)
})

onUnmounted(() => {
  mobileMediaQuery?.removeEventListener('change', syncNarrowScreen)
})

function singleRowIndex(index) {
  return (page.value - 1) * pageSize.value + index + 1
}

/** 手机端勾选：与表格 selection 共用 selectedSingleRows */
function isSingleMobileSelected(row) {
  return selectedSingleRows.value.some((r) => r.id === row.id)
}

function onSingleMobileSelectChange(row, checked) {
  if (checked) {
    if (!selectedSingleRows.value.some((r) => r.id === row.id)) {
      onSingleSelectionChange([...selectedSingleRows.value, row])
    }
    return
  }
  onSingleSelectionChange(selectedSingleRows.value.filter((r) => r.id !== row.id))
}
</script>

<template>
  <div class="single-orders-tab">
    <p
      v-if="singleOrderBucketSummary"
      class="orders-manage-stats-line single-orders-tab__summary"
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
        >（供餐日全天概览，不受发货 Tab 影响；待发货含门店自提「待自提」；占用库存=已支付未取消
        {{ singleOrderBucketSummary.paid_portions }} 份 + 待支付
        {{ singleOrderBucketSummary.pending_unpaid_portions }} 份，已取消不计入）</span
      >
    </p>

    <div class="orders-manage-tab-bar single-orders-tab-bar single-orders-tab__filter-bar orders-tab-bar--inline">
      <el-tabs
        v-model="singleFulfillmentFilter"
        class="orders-pay-tabs single-orders-pay-tabs orders-tab-bar__tabs"
      >
        <el-tab-pane
          v-for="tab in SINGLE_FULFILLMENT_TABS"
          :key="tab.value"
          :label="tab.label"
          :name="tab.value"
        />
      </el-tabs>
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

    <!-- 桌面：表格 -->
    <AdminTable
      v-if="!isNarrowScreen"
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
          <span class="orders-cell-pill orders-cell-pill--idx">{{ singleRowIndex($index) }}</span>
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

    <!-- 手机：卡片列表 -->
    <div
      v-else
      v-loading="loading && activeTab === 'single'"
      class="retail-orders-mobile-list"
    >
      <p
        v-if="!singleItems.length && !(loading && activeTab === 'single')"
        class="retail-orders-mobile-empty"
      >
        该供餐日暂无零售订单
      </p>
      <article v-for="row in singleItems" :key="row.id" class="retail-order-card">
        <header class="retail-order-card__head">
          <div class="retail-order-card__head-left">
            <el-checkbox
              v-if="isSingleRowSelectable(row)"
              :model-value="isSingleMobileSelected(row)"
              class="retail-order-card__check"
              @change="(checked) => onSingleMobileSelectChange(row, checked)"
            />
            <span class="retail-order-card__order-id">#{{ row.id }}</span>
          </div>
          <time class="retail-order-card__time">
            {{ orderCreatedAtParts(row.created_at).date }}
            <template v-if="orderCreatedAtParts(row.created_at).time">
              {{ orderCreatedAtParts(row.created_at).time }}
            </template>
          </time>
        </header>

        <section class="retail-order-card__goods">
          <div class="retail-order-card__goods-info">
            <span class="orders-cell-pill orders-cell-pill--dish">{{ row.dish_title || '—' }}</span>
            <span class="retail-order-card__meal-date"
              >供餐 {{ formatIsoDateZh(row.delivery_date) }}</span
            >
          </div>
          <div class="retail-order-card__goods-meta">
            <span
              class="retail-order-card__amount"
              :class="{ 'retail-order-card__amount--member-card': isMemberCardPaidSingleMeal(row) }"
              >{{ singleMealOrderAmountDisplay(row) }}</span
            >
            <span class="retail-order-card__qty">×{{ row.quantity ?? 1 }}</span>
          </div>
        </section>

        <section class="retail-order-card__ship">
          <div class="retail-order-card__ship-contact">
            <span class="retail-order-card__ship-name">{{
              resolveSingleOrderMemberDisplayName(row)
            }}</span>
            <span
              v-if="(row.member_phone || '').trim()"
              class="retail-order-card__ship-phone td-mono"
              >{{ row.member_phone }}</span
            >
          </div>
          <p class="retail-order-card__ship-addr">
            {{ row.store_pickup ? '门店自提' : singleOrderDeliveryAddressTextOnly(row) }}
          </p>
        </section>

        <p
          v-if="!row.store_pickup && (row.address_remarks || '').trim()"
          class="retail-order-card__remark"
        >
          <span class="retail-order-card__remark-label">地址备注</span>
          <span class="retail-order-card__remark-text">{{ row.address_remarks }}</span>
        </p>

        <footer class="retail-order-card__footer">
          <el-dropdown trigger="click" @command="(cmd) => onSingleRowMoreCommand(row, cmd)">
            <el-button
              type="primary"
              size="small"
              plain
              class="orders-more-trigger retail-order-card__more-btn"
              :loading="singleRowActionLoading(row)"
            >
              更多操作
              <ChevronDown :size="14" class="orders-more-chevron" />
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
        </footer>
      </article>
    </div>
  </div>
</template>
