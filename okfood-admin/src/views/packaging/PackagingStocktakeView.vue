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
      '<p class="okfood-message-box__detail">实盘会改写结存。22 点之后再改的日总份不会回写当天扣库，差额留在这次校对里。</p>',
      '保存校对',
      {
        customClass: 'okfood-message-box',
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        cancelButtonClass: 'okfood-message-box__cancel',
        distinguishCancelAndClose: true,
        dangerouslyUseHTMLString: true,
      },
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
  <section class="mkt-page tab-content animate-up">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">库存管理</p>
        <h1 class="mkt-title">库存校对</h1>
        <p class="mkt-intro">
          每周把仓库里的实数填在右边。没填的行不会改。第一次填写会当作期初，之后晚上才会扣这个品。
        </p>
      </div>
      <el-button type="primary" round :loading="saving" @click="save">保存校对</el-button>
    </header>

    <article class="mkt-card">
      <div class="mkt-table-wrap">
        <el-table v-loading="loading" :data="rows" class="admin-table" empty-text="还没有耗材">
          <el-table-column prop="name" label="名称" min-width="140" />
          <el-table-column prop="supplier_name" label="供应商" min-width="120" />
          <el-table-column label="系统结存" width="120">
            <template #default="{ row }">
              <el-tag v-if="!row.initialized" type="info" round effect="light">未期初</el-tag>
              <span v-else>{{ row.qty }}</span>
            </template>
          </el-table-column>
          <el-table-column label="实盘" width="180">
            <template #default="{ row }">
              <el-input v-model="row.actual_text" placeholder="不填则不改" style="width: 140px" />
            </template>
          </el-table-column>
        </el-table>
      </div>
    </article>
  </section>
</template>
