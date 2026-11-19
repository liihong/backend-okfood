<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import StatRollNumber from '../../../components/StatRollNumber.vue'
import { adminStoreId } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { fetchRetailPickSummary } from '../../../api/retailPickSummary.js'

defineOptions({ name: 'RetailPickSummaryPanel' })

const loading = ref(false)
/** 每次拉到新数据 +1，汇总和盒数从 0 再滚一遍 */
const rollKey = ref(0)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const summary = ref(null)

/** @param {unknown} value */
function metric(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const items = computed(() => {
  const list = summary.value?.items
  return Array.isArray(list) ? list : []
})

const deliveryTotal = computed(() =>
  items.value.reduce((n, row) => n + Number(row.delivery_boxes || 0), 0),
)
const pickupTotal = computed(() =>
  items.value.reduce((n, row) => n + Number(row.pickup_boxes || 0), 0),
)

async function load() {
  if (loading.value) return
  loading.value = true
  try {
    summary.value = await fetchRetailPickSummary({ storeId: adminStoreId.value })
    rollKey.value += 1
  } catch (e) {
    showToast(e instanceof Error ? e.message : '加载备货汇总失败', 'error')
    summary.value = null
  } finally {
    loading.value = false
  }
}

function onPrint() {
  window.print()
}

defineExpose({ reload: load })

onMounted(() => {
  void load()
})

onActivated(() => {
  void load()
})
</script>

<template>
  <div v-loading="loading" class="retail-pick-board">
    <header class="retail-pick-board__head">
      <div class="retail-pick-board__titles">
        <h2 class="retail-pick-board__title">厨师备货看板</h2>
        <el-tag size="small" effect="plain" round class="retail-pick-board__scope">
          {{ summary?.scope_label || '已支付 · 已接单 · 待发货' }}
        </el-tag>
      </div>
      <div class="retail-pick-board__head-actions">
        <el-button size="small" round :loading="loading" @click="load">刷新</el-button>
        <el-button size="small" round type="primary" :disabled="!items.length" @click="onPrint">
          打印
        </el-button>
      </div>
    </header>

    <div v-if="summary" class="retail-pick-board__stats" role="status">
      <span class="retail-pick-stat retail-pick-stat--total">
        <span class="retail-pick-stat__label">待备</span>
        <strong class="retail-pick-stat__num retail-pick-stat__num--total">
          <StatRollNumber :value="metric(summary.grand_total_boxes)" :replay-key="rollKey" />
          <span class="retail-pick-stat__unit">盒</span>
        </strong>
      </span>
      <span class="retail-pick-stat">
        <span class="retail-pick-stat__label">SKU</span>
        <strong class="retail-pick-stat__num">
          <StatRollNumber :value="metric(summary.sku_count)" :replay-key="rollKey" />
          <span class="retail-pick-stat__unit">种</span>
        </strong>
      </span>
      <span class="retail-pick-stat">
        <span class="retail-pick-stat__label">订单</span>
        <strong class="retail-pick-stat__num">
          <StatRollNumber :value="metric(summary.order_count)" :replay-key="rollKey" />
          <span class="retail-pick-stat__unit">笔</span>
        </strong>
      </span>
      <span class="retail-pick-stat">
        <span class="retail-pick-stat__label">配送</span>
        <strong class="retail-pick-stat__num retail-pick-stat__num--ship">
          <StatRollNumber :value="deliveryTotal" :replay-key="rollKey" />
          <span class="retail-pick-stat__unit">盒</span>
        </strong>
      </span>
      <span class="retail-pick-stat">
        <span class="retail-pick-stat__label">自提</span>
        <strong class="retail-pick-stat__num retail-pick-stat__num--pickup">
          <StatRollNumber :value="pickupTotal" :replay-key="rollKey" />
          <span class="retail-pick-stat__unit">盒</span>
        </strong>
      </span>
    </div>

    <div class="retail-pick-board__body">
      <el-empty
        v-if="!loading && !items.length"
        class="retail-pick-board__empty"
        description="当前没有待发货订单"
      />
      <div v-else-if="items.length" class="retail-pick-board__grid" role="list">
        <article
          v-for="row in items"
          :key="row.retail_product_id"
          class="retail-pick-card"
          role="listitem"
        >
          <strong class="retail-pick-card__qty" :title="`${row.total_boxes} 盒`">
            <StatRollNumber :value="metric(row.total_boxes)" :replay-key="rollKey" />
            <span class="retail-pick-card__unit">盒</span>
          </strong>
          <el-tooltip :content="String(row.display_title || '')" placement="top" :show-after="300">
            <h3 class="retail-pick-card__name">{{ row.display_title }}</h3>
          </el-tooltip>
          <p class="retail-pick-card__code">{{ row.sku_code ? `编码 ${row.sku_code}` : ' ' }}</p>
          <div class="retail-pick-card__split">
            <el-tag
              v-if="row.delivery_boxes > 0"
              size="small"
              effect="plain"
              round
              class="retail-pick-card__tag retail-pick-card__tag--ship"
            >
              配送 {{ row.delivery_boxes }}
            </el-tag>
            <el-tag
              v-if="row.pickup_boxes > 0"
              size="small"
              effect="plain"
              round
              type="success"
              class="retail-pick-card__tag"
            >
              自提 {{ row.pickup_boxes }}
            </el-tag>
            <el-tag size="small" effect="plain" round type="info" class="retail-pick-card__tag">
              {{ row.order_count }} 单
            </el-tag>
          </div>
        </article>
      </div>
    </div>
  </div>
</template>