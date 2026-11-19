<script setup>
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import StatRollNumber from '../../../components/StatRollNumber.vue'
import {
  adminAccessToken,
  adminStoreId,
  apiJson,
  handleAdminLogout,
} from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { fetchRetailPickSummary } from '../../../api/retailPickSummary.js'

defineOptions({ name: 'PickBoardView' })

/** 全部分类 */
const ALL_CATEGORY = 'all'
/** 备货看板目前只看这些商品分类。果蔬汁、月饼不进这张板 */
const PREP_CATEGORY_NAMES = ['馄饨']

const loading = ref(false)
/** 每次拉到新数据 +1，盒数从 0 再滚一遍 */
const rollKey = ref(0)
/** @type {import('vue').Ref<string>} */
const categoryKey = ref(ALL_CATEGORY)
/** @type {import('vue').Ref<Record<string, unknown> | null>} */
const summary = ref(null)
/** @type {import('vue').Ref<Array<{ id: number, name: string, sort_order: number, is_active: boolean }>>} */
const categories = ref([])

/** @param {unknown} value */
function metric(value) {
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

const items = computed(() => {
  const list = summary.value?.items
  return Array.isArray(list) ? list : []
})

/** 分类 id → 名称。停用分类只要还有待备货也保留名字 */
const categoryNameById = computed(() => {
  /** @type {Map<string, string>} */
  const map = new Map()
  for (const row of categories.value) {
    map.set(String(row.id), row.name)
  }
  return map
})

/** 没有分类的口味 */
const UNCATEGORIZED = 'none'

/**
 * @param {unknown} categoryId
 */
function categoryKeyOf(categoryId) {
  if (categoryId == null || categoryId === '') return UNCATEGORIZED
  return String(categoryId)
}

const prepCategoryIds = computed(() => {
  const ids = new Set()
  for (const row of categories.value) {
    if (PREP_CATEGORY_NAMES.includes(String(row.name || '').trim())) ids.add(String(row.id))
  }
  return ids
})

/** 只保留馄饨；果蔬汁、月饼即使有待备货也不出现 */
const prepItems = computed(() =>
  items.value.filter((row) => prepCategoryIds.value.has(categoryKeyOf(row.category_id))),
)

const categoryChips = computed(() => {
  /** @type {Array<{ key: string, label: string }>} */
  const chips = [{ key: ALL_CATEGORY, label: '全部' }]
  const rows = [...categories.value].sort((a, b) => {
    const order = Number(a.sort_order || 0) - Number(b.sort_order || 0)
    if (order !== 0) return order
    return String(a.name).localeCompare(String(b.name), 'zh-CN')
  })
  for (const row of rows) {
    if (!PREP_CATEGORY_NAMES.includes(String(row.name || '').trim())) continue
    chips.push({ key: String(row.id), label: row.name })
  }
  return chips
})

const filteredItems = computed(() => {
  if (categoryKey.value === ALL_CATEGORY) return prepItems.value
  return prepItems.value.filter((row) => categoryKeyOf(row.category_id) === categoryKey.value)
})

const deliveryTotal = computed(() =>
  filteredItems.value.reduce((n, row) => n + Number(row.delivery_boxes || 0), 0),
)
const pickupTotal = computed(() =>
  filteredItems.value.reduce((n, row) => n + Number(row.pickup_boxes || 0), 0),
)
const boxTotal = computed(() =>
  filteredItems.value.reduce((n, row) => n + Number(row.total_boxes || 0), 0),
)
const skuTotal = computed(() => filteredItems.value.length)
const orderTotal = computed(() => {
  const visibleIds = new Set(filteredItems.value.map((row) => row.retail_product_id))
  const coversAll = items.value.every((row) => visibleIds.has(row.retail_product_id))
  if (coversAll) return metric(summary.value?.order_count)
  return filteredItems.value.reduce((n, row) => n + Number(row.order_count || 0), 0)
})

/** 选中某一品类时，卡片只写口味；全部放在一起时保留完整商品名 */
function cardTitle(row) {
  if (categoryKey.value !== ALL_CATEGORY) {
    const spec = String(row.spec_label || '').trim()
    if (spec) return spec
  }
  return String(row.display_title || '商品')
}

function categoryLabel(row) {
  return categoryNameById.value.get(categoryKeyOf(row.category_id)) || '未分类'
}

async function loadCategories() {
  const data = await apiJson(
    `/api/admin/catalog/retail-categories?store_id=${adminStoreId.value}`,
    {},
    { auth: true },
  )
  categories.value = Array.isArray(data) ? data : []
}

/**
 * @param {unknown} err
 */
function isUnauthorized(err) {
  return Boolean(err && typeof err === 'object' && 'status' in err && Number(err.status) === 401)
}

async function load() {
  if (loading.value) return
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const [summaryResult, categoryResult] = await Promise.allSettled([
      fetchRetailPickSummary({ storeId: adminStoreId.value }),
      loadCategories(),
    ])
    if (summaryResult.status === 'rejected') throw summaryResult.reason
    if (categoryResult.status === 'rejected') {
      if (isUnauthorized(categoryResult.reason)) throw categoryResult.reason
      showToast(
        categoryResult.reason instanceof Error ? categoryResult.reason.message : '分类加载失败',
        'error',
      )
    }
    summary.value = summaryResult.value
    rollKey.value += 1
    const stillThere = categoryChips.value.some((chip) => chip.key === categoryKey.value)
    if (!stillThere) categoryKey.value = ALL_CATEGORY
  } catch (e) {
    if (isUnauthorized(e)) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载备货看板失败', 'error')
    summary.value = null
  } finally {
    loading.value = false
  }
}

