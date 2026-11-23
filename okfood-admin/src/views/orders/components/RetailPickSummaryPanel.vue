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

/** 卡片只展示规格名 */
function cardTitle(row) {
  const spec = String(row.spec_label || '').trim()
  if (spec) return spec
  const display = String(row.display_title || '').trim()
  const dot = display.indexOf(' · ')
  if (dot >= 0) return display.slice(dot + 3).trim() || display
  return display || '商品'
}

const sharedSpuTitle = computed(() => {
  const titles = new Set(
    items.value.map((row) => String(row.spu_title || '').trim()).filter(Boolean),
  )
  if (titles.size === 1) return [...titles][0]
  return ''
})

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
        <span v-if="sharedSpuTitle" class="retail-pick-board__spu" :title="sharedSpuTitle">
          {{ sharedSpuTitle }}
        </span>
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
          <div class="retail-pick-card__head">
            <el-tooltip
              :content="String(row.display_title || cardTitle(row))"
              placement="top"
              :show-after="400"
            >
              <h3 class="retail-pick-card__name">{{ cardTitle(row) }}</h3>
            </el-tooltip>
            <span v-if="row.sku_code" class="retail-pick-card__code" :title="`编码 ${row.sku_code}`">
              {{ row.sku_code }}
            </span>
          </div>
          <strong class="retail-pick-card__qty" :title="`${row.total_boxes} 盒`">
            <StatRollNumber :value="metric(row.total_boxes)" :replay-key="rollKey" />
            <span class="retail-pick-card__unit">盒</span>
          </strong>
        </article>
      </div>
    </div>
  </div>
</template>