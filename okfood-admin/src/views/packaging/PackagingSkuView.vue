<script setup>
defineOptions({ name: 'PackagingSkuView' })
import { onMounted, reactive, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { showToast } from '../../composables/useToast.js'
import {
  createPackagingSku,
  deletePackagingSku,
  importDefaultPackagingSkus,
  listPackagingSkus,
  patchPackagingSku,
} from '../../api/packaging/sku.js'

const loading = ref(false)
const rows = ref([])
const dialogOpen = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = reactive({
  name: '',
  usage_note: '',
  supplier_name: '',
  unit: '个',
  safety_stock: null,
  safety_enabled: false,
  is_meal_bag: false,
  is_active: true,
})

function resetForm() {
  form.name = ''
  form.usage_note = ''
  form.supplier_name = ''
  form.unit = '个'
  form.safety_stock = null
  form.safety_enabled = false
  form.is_meal_bag = false
  form.is_active = true
}

async function load() {
  loading.value = true
  try {
    rows.value = await listPackagingSkus()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.usage_note = row.usage_note || ''
  form.supplier_name = row.supplier_name || ''
  form.unit = row.unit || '个'
  form.safety_enabled = row.safety_stock != null
  form.safety_stock = row.safety_stock
  form.is_meal_bag = !!row.is_meal_bag
  form.is_active = row.is_active !== false
  dialogOpen.value = true
}

function payload() {
  return {
    name: form.name.trim(),
    usage_note: form.usage_note.trim(),
    supplier_name: form.supplier_name.trim(),
    unit: form.unit.trim() || '个',
    safety_stock: form.safety_enabled ? Number(form.safety_stock || 0) : null,
    is_meal_bag: form.is_meal_bag,
    is_active: form.is_active,
  }
}

async function save() {
  if (!form.name.trim()) {
    showToast('请填写名称', 'error')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await patchPackagingSku(editingId.value, payload())
    } else {
      await createPackagingSku(payload())
    }
    dialogOpen.value = false
    showToast('已保存', 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(`删除「${row.name}」？已有流水的耗材不能删除。`, '删除耗材', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deletePackagingSku(row.id)
    showToast('已删除', 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '删除失败', 'error')
  }
}

async function onImport() {
  try {
    await ElMessageBox.confirm('只给当前门店补上还没有的常用打包耗材，已有名称不会被覆盖。', '导入常用耗材', {
      type: 'info',
      confirmButtonText: '导入',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const data = await importDefaultPackagingSkus()
    showToast(`新导入 ${data?.created ?? 0} 个`, 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '导入失败', 'error')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-alert
      title="打包袋全店只能有一个，晚上按每餐出餐份数自动扣一只。最低库存留空则不提醒采购，结存变成负数时仍会通知。"
      type="info"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <div class="pack-toolbar">
      <el-button type="primary" @click="openCreate">新增品类</el-button>
      <el-button @click="onImport">导入常用打包耗材</el-button>
    </div>
    <el-table :data="rows" border>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="usage_note" label="用途" min-width="100" />
      <el-table-column prop="supplier_name" label="供应商" min-width="120" />
      <el-table-column prop="unit" label="单位" width="80" />
      <el-table-column label="最低库存" width="110">
        <template #default="{ row }">{{ row.safety_stock == null ? '未设置' : row.safety_stock }}</template>
      </el-table-column>
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag v-if="row.is_meal_bag" type="warning">每餐打包袋</el-tag>
          <span v-else>普通</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="还没有耗材" /></template>
    </el-table>

    <el-dialog v-model="dialogOpen" :title="editingId ? '编辑耗材' : '新增耗材'" width="480px">
      <el-form label-width="96px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" maxlength="64" />
        </el-form-item>
        <el-form-item label="用途">
          <el-input v-model="form.usage_note" maxlength="64" placeholder="如沙拉、料汁" />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="form.supplier_name" maxlength="64" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" maxlength="16" />
        </el-form-item>
        <el-form-item label="最低库存">
          <el-switch v-model="form.safety_enabled" active-text="设置" inactive-text="不提醒" />
          <el-input-number
            v-if="form.safety_enabled"
            v-model="form.safety_stock"
            :min="0"
            :step="1"
            :precision="0"
            class="pack-safety"
          />
        </el-form-item>
        <el-form-item label="每餐打包袋">
          <el-switch v-model="form.is_meal_bag" />
        </el-form-item>
        <el-form-item v-if="editingId" label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
.pack-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.pack-safety { margin-left: 12px; }
</style>