function onPrint() {
  window.print()
}

watch(adminStoreId, () => {
  categoryKey.value = ALL_CATEGORY
  void load()
})

onMounted(() => {
  void load()
})

onActivated(() => {
  void load()
})
</script>

<template>
  <section v-loading="loading" class="tab-content animate-up pick-board-page members-view-fill">
    <div class="table-container table-container--members-fill pick-board">
      <header class="pick-board__head">
        <div class="pick-board__titles">
          <h2 class="pick-board__title">备货看板</h2>
          <el-tag size="small" effect="plain" round class="pick-board__scope">
            {{ summary?.scope_label || '已支付 · 已接单 · 待发货' }}
          </el-tag>
          <div class="pick-board__cats">
            <el-radio-group v-model="categoryKey" size="small" class="pick-board__cat-radios">
              <el-radio-button v-for="chip in categoryChips" :key="chip.key" :value="chip.key">
                {{ chip.label }}
              </el-radio-button>
            </el-radio-group>
          </div>
        </div>
        <div class="pick-board__actions">
          <el-button size="small" round :loading="loading" @click="load">刷新</el-button>
          <el-button size="small" round type="primary" :disabled="!filteredItems.length" @click="onPrint">
            打印
          </el-button>
        </div>
      </header>

      <div v-if="summary" class="pick-board__stats" role="status">
        <span class="pick-board__stat pick-board__stat--total">
          <span class="pick-board__stat-label">待备</span>
          <strong class="pick-board__stat-num pick-board__stat-num--total">
            <StatRollNumber :value="boxTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">盒</span>
          </strong>
        </span>
        <span class="pick-board__stat">
          <span class="pick-board__stat-label">SKU</span>
          <strong class="pick-board__stat-num">
            <StatRollNumber :value="skuTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">种</span>
          </strong>
        </span>
        <span class="pick-board__stat">
          <span class="pick-board__stat-label">订单</span>
          <strong class="pick-board__stat-num">
            <StatRollNumber :value="orderTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">笔</span>
          </strong>
        </span>
        <span class="pick-board__stat">
          <span class="pick-board__stat-label">配送</span>
          <strong class="pick-board__stat-num pick-board__stat-num--ship">
            <StatRollNumber :value="deliveryTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">盒</span>
          </strong>
        </span>
        <span class="pick-board__stat">
          <span class="pick-board__stat-label">自提</span>
          <strong class="pick-board__stat-num pick-board__stat-num--pickup">
            <StatRollNumber :value="pickupTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">盒</span>
          </strong>
        </span>
      </div>

      <div class="pick-board__body">
        <el-empty
          v-if="!loading && !filteredItems.length"
          :description="categoryKey === ALL_CATEGORY ? '当前没有待发货的货' : '这个品类没有待备货'"
        />
        <div v-else-if="filteredItems.length" class="pick-board__grid" role="list">
          <article
            v-for="row in filteredItems"
            :key="row.retail_product_id"
            class="pick-board__card"
            role="listitem"
          >
            <el-tooltip :content="String(row.display_title || cardTitle(row))" placement="top" :show-after="300">
              <h3 class="pick-board__name">{{ cardTitle(row) }}</h3>
            </el-tooltip>
            <p class="pick-board__meta">
              <span v-if="categoryKey === ALL_CATEGORY">{{ categoryLabel(row) }}</span>
              <span v-if="categoryKey === ALL_CATEGORY && row.sku_code"> · </span>
              <span v-if="row.sku_code">编码 {{ row.sku_code }}</span>
            </p>
            <strong class="pick-board__qty" :title="`${row.total_boxes} 盒`">
              <StatRollNumber :value="metric(row.total_boxes)" :replay-key="rollKey" />
              <span class="pick-board__unit">盒</span>
            </strong>
            <div class="pick-board__tags">
              <el-tag
                v-if="row.delivery_boxes > 0"
                size="small"
                effect="plain"
                round
                class="pick-board__tag pick-board__tag--ship"
              >
                配送 {{ row.delivery_boxes }}
              </el-tag>
              <el-tag
                v-if="row.pickup_boxes > 0"
                size="small"
                effect="plain"
                round
                type="success"
              >
                自提 {{ row.pickup_boxes }}
              </el-tag>
              <el-tag size="small" effect="plain" round type="info">{{ row.order_count }} 单</el-tag>
            </div>
          </article>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.pick-board-page {
  padding: 0;
  min-width: 0;
}
.pick-board {
  display: flex;
  flex-direction: column;
  min-width: 0;
  padding: 8px 18px 12px;
  gap: 10px;
}
.pick-board__head,
.pick-board__stats,
.pick-board__cats {
  flex-shrink: 0;
}
.pick-board__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
}
.pick-board__titles {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
}
.pick-board__title {
  margin: 0;
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 800;
  line-height: 32px;
  height: 32px;
  white-space: nowrap;
}
.pick-board__scope.el-tag {
  flex-shrink: 0;
  height: 32px;
  max-width: 100%;
  overflow: hidden;
}
.pick-board__scope.el-tag .el-tag__content {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 30px;
}
.pick-board__cats {
  flex: 1 1 auto;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}
