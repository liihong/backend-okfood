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
import { isPrepBoardCategoryName, prepBoardQtyUnit } from '../../../constants/retailPickBoard.js'

defineOptions({ name: 'PickBoardView' })

/** 全部分类 */
const ALL_CATEGORY = 'all'

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

/** 没有分类的口味 */
const UNCATEGORIZED = 'none'

/**
 * @param {unknown} categoryId
 */
function categoryKeyOf(categoryId) {
  if (categoryId == null || categoryId === '') return UNCATEGORIZED
  return String(categoryId)
}

/** 分类 id → 名称 */
const categoryNameById = computed(() => {
  /** @type {Map<string, string>} */
  const map = new Map()
  for (const row of categories.value) {
    map.set(String(row.id), String(row.name || '').trim())
  }
  return map
})

const excludedCategoryIds = computed(() => {
  const ids = new Set()
  for (const row of categories.value) {
    if (!isPrepBoardCategoryName(row.name)) ids.add(String(row.id))
  }
  return ids
})

/** 果蔬汁、月饼等排除；代餐粉、馄饨等默认纳入 */
const prepItems = computed(() =>
  items.value.filter((row) => {
    const key = categoryKeyOf(row.category_id)
    if (key === UNCATEGORIZED) return true
    return !excludedCategoryIds.value.has(key)
  }),
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
    if (!isPrepBoardCategoryName(row.name)) continue
    chips.push({ key: String(row.id), label: row.name })
  }
  return chips
})

const filteredItems = computed(() => {
  if (categoryKey.value === ALL_CATEGORY) return prepItems.value
  return prepItems.value.filter((row) => categoryKeyOf(row.category_id) === categoryKey.value)
})

const skuTotal = computed(() => filteredItems.value.length)

/**
 * @param {Record<string, unknown>} row
 */
function qtyUnitForRow(row) {
  const name = categoryNameById.value.get(categoryKeyOf(row.category_id))
  return prepBoardQtyUnit(name)
}

/** 按计量单位汇总待备数量（馄饨用盒、代餐粉用套） */
const prepTotalsByUnit = computed(() => {
  /** @type {Map<string, number>} */
  const map = new Map()
  for (const row of filteredItems.value) {
    const unit = qtyUnitForRow(row)
    map.set(unit, (map.get(unit) || 0) + Number(row.total_boxes || 0))
  }
  const order = ['盒', '套', '件']
  return [...map.entries()].sort((a, b) => {
    const ia = order.indexOf(a[0])
    const ib = order.indexOf(b[0])
    const ra = ia === -1 ? 99 : ia
    const rb = ib === -1 ? 99 : ib
    if (ra !== rb) return ra - rb
    return a[0].localeCompare(b[0], 'zh-CN')
  })
})

/** 当前筛选项下若只有一个 SPU，在 Tab 旁展示一次商品名，卡片不再重复 */
const sharedSpuTitle = computed(() => {
  const titles = new Set(
    filteredItems.value.map((row) => String(row.spu_title || '').trim()).filter(Boolean),
  )
  if (titles.size === 1) return [...titles][0]
  return ''
})

/** 卡片只展示规格/SKU 名（后厨认口味，不认「商品名 · 规格」长标题） */
function cardTitle(row) {
  const spec = String(row.spec_label || '').trim()
  if (spec) return spec
  const display = String(row.display_title || '').trim()
  const dot = display.indexOf(' · ')
  if (dot >= 0) return display.slice(dot + 3).trim() || display
  return display || '商品'
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
          <!-- <el-tag size="small" effect="plain" round class="pick-board__scope">
            {{ summary?.scope_label || '已支付 · 已接单 · 待发货' }}
          </el-tag> -->
          <div class="pick-board__cats">
            <span v-if="sharedSpuTitle" class="pick-board__spu" :title="sharedSpuTitle">
              {{ sharedSpuTitle }}
            </span>
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
        <span
          v-for="([unit, total], idx) in prepTotalsByUnit"
          :key="unit"
          class="pick-board__stat"
          :class="{ 'pick-board__stat--total': idx === 0 }"
        >
          <span class="pick-board__stat-label">待备</span>
          <strong
            class="pick-board__stat-num"
            :class="{ 'pick-board__stat-num--total': idx === 0 }"
          >
            <StatRollNumber :value="total" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">{{ unit }}</span>
          </strong>
        </span>
        <span class="pick-board__stat">
          <span class="pick-board__stat-label">SKU</span>
          <strong class="pick-board__stat-num">
            <StatRollNumber :value="skuTotal" :replay-key="rollKey" />
            <span class="pick-board__stat-unit">种</span>
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
            <div class="pick-board__card-head">
              <el-tooltip
                :content="String(row.display_title || cardTitle(row))"
                placement="top"
                :show-after="400"
              >
                <h3 class="pick-board__name">{{ cardTitle(row) }}</h3>
              </el-tooltip>
              <span v-if="row.sku_code" class="pick-board__code" :title="`编码 ${row.sku_code}`">
                {{ row.sku_code }}
              </span>
            </div>
            <strong class="pick-board__qty" :title="`${row.total_boxes} ${qtyUnitForRow(row)}`">
              <StatRollNumber :value="metric(row.total_boxes)" :replay-key="rollKey" />
              <span class="pick-board__unit">{{ qtyUnitForRow(row) }}</span>
            </strong>
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
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1 1 auto;
  min-width: 0;
  /* 单选边线画在盒外，滚动裁切会吃掉上下边，留出空隙 */
  padding: 2px;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: thin;
}
.pick-board__spu {
  flex-shrink: 0;
  max-width: min(220px, 28vw);
  padding: 0 10px;
  height: 32px;
  line-height: 32px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
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
  justify-content: flex-start;
  text-align: left;
  min-width: 0;
  height: 100%;
  min-height: 108px;
  padding: 12px 14px 14px;
  border-radius: var(--okfood-surface-radius, 14px);
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.pick-board__card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
  width: 100%;
  min-width: 0;
}
.pick-board__name {
  margin: 0;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 2.6em;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
  color: #0f172a;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
.pick-board__code {
  flex-shrink: 0;
  margin-top: 1px;
  padding: 2px 6px;
  max-width: 4.5em;
  font-size: 10px;
  font-weight: 700;
  line-height: 1.2;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: #64748b;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-radius: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}
.pick-board__qty {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 3px;
  margin-top: auto;
  padding-top: 12px;
  font-size: 28px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--el-color-primary-dark-2, #b45309);
  white-space: nowrap;
}
.pick-board__unit {
  display: inline-flex;
  align-items: center;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  color: #64748b;
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
  .pick-board__cat-radios {
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
