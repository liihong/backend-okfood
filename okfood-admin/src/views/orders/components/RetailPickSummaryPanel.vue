<script setup>
import { computed, onActivated, onMounted, ref } from 'vue'
import { Printer, RefreshCw } from 'lucide-vue-next'
import { adminStoreId } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { fetchRetailPickSummary } from '../../../api/retailPickSummary.js'

defineOptions({ name: 'RetailPickSummaryPanel' })

const loading = ref(false)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const summary = ref(null)

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
  <div class="retail-pick-board" :class="{ 'retail-pick-board--loading': loading }">
    <header class="retail-pick-board__head">
      <div class="retail-pick-board__titles">
        <h2 class="retail-pick-board__title">厨师备货看板</h2>
        <p class="retail-pick-board__scope">
          {{ summary?.scope_label || '已支付 · 已接单 · 待发货' }}
        </p>
      </div>
      <div class="retail-pick-board__head-actions">
        <button type="button" class="btn-sm orders-manage-refresh" :disabled="loading" @click="load">
          <RefreshCw :size="16" stroke-width="2" />
          {{ loading ? '刷新中…' : '刷新' }}
        </button>
        <button type="button" class="btn-sm" :disabled="!items.length" @click="onPrint">
          <Printer :size="16" stroke-width="2" />
          打印
        </button>
      </div>
    </header>

    <div v-if="summary" class="retail-pick-board__kpi">
      <article class="retail-pick-kpi retail-pick-kpi--primary">
        <span class="retail-pick-kpi__label">待备总盒数</span>
        <span class="retail-pick-kpi__value">{{ summary.grand_total_boxes }}</span>
        <span class="retail-pick-kpi__hint">全 SKU 合计</span>
      </article>
      <article class="retail-pick-kpi">
        <span class="retail-pick-kpi__label">SKU 种类</span>
        <span class="retail-pick-kpi__value">{{ summary.sku_count }}</span>
      </article>
      <article class="retail-pick-kpi">
        <span class="retail-pick-kpi__label">涉及订单</span>
        <span class="retail-pick-kpi__value">{{ summary.order_count }}</span>
        <span class="retail-pick-kpi__hint">笔</span>
      </article>
      <article class="retail-pick-kpi">
        <span class="retail-pick-kpi__label">配送</span>
        <span class="retail-pick-kpi__value retail-pick-kpi__value--sub">{{ deliveryTotal }}</span>
        <span class="retail-pick-kpi__hint">盒</span>
      </article>
      <article class="retail-pick-kpi">
        <span class="retail-pick-kpi__label">自提</span>
        <span class="retail-pick-kpi__value retail-pick-kpi__value--sub">{{ pickupTotal }}</span>
        <span class="retail-pick-kpi__hint">盒</span>
      </article>
    </div>

    <p v-if="loading && !items.length" class="retail-pick-board__empty">正在加载…</p>
    <p v-else-if="!items.length" class="retail-pick-board__empty">
      当前没有待发货订单，接单后才会出现在这里。
    </p>

    <div v-else class="retail-pick-board__grid" role="list">
      <article
        v-for="row in items"
        :key="row.retail_product_id"
        class="retail-pick-card"
        role="listitem"
      >
        <div class="retail-pick-card__qty" :title="`${row.total_boxes} 盒`">
          {{ row.total_boxes }}
        </div>
        <div class="retail-pick-card__unit">盒</div>
        <h3 class="retail-pick-card__name" :title="row.display_title">{{ row.display_title }}</h3>
        <p v-if="row.sku_code" class="retail-pick-card__code">编码 {{ row.sku_code }}</p>
        <div class="retail-pick-card__split">
          <span v-if="row.delivery_boxes > 0" class="retail-pick-card__tag retail-pick-card__tag--ship">
            配送 {{ row.delivery_boxes }}
          </span>
          <span v-if="row.pickup_boxes > 0" class="retail-pick-card__tag retail-pick-card__tag--pickup">
            自提 {{ row.pickup_boxes }}
          </span>
          <span class="retail-pick-card__tag retail-pick-card__tag--orders">
            {{ row.order_count }} 单
          </span>
        </div>
      </article>
    </div>
  </div>
</template>