.pick-board__cat-radios.el-radio-group {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
}
.pick-board__cat-radios :deep(.el-radio-button__inner) {
  height: 32px;
  padding-top: 0;
  padding-bottom: 0;
  line-height: 30px;
}
.pick-board__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.pick-board__actions .el-button {
  height: 32px;
  margin: 0;
  border-radius: 999px;
}
.pick-board__stats {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}
.pick-board__stat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 0 0 auto;
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid #e2e8f0;
  white-space: nowrap;
}
.pick-board__stat--total {
  border-color: color-mix(in srgb, var(--el-color-primary) 45%, #ffffff);
  background: color-mix(in srgb, var(--el-color-primary-light-9, #fff7f5) 82%, #ffffff);
}
.pick-board__stat-label,
.pick-board__stat-num,
.pick-board__stat-unit {
  display: inline-flex;
  align-items: center;
  height: 22px;
  line-height: 22px;
}
.pick-board__stat-label {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}
.pick-board__stat-num {
  gap: 2px;
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
}
.pick-board__stat-num--total {
  color: var(--el-color-primary-dark-2, #c75f48);
}
.pick-board__stat-num--ship {
  color: #1d4ed8;
}
.pick-board__stat-num--pickup {
  color: #047857;
}
.pick-board__stat-unit {
  font-size: 12px;
  font-weight: 700;
}
.pick-board__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
}
.pick-board__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
  gap: 12px;
  align-items: stretch;
  align-content: start;
  padding: 2px 2px 8px;
}
.pick-board__card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  text-align: left;
  min-width: 0;
  height: 100%;
  padding: 12px 14px;
  border-radius: var(--okfood-surface-radius, 14px);
  background: #fff;
  border: 1px solid #e2e8f0;
}
.pick-board__name {
  margin: 0;
  width: 100%;
  height: 2.6em;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
  color: #0f172a;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.pick-board__meta {
  margin: 4px 0 0;
  height: 1.2em;
  font-size: 12px;
  line-height: 1.2;
  color: #94a3b8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pick-board__qty {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-top: 10px;
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: #0f172a;
  white-space: nowrap;
}
.pick-board__unit {
  display: inline-flex;
  align-items: center;
  height: 1em;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
  color: #64748b;
}
.pick-board__tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px;
  margin-top: auto;
  padding-top: 10px;
}
.pick-board__tag--ship.el-tag {
  color: #1d4ed8;
  background-color: rgba(59, 130, 246, 0.12);
  border-color: transparent;
}
@media (max-width: 560px) {
  .pick-board__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

<style>
@media print {
  .sidebar,
  .admin-top-tab-bar,
  .admin-layout__mobile-bar,
  .pick-board__actions,
  .pick-board__cats {
    display: none !important;
  }
  .pick-board__body {
    overflow: visible;
  }
  .pick-board__grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
  .pick-board__card {
    break-inside: avoid;
  }
}
</style>
