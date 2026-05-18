<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const form = ref({
  kind_label: '',
  name: '',
  meals_grant: 6,
  remark: '',
  sort_order: 0,
  is_active: true,
})

const qs = computed(() => {
  const p = new URLSearchParams({ store_id: String(storeId.value || 1) })
  return p.toString()
})

async function fetchList() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const data = await apiJson(`/api/admin/catalog/membership-templates?${qs.value}`, {}, { auth: true })
    list.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = {
    kind_label: '',
    name: '',
    meals_grant: 6,
    remark: '',
    sort_order: 0,
    is_active: true,
  }
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    kind_label: row.kind_label ?? '',
    name: row.name || '',
    meals_grant: row.meals_grant,
    remark: row.remark || '',
    sort_order: row.sort_order,
    is_active: row.is_active,
  }
  dialogVisible.value = true
}

async function saveForm() {
  if (saving.value) return
  const kind = String(form.value.kind_label || '').trim()
  const name = String(form.value.name || '').trim()
  if (!kind) {
    showToast('请填写种类（如：周卡、季卡、午晚餐卡）', 'error')
    return
  }
  if (!name) {
    showToast('请填写名称', 'error')
    return
  }
  saving.value = true
  try {
    const sid = encodeURIComponent(String(storeId.value || 1))
    if (editingId.value) {
      const body = {}
      body.kind_label = kind
      body.name = name
      body.meals_grant = Number(form.value.meals_grant)
      body.remark = String(form.value.remark || '').trim() || null
      body.sort_order = Number(form.value.sort_order) || 0
      body.is_active = Boolean(form.value.is_active)
      await apiJson(`/api/admin/catalog/membership-templates/${editingId.value}?store_id=${sid}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }, { auth: true })
      showToast('已保存')
    } else {
      await apiJson(`/api/admin/catalog/membership-templates?store_id=${sid}`, {
        method: 'POST',
        body: JSON.stringify({
          kind_label: kind,
          name,
          meals_grant: Number(form.value.meals_grant) || 1,
          remark: String(form.value.remark || '').trim() || null,
          sort_order: Number(form.value.sort_order) || 0,
          is_active: Boolean(form.value.is_active),
        }),
      }, { auth: true })
      showToast('已创建')
    }
    dialogVisible.value = false
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function removeRow(row) {
  const ok = window.confirm(`确定删除「${row.name}」？`)
  if (!ok) return
  try {
    const sid = encodeURIComponent(String(storeId.value || 1))
    await apiJson(`/api/admin/catalog/membership-templates/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(fetchList)
</script>

<template>
  <div class="page-wrap">
    <div class="page-toolbar">
      <div class="field">
        <span class="label">门店 ID</span>
        <el-input-number v-model="storeId" :min="1" controls-position="right" @change="fetchList" />
      </div>
      <el-button type="primary" @click="openCreate">
        <Plus :size="16" stroke-width="2" class="btn-icon" />
        新增会员卡模版
      </el-button>
    </div>

    <el-alert
      type="info"
      title="种类可自定义（周卡 / 季卡 / 午晚餐卡等）；本期仅入库，不改变小程序与原开卡入账逻辑。"
      show-icon
      class="banner"
    />

    <el-card shadow="never" class="tbl-card">
      <el-table v-loading="loading" :data="list" stripe empty-text="暂无模版">
        <el-table-column prop="kind_label" label="种类" width="120" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="meals_grant" label="入账餐次/次购买" width="140" align="center" />
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column prop="is_active" label="启用" width="80" align="center">
          <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模版' : '新建模版'" width="480px">
      <el-form label-width="112px">
        <el-form-item label="种类">
          <el-input
            v-model="form.kind_label"
            maxlength="64"
            placeholder="如：周卡、月卡、次卡、季卡、午晚餐卡"
          />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" maxlength="128" placeholder="如：标准六餐 — 可作具体套餐名" />
        </el-form-item>
        <el-form-item label="单笔入账次数">
          <el-input-number v-model="form.meals_grant" :min="1" :max="366" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveForm">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-wrap {
  padding: 0 24px 32px;
  max-width: 1200px;
}
.page-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}
.field {
  display: flex;
  align-items: center;
  gap: 8px;
}
.label {
  color: rgba(15, 23, 42, 0.55);
  font-size: 13px;
}
.btn-icon {
  margin-right: 4px;
  vertical-align: text-bottom;
}
.banner {
  margin-bottom: 16px;
}
.tbl-card :deep(.el-card__body) {
  padding: 0;
}
</style>
