<script setup>
defineOptions({ name: 'PackagingLedgerView' })
import { onMounted, reactive, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { listPackagingSkus } from '../../api/packaging/sku.js'
import { listPackagingTxns } from '../../api/packaging/stock.js'

const loading = ref(false)
const rows = ref([])
const skus = ref([])
const filters = reactive({
  sku_id: null,
  biz_date_from: '',
  biz_date_to: '',
})

async function load() {
  loading.value = true
  try {
    rows.value = await listPackagingTxns({
      sku_id: filters.sku_id,
      biz_date_from: filters.biz_date_from,
      biz_date_to: filters.biz_date_to,
    })
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    skus.value = await listPackagingSkus()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载品类失败', 'error')
  }
  await load()
})
</script>

<template>
  <section class="mkt-page tab-content animate-up">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">库存管理</p>
        <h1 class="mkt-title">库存流水</h1>
        <p class="mkt-intro">按耗材和业务日查看入库、自动领用、期初和盘点。</p>
      </div>
    </header>

    <article class="mkt-card">
      <el-form :inline="true" class="pack-filters">
        <el-form-item label="耗材">
          <el-select v-model="filters.sku_id" clearable filterable placeholder="全部" style="width: 180px">
            <el-option v-for="sku in skus" :key="sku.id" :label="sku.name" :value="sku.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="从">
          <el-date-picker v-model="filters.biz_date_from" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="到">
          <el-date-picker v-model="filters.biz_date_to" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" round @click="load">查询</el-button>
        </el-form-item>
      </el-form>
      <div class="mkt-table-wrap">
        <el-table v-loading="loading" :data="rows" class="admin-table" empty-text="还没有流水">
          <el-table-column prop="biz_date" label="业务日" width="120" />
          <el-table-column prop="sku_name" label="耗材" min-width="140" />
          <el-table-column prop="txn_label" label="类型" width="110" />
          <el-table-column label="餐段" width="90">
            <template #default="{ row }">{{ row.meal_period === 'lunch' ? '午餐' : row.meal_period === 'dinner' ? '晚餐' : '—' }}</template>
          </el-table-column>
          <el-table-column prop="qty_delta" label="变动" width="90" />
          <el-table-column prop="qty_after" label="结存" width="90" />
          <el-table-column prop="operator" label="操作人" width="120" />
          <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
        </el-table>
      </div>
    </article>
  </section>
</template>

<style scoped>
.pack-filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}
.pack-filters :deep(.el-form-item) {
  margin: 0;
}
</style>
