<script setup>
import { ChevronDown, Plus } from 'lucide-vue-next'
import { onMounted, onUnmounted, ref } from 'vue'
import AdminTable from '../../../components/AdminTable.vue'
import RetailManualOrderDialog from './RetailManualOrderDialog.vue'
import { RETAIL_DELIVERY_TABS } from '../constants.js'
import {
  retailJuiceDurationBadge,
  resolveSingleOrderMemberDisplayName,
  singleOrderStatusClass,
  singleOrderStatusLabelZh,
} from '../utils/orderDisplay.js'
import { orderCreatedAtParts, singleOrderDeliveryAddressTextOnly } from '../utils/orderFormatters.js'
import {
  canAcceptRetailOrder,
  canRevokeAcceptRetailOrder,
  canDispatchActions,
  canCancelOrder,
  canMarkOrderComplete,
  canModifyRetailOrder,
  canRefundWechatRetail,
  isRetailRowSelectable,
} from '../utils/orderPermissions.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const MOBILE_MEDIA = '(max-width: 768px)'

const {
  retailDeliveryFilter,
  retailItems,
  loading,
  activeTab,
  page,
  pageSize,
  retailTableRef,
  selectedRetailRows,
  batchDispatchLoading,
  batchActionBusy,
  selectedRetailDispatchableRows,
  onRetailSelectionChange,
  onBatchPushSfRetailOrders,
  clearRetailSelection,
  onRetailRowMoreCommand,
  fetchActive,
} = useOrdersManageInject()

const manualOrderOpen = ref(false)

function onManualOrderSuccess() {
  void fetchActive()
}

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

function retailRowIndex(index) {
  return (page.value - 1) * pageSize.value + index + 1
}

/** 手机端勾选：与表格 selection 共用 selectedRetailRows */
function isRetailMobileSelected(row) {
  return selectedRetailRows.value.some((r) => r.id === row.id)
}

function onRetailMobileSelectChange(row, checked) {
  if (checked) {
    if (!selectedRetailRows.value.some((r) => r.id === row.id)) {
      onRetailSelectionChange([...selectedRetailRows.value, row])
    }
    return
  }
  onRetailSelectionChange(selectedRetailRows.value.filter((r) => r.id !== row.id))
}
</script>

<template>
  <div class="retail-orders-tab">
    <div class="orders-manage-tab-bar retail-orders-tab-bar retail-orders-tab__filter-bar orders-tab-bar--inline">
      <el-tabs
        v-model="retailDeliveryFilter"
        class="orders-pay-tabs retail-orders-pay-tabs orders-tab-bar__tabs"
      >
        <el-tab-pane
          v-for="tab in RETAIL_DELIVERY_TABS"
          :key="'r-' + tab.value"
          :label="tab.label"
          :name="tab.value"
        />
      </el-tabs>
      <div class="orders-batch-bar__actions">
        <el-button type="primary" size="small" @click="manualOrderOpen = true">
          <Plus :size="14" style="margin-right: 4px" />
          手动建单
        </el-button>
        <span v-if="selectedRetailRows.length" class="orders-batch-bar__count">
          已选 {{ selectedRetailRows.length }} 笔
        </span>
        <el-button
          type="primary"
          size="small"
          :loading="batchDispatchLoading"
          :disabled="!selectedRetailDispatchableRows.length || batchActionBusy"
          @click="onBatchPushSfRetailOrders"
        >
          批量推送到顺丰
        </el-button>
        <el-button
          size="small"
          :disabled="!selectedRetailRows.length || batchActionBusy"
          @click="clearRetailSelection"
        >
          清空选择
        </el-button>
      </div>
    </div>

    <!-- 桌面：表格 -->
    <AdminTable
      v-if="!isNarrowScreen"
      ref="retailTableRef"
      variant="members"
      size="small"
      :data="retailItems"
      :loading="loading && activeTab === 'retail'"
      row-key="id"
      empty-text="暂无商城订单"
      @selection-change="onRetailSelectionChange"
    >
      <el-table-column type="selection" width="42" :selectable="isRetailRowSelectable" />
      <el-table-column label="序号" width="72" align="center" class-name="td-mono orders-idx-col">
        <template #default="{ $index }">
          <span class="orders-cell-pill orders-cell-pill--idx">{{ retailRowIndex($index) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="订单号" width="88" align="center" class-name="td-mono orders-order-id-col">
        <template #default="{ row }">
          <span class="orders-cell-pill orders-cell-pill--order-id" :title="`订单 #${row.id}`"
            >#{{ row.id }}</span
          >
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
            <template
              v-for="badge in [retailJuiceDurationBadge(row.product_title)]"
              :key="badge?.days ?? 'plain'"
            >
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
                <el-dropdown-item command="revokeAccept" :disabled="!canRevokeAcceptRetailOrder(row)">
                  取消接单
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

    <!-- 手机：卡片列表 -->
    <div
      v-else
      v-loading="loading && activeTab === 'retail'"
      class="retail-orders-mobile-list"
    >
      <p v-if="!retailItems.length && !(loading && activeTab === 'retail')" class="retail-orders-mobile-empty">
        暂无商城订单
      </p>
      <article
        v-for="row in retailItems"
        :key="row.id"
        class="retail-order-card"
      >
        <!-- 顶栏：订单号 + 下单时间 -->
        <header class="retail-order-card__head">
          <div class="retail-order-card__head-left">
            <el-checkbox
              v-if="isRetailRowSelectable(row)"
              :model-value="isRetailMobileSelected(row)"
              class="retail-order-card__check"
              @change="(checked) => onRetailMobileSelectChange(row, checked)"
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

        <!-- 商品区 -->
        <section class="retail-order-card__goods">
          <div class="retail-order-card__goods-info">
            <div class="retail-product-cell">
              <template
                v-for="badge in [retailJuiceDurationBadge(row.product_title)]"
                :key="badge?.days ?? 'plain-m'"
              >
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
          </div>
          <div class="retail-order-card__goods-meta">
            <span class="retail-order-card__amount">{{ row.amount_yuan }}</span>
            <span class="retail-order-card__qty">×{{ row.quantity || 1 }}</span>
          </div>
        </section>

        <!-- 配送区 -->
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
            {{
              row.store_pickup ? '门店自提' : singleOrderDeliveryAddressTextOnly(row)
            }}
          </p>
        </section>

        <!-- 备注（有则显示） -->
        <p v-if="(row.remark || '').trim()" class="retail-order-card__remark">
          <span class="retail-order-card__remark-label">备注</span>
          <span class="retail-order-card__remark-text">{{ row.remark }}</span>
        </p>

        <!-- 底栏：操作 -->
        <footer class="retail-order-card__footer">
          <el-dropdown trigger="click" @command="(cmd) => onRetailRowMoreCommand(row, cmd)">
            <el-button type="primary" size="small" plain class="orders-more-trigger retail-order-card__more-btn">
              更多操作
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
                <el-dropdown-item command="revokeAccept" :disabled="!canRevokeAcceptRetailOrder(row)">
                  取消接单
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
        </footer>
      </article>
    </div>

    <RetailManualOrderDialog v-model="manualOrderOpen" @success="onManualOrderSuccess" />
  </div>
</template>
