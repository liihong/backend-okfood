<script setup>
defineOptions({ name: 'PackagingStocktakeView' })
import { onMounted, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { showToast } from '../../composables/useToast.js'
import { listPackagingStocks, stocktakePackaging } from '../../api/packaging/stock.js'

const loading = ref(false)
const saving = ref(false)
const rows = ref([])

async function load() {
  loading.value = true
  try {
    const data = await listPackagingStocks()
    rows.value = (data || []).map((row) => ({
      ...row,
      actual_text: row.initialized ? String(row.qty) : '',
    }))
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function save() {
  const lines = []
  for (const row of rows.value) {
    const text = String(row.actual_text ?? '').trim()
    if (!text) continue
    const qty = Number(text)
    if (!Number.isInteger(qty) || qty < 0) {
      showToast(`${row.name} 的实盘须为非负整数`, 'error')
      return
    }
    lines.push({ sku_id: row.sku_id, actual_qty: qty })
  }
  if (!lines.length) {
    showToast('请至少填写一项实盘', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      '实盘会改写结存。22 点之后再改的日总份不会回写当天扣库，差额留在这次校对里。',
      '保存校对',
      { type: 'warning', confirmButtonText: '保存', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await stocktakePackaging({ lines })
    showToast('校对已保存', 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-alert
      title="每周把仓库里的实数填在右边。没填的行不会改。第一次填写会当作期初，之后晚上才会扣这个品。"
      type="info"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <div class="pack-toolbar">
      <el-button type="primary" :loading="saving" @click="save">保存校对</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="supplier_name" label="供应商" min-width="120" />
      <el-table-column label="系统结存" width="120">
        <template #default="{ row }">{{ row.initialized ? row.qty : '未期初' }}</template>
      </el-table-column>
      <el-table-column label="实盘" width="180">
        <template #default="{ row }">
          <el-input v-model="row.actual_text" placeholder="不填则不改" style="width: 140px" />
        </template>
      </el-table-column>
      <template #empty><el-empty description="还没有耗材" /></template>
    </el-table>
  </div>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
.pack-toolbar { margin-bottom: 12px; }
</style>
