<script setup>
defineOptions({ name: 'PackagingDishRecipeView' })
import { computed, onMounted, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { listPackagingSkus } from '../../api/packaging/sku.js'
import { listDishPackaging, saveDishPackaging } from '../../api/packaging/recipe.js'
import PackagingLineEditor from './components/PackagingLineEditor.vue'

const loading = ref(false)
const saving = ref(false)
const dishes = ref([])
const skus = ref([])
const dialogOpen = ref(false)
const current = ref(null)
const lines = ref([])

const skuOptions = computed(() => skus.value.filter((item) => !item.is_meal_bag))

async function load() {
  loading.value = true
  try {
    const [dishRows, skuRows] = await Promise.all([listDishPackaging(), listPackagingSkus()])
    dishes.value = dishRows || []
    skus.value = skuRows || []
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openDish(row) {
  current.value = row
  lines.value = (row.lines || []).map((line) => ({
    sku_id: line.sku_id,
    qty_per_portion: line.qty_per_portion,
  }))
  dialogOpen.value = true
}

async function save() {
  if (!current.value) return
  const payload = lines.value
    .filter((line) => line.sku_id)
    .map((line) => ({ sku_id: line.sku_id, qty_per_portion: line.qty_per_portion || 1 }))
  saving.value = true
  try {
    await saveDishPackaging(current.value.dish_id, payload)
    showToast('菜品用盒已保存。已排到本周的槽位不会自动改掉。', 'success')
    dialogOpen.value = false
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

function boxText(row) {
  if (!row.lines?.length) return '未设置'
  return row.lines.map((line) => `${line.sku_name}×${line.qty_per_portion}`).join('、')
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-alert
      title="这里是菜品默认用盒。本周某一天要换盒子，请在本周菜单点「用盒」，那一次会同时改当天槽位和默认值。"
      type="info"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <el-table :data="dishes" border>
      <el-table-column prop="dish_name" label="菜品" min-width="180" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="默认用盒" min-width="240">
        <template #default="{ row }">
          <el-tag v-if="!row.lines?.length" type="warning">未设置</el-tag>
          <span v-else>{{ boxText(row) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDish(row)">设置</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="还没有菜品" /></template>
    </el-table>
    <el-dialog v-model="dialogOpen" :title="current ? `${current.dish_name} 的用盒` : '用盒'" width="640px">
      <PackagingLineEditor v-model="lines" :sku-options="skuOptions" />
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
</style>
