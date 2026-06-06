<script setup>
defineOptions({ name: 'DishCategoriesView' })
import { ref, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import { buildCategoryTree } from '../utils/categoryTree.js'

const storeId = ref(1)
const categories = ref([])
const loading = ref(false)

const qs = computed(() => new URLSearchParams({ store_id: String(storeId.value || 1) }).toString())

const categoryTree = computed(() => buildCategoryTree(categories.value))

const parentOptions = computed(() =>
  categories.value.filter((c) => c.parent_id == null && c.is_active !== false),
)

async function fetchCategories() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const data = await apiJson(`/api/admin/categories?${qs.value}`, {}, { auth: true })
    categories.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '分类加载失败', 'error')
  } finally {
    loading.value = false
  }
}

const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const form = ref({ code: '', name: '', sort_order: 0, is_active: true, parent_id: null })

const formRules = {
  code: [
    { required: true, message: '请输入分类编码', trigger: 'blur' },
    {
      pattern: /^[a-z][a-z0-9_]{0,31}$/,
      message: '编码须为小写英文开头，可含数字与下划线，最长 32 位',
      trigger: 'blur',
    },
  ],
  name: [
    { required: true, message: '请输入分类名称', trigger: 'blur' },
    { max: 64, message: '名称不超过 64 字', trigger: 'blur' },
  ],
}

const dialogTitle = computed(() => {
  if (editingId.value) return '编辑菜品分类'
  return form.value.parent_id ? '新建二级分类' : '新建一级分类'
})

function levelLabel(row) {
  return row.parent_id == null ? '一级' : '二级'
}

function openCreate(parentId = null) {
  editingId.value = null
  form.value = { code: '', name: '', sort_order: 0, is_active: true, parent_id: parentId }
  dialogVisible.value = true
}

function openCreateChild(row) {
  if (row.parent_id != null) {
    showToast('仅支持二级分类，不能再建下级', 'error')
    return
  }
  openCreate(row.id)
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    code: row.code || '',
    name: row.name || '',
    sort_order: row.sort_order ?? 0,
    is_active: row.is_active !== false,
    parent_id: row.parent_id ?? null,
  }
  dialogVisible.value = true
}

async function saveCategory() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  const name = String(form.value.name || '').trim()
  saving.value = true
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    if (editingId.value) {
      await apiJson(`/api/admin/category/${editingId.value}?store_id=${sid}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name,
          sort_order: Number(form.value.sort_order) || 0,
          is_active: Boolean(form.value.is_active),
          parent_id: form.value.parent_id ?? null,
        }),
      }, { auth: true })
    } else {
      const code = String(form.value.code || '').trim()
      await apiJson(`/api/admin/category?store_id=${sid}`, {
        method: 'POST',
        body: JSON.stringify({
          code,
          name,
          sort_order: Number(form.value.sort_order) || 0,
          parent_id: form.value.parent_id ?? null,
        }),
      }, { auth: true })
    }
    showToast('已保存', 'success')
    dialogVisible.value = false
    await fetchCategories()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function removeCategory(row) {
  const hint = row.parent_id == null ? '若该分类下仍有子分类或菜品，将无法删除。' : '若该分类下仍有菜品，将无法删除。'
  try {
    await ElMessageBox.confirm(`确定删除分类「${row.name}」？${hint}`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/category/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除', 'success')
    await fetchCategories()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(fetchCategories)
</script>

<template>
  <div class="dish-categories-page tab-content animate-up page-content-shell">
    <el-card shadow="never" class="toolbar-card">
      <el-form inline label-width="72px" @submit.prevent>
        <el-form-item label="门店 ID">
          <el-input-number
            v-model="storeId"
            :min="1"
            controls-position="right"
            @change="fetchCategories"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <el-alert
      class="page-alert"
      type="info"
      :closable="true"
      show-icon
      title="支持二级分类：一级如「肉类」「菜品分类」，二级为具体子类。菜品请归到二级分类；选一级筛选时会包含其下全部菜品。"
    />

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span class="card-header__title">菜品分类</span>
          <el-button type="primary" @click="openCreate()">新建一级分类</el-button>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="categoryTree"
        style="width: 100%"
        row-key="id"
        :tree-props="{ children: 'children' }"
        default-expand-all
        table-layout="auto"
        empty-text="暂无分类，点击右上角新建"
      >
        <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="层级" width="72" align="center">
          <template #default="{ row }">
            <el-tag :type="row.parent_id == null ? 'primary' : 'info'" size="small" effect="plain">
              {{ levelLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="编码" min-width="130">
          <template #default="{ row }">
            <el-tag type="info" size="small" effect="plain">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button v-if="row.parent_id == null" link type="primary" @click="openCreateChild(row)">
              添加子类
            </el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeCategory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="460px"
      destroy-on-close
      :close-on-click-modal="false"
      @closed="formRef?.resetFields?.()"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="editingId ? { name: formRules.name } : formRules"
        label-position="top"
      >
        <el-form-item label="上级分类">
          <el-select
            v-model="form.parent_id"
            clearable
            placeholder="无（一级分类）"
            style="width: 100%"
            :disabled="Boolean(editingId && form.parent_id == null && categories.some((c) => c.parent_id === editingId))"
          >
            <el-option
              v-for="p in parentOptions"
              :key="p.id"
              :label="p.name"
              :value="p.id"
              :disabled="editingId != null && p.id === editingId"
            />
          </el-select>
          <p class="form-hint">仅支持二级；有子类的一级分类不可再挂到其它上级下</p>
        </el-form-item>

        <el-form-item v-if="!editingId" label="编码" prop="code">
          <el-input
            v-model="form.code"
            maxlength="32"
            placeholder="如 meat_chicken、dish_salad"
            clearable
          />
        </el-form-item>
        <el-form-item v-else label="编码">
          <el-tag type="info" effect="plain">{{ form.code }}</el-tag>
          <p class="form-hint">编码创建后不可修改</p>
        </el-form-item>

        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" maxlength="64" placeholder="如：鸡肉" show-word-limit clearable />
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number
            v-model="form.sort_order"
            :min="0"
            :max="9999"
            controls-position="right"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item v-if="editingId" label="启用">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.dish-categories-page {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.toolbar-card :deep(.el-card__body) {
  padding-bottom: 2px;
}
.page-alert {
  margin: 0;
}
.table-card :deep(.el-card__header) {
  padding: 14px 20px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.card-header__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}
.form-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}
</style>
