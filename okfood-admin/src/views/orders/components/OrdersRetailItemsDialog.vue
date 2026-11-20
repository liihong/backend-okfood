<script setup>
import { computed } from 'vue'
import {
  resolveRetailOrderLineItems,
  retailOrderTotalBoxes,
} from '../utils/orderDisplay.js'

const open = defineModel('open', { type: Boolean, default: false })
const emit = defineEmits(['closed'])

/** @type {import('vue').PropType<Record<string, unknown> | null>} */
const props = defineProps({
  order: { type: Object, default: null },
})

const lineItems = computed(() => resolveRetailOrderLineItems(props.order))
const totalBoxes = computed(() => retailOrderTotalBoxes(props.order))
const orderId = computed(() => (props.order?.id != null ? String(props.order.id) : ''))
const summaryTitle = computed(() => String(props.order?.product_title || '').trim() || '—')
</script>

<template>
  <el-dialog
    v-model="open"
    width="520px"
    title="商品明细"
    destroy-on-close
    align-center
    @closed="emit('closed')"
  >
    <div v-if="order" class="orders-retail-items-body">
      <p class="orders-retail-items-meta">
        订单
        <span v-if="orderId" class="td-mono">#{{ orderId }}</span>
        <template v-if="orderId"> · </template>
        共 {{ totalBoxes }} 盒
      </p>
      <p v-if="lineItems.length > 1" class="orders-retail-items-summary" :title="summaryTitle">
        {{ summaryTitle }}
      </p>
      <el-table :data="lineItems" border stripe size="small" empty-text="暂无明细">
        <el-table-column label="商品" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.title }}
          </template>
        </el-table-column>
        <el-table-column label="规格" min-width="96" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.specLabel || '—' }}
          </template>
        </el-table-column>
        <el-table-column label="盒数" width="72" align="center">
          <template #default="{ row }">×{{ row.quantity }}</template>
        </el-table-column>
        <el-table-column label="单价" width="80" align="right" class-name="td-mono">
          <template #default="{ row }">
            {{ row.unitPriceYuan ? `¥${row.unitPriceYuan}` : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="小计" width="80" align="right" class-name="td-mono">
          <template #default="{ row }">
            {{ row.lineAmountYuan ? `¥${row.lineAmountYuan}` : '—' }}
          </template>
        </el-table-column>
      </el-table>
    </div>
    <template #footer>
      <el-button round type="primary" @click="open = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.orders-retail-items-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.orders-retail-items-meta {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.orders-retail-items-summary {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-text-strong, #0f172a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>