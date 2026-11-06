<script setup>
defineOptions({ name: 'PackagingStockView' })
import { computed, onMounted, reactive, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { listPackagingAlerts, listPackagingStocks, purchasePackaging } from '../../api/packaging/stock.js'

const loading = ref(false)
const rows = ref([])
const alerts = ref([])
const dialogOpen = ref(false)
const saving = ref(false)
const form = reactive({ sku_id: null, qty: 1, remark: '' })

const alertText = computed(() => {
  if (!alerts.value.length) return ''
  return alerts.value.map((row) => `${row.name} 结存 ${row.qty}`).join('、')
})

async function load() {
  loading.value = true
  try {
    const [stockRows, alertRows] = await Promise.all([listPackagingStocks(), listPackagingAlerts()])
    rows.value = stockRows || []
    alerts.value = alertRows || []
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openIn(row) {
  form.sku_id = row.sku_id
  form.qty = 1
  form.remark = ''
  dialogOpen.value = true
}

async function saveIn() {
  saving.value = true
  try {
    await purchasePackaging({ sku_id: form.sku_id, qty: form.qty, remark: form.remark })
    dialogOpen.value = false
    showToast('已入库', 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '入库失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-alert
      v-if="alerts.length"
      :title="`低于最低库存：${alertText}`"
      type="warning"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <el-alert
      v-else
      title="未盘点的结存显示为 0，晚上不会扣。盘点或入库之后才会按后厨出餐扣减。"
      type="info"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <el-table :data="rows" border>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="usage_note" label="用途" min-width="100" />
      <el-table-column prop="supplier_name" label="供应商" min-width="120" />
      <el-table-column label="结存" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.low" type="danger">{{ row.qty }} {{ row.unit }}</el-tag>
          <span v-else-if="!row.initialized">0 {{ row.unit }} <el-tag size="small" type="info">未盘点</el-tag></span>
          <span v-else>{{ row.qty }} {{ row.unit }}</span>
        </template>
      </el-table-column>
      <el-table-column label="最低库存" width="110">
        <template #default="{ row }">{{ row.safety_stock == null ? '未设置' : row.safety_stock }}</template>
      </el-table-column>
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_meal_bag" type="warning">每餐打包袋</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="!row.is_active" @click="openIn(row)">入库</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="还没有耗材" /></template>
    </el-table>
    <el-dialog v-model="dialogOpen" title="采购入库" width="420px">
      <el-form label-width="80px">
        <el-form-item label="数量">
          <el-input-number v-model="form.qty" :min="1" :step="1" :precision="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveIn">确认入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
</style>
