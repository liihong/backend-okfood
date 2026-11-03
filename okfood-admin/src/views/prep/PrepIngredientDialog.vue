<script setup>
defineOptions({ name: 'PrepIngredientDialog' })
import { ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { showToast } from '../../composables/useToast.js'
import { handleAdminLogout } from '../../admin/core.js'
import {
  createPrepIngredient,
  deletePrepIngredient,
  listPrepIngredients,
  patchPrepIngredient,
  percentToYieldRate,
  yieldRateToPercent,
} from '../../api/prepMenu.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'changed'])

const loading = ref(false)
const saving = ref(false)
/** @type {import('vue').Ref<Array<{ id: number, name: string, unit: 'g' | 'piece', yield_rate: string }>>} */
const rows = ref([])
const editingId = ref(/** @type {number | null} */ (null))
const form = ref({ name: '', unit: /** @type {'g' | 'piece'} */ ('g'), percent: 100 })

function close() {
  emit('update:modelValue', false)
}

/** @param {unknown} error @param {string} fallback */
function report(error, fallback) {
  const status = error && typeof error === 'object' && 'status' in error ? Number(error.status) : 0
  if (status === 401) {
    alert('登录已过期，请重新登录')
    handleAdminLogout()
    return
  }
  showToast(error instanceof Error ? error.message : fallback, 'error')
}

function resetForm() {
  editingId.value = null
  form.value = { name: '', unit: 'g', percent: 100 }
}

async function load() {
  loading.value = true
  try {
    const data = await listPrepIngredients()
    rows.value = Array.isArray(data) ? data : []
  } catch (error) {
    report(error, '食材加载失败')
  } finally {
    loading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    resetForm()
    void load()
  },
)

/** @param {{ id: number, name: string, unit: 'g' | 'piece', yield_rate: string }} row */
function editRow(row) {
  editingId.value = row.id
  form.value = {
    name: row.name,
    unit: row.unit,
    percent: row.unit === 'piece' ? 100 : yieldRateToPercent(row.yield_rate),
  }
}

async function save() {
  const name = form.value.name.trim()
  if (!name) {
    showToast('请填写食材名称', 'error')
    return
  }
  /** @type {{ name: string, unit: 'g' | 'piece', yield_rate: string }} */
  const body = { name, unit: form.value.unit, yield_rate: '1.0000' }
  if (form.value.unit === 'g') {
    const rate = percentToYieldRate(form.value.percent)
    if (!rate) {
      showToast('出成率请填大于 0 且不超过 100 的数，例如 70', 'error')
      return
    }
    body.yield_rate = rate
  }
  saving.value = true
  try {
    if (editingId.value) {
      await patchPrepIngredient(editingId.value, body)
    } else {
      await createPrepIngredient(body)
    }
    showToast('食材已保存', 'success')
    resetForm()
    await load()
    emit('changed')
  } catch (error) {
    report(error, '保存失败')
  } finally {
    saving.value = false
  }
}

/** @param {{ id: number, name: string }} row */
async function removeRow(row) {
  try {
    await ElMessageBox.confirm(`确定删除食材「${row.name}」？已被菜品使用的食材不能删除。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deletePrepIngredient(row.id)
    showToast('食材已删除', 'success')
    if (editingId.value === row.id) resetForm()
    await load()
    emit('changed')
  } catch (error) {
    report(error, '删除失败')
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    title="食材与出成率"
    width="720px"
    append-to-body
    :close-on-click-modal="false"
    @update:model-value="(open) => emit('update:modelValue', open)"
  >
    <p class="prep-ing-tip">克重食材的出成率用来把毛菜折成净菜。按个计的食材只统计个数。</p>
    <el-form label-position="top" class="prep-ing-form" @submit.prevent="save">
      <el-form-item label="名称">
        <el-input v-model="form.name" maxlength="64" placeholder="如 花菜" />
      </el-form-item>
      <el-form-item label="单位">
        <el-select v-model="form.unit" style="width: 120px">
          <el-option label="克" value="g" />
          <el-option label="个" value="piece" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="form.unit === 'g'" label="出成率 %">
        <el-input-number v-model="form.percent" :min="0.01" :max="100" :step="1" :precision="2" />
      </el-form-item>
      <el-form-item v-else label="出成率">
        <span class="prep-ing-muted">按个计，不换算</span>
      </el-form-item>
      <el-form-item label=" ">
        <el-button type="primary" :loading="saving" @click="save">{{ editingId ? '保存修改' : '添加' }}</el-button>
        <el-button v-if="editingId" @click="resetForm">取消编辑</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" empty-text="还没有食材">
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="单位" width="80">
        <template #default="{ row }">{{ row.unit === 'piece' ? '个' : '克' }}</template>
      </el-table-column>
      <el-table-column label="出成率" width="100">
        <template #default="{ row }">
          {{ row.unit === 'piece' ? '—' : `${yieldRateToPercent(row.yield_rate)}%` }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center">
        <template #default="{ row }">
          <el-button link type="primary" @click="editRow(row)">编辑</el-button>
          <el-button link type="danger" @click="removeRow(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="close">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.prep-ing-tip {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.5;
}
.prep-ing-form {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  align-items: flex-end;
  margin-bottom: 12px;
}
.prep-ing-form :deep(.el-form-item) {
  margin-bottom: 8px;
}
.prep-ing-muted {
  color: #64748b;
  line-height: 32px;
}
</style>
