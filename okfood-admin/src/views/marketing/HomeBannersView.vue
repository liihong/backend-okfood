<script setup>
defineOptions({ name: 'HomeBannersView' })
import { ref, onMounted, computed } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, apiForm, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const storeId = ref(1)
const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(null)
const dishes = ref([])
const membershipTemplates = ref([])
const photoUploading = ref(false)
const photoUploadKey = ref(0)

const LINK_LABEL = {
  none: '不跳转',
  dish: '菜品详情',
  tab: '小程序 Tab 页',
  webview: '外链 H5',
  member_card: '卡包详情',
}

const TAB_OPTIONS = [
  { value: 'pages/home/index', label: '首页' },
  { value: 'pages/order/index', label: '菜单' },
  { value: 'pages/orders/index', label: '订单' },
  { value: 'pages/mine/index', label: '我的' },
]

const emptyForm = () => ({
  title: '',
  image_url: '',
  link_type: 'none',
  link_target: '',
  sort_order: 0,
  is_active: true,
})

const form = ref(emptyForm())

const dishOptions = computed(() =>
  (dishes.value || []).map((d) => ({
    value: String(d.id),
    label: d.is_enabled === false ? `${d.name}（已停用）` : d.name,
    disabled: d.is_enabled === false,
  })),
)

const membershipTemplateOptions = computed(() =>
  (membershipTemplates.value || []).map((t) => ({
    value: String(t.id),
    label:
      t.is_active === false
        ? `${t.name || t.kind_label || `模版#${t.id}`}（已下架）`
        : t.name || t.kind_label || `模版#${t.id}`,
    disabled: t.is_active === false,
  })),
)

async function loadDishes() {
  try {
    const data = await apiJson('/api/admin/dishes?lite=1', {}, { auth: true })
    dishes.value = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : []
  } catch {
    dishes.value = []
  }
}

async function loadMembershipTemplates() {
  try {
    const data = await apiJson(
      `/api/admin/catalog/membership-templates?store_id=${storeId.value}`,
      {},
      { auth: true },
    )
    membershipTemplates.value = Array.isArray(data) ? data : []
  } catch {
    membershipTemplates.value = []
  }
}

async function loadList() {
  loading.value = true
  try {
    const data = await apiJson(
      `/api/admin/marketing/home-banners?store_id=${storeId.value}`,
      {},
      { auth: true },
    )
    list.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  form.value = emptyForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  form.value = {
    title: row.title || '',
    image_url: row.image_url || '',
    link_type: row.link_type || 'none',
    link_target: row.link_target || '',
    sort_order: Number(row.sort_order) || 0,
    is_active: row.is_active !== false,
  }
  dialogVisible.value = true
}

async function onPhotoUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  photoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      form.value.image_url = url
      showToast('图片已上传', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '上传失败', 'error')
  } finally {
    photoUploading.value = false
    photoUploadKey.value += 1
  }
}

async function saveBanner() {
  if (!form.value.image_url?.trim()) {
    showToast('请上传 Banner 图片', 'error')
    return
  }
  saving.value = true
  try {
    const body = {
      title: form.value.title?.trim() || null,
      image_url: form.value.image_url.trim(),
      link_type: form.value.link_type || 'none',
      link_target: form.value.link_target?.trim() || null,
      sort_order: Number(form.value.sort_order) || 0,
      is_active: Boolean(form.value.is_active),
    }
    if (editing.value?.id) {
      await apiJson(
        `/api/admin/marketing/home-banners/${editing.value.id}?store_id=${storeId.value}`,
        { method: 'PATCH', body: JSON.stringify(body) },
        { auth: true },
      )
      showToast('已更新', 'success')
    } else {
      await apiJson(
        `/api/admin/marketing/home-banners?store_id=${storeId.value}`,
        { method: 'POST', body: JSON.stringify(body) },
        { auth: true },
      )
      showToast('已创建', 'success')
    }
    dialogVisible.value = false
    await loadList()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function toggleActive(row) {
  try {
    await apiJson(
      `/api/admin/marketing/home-banners/${row.id}/active?store_id=${storeId.value}`,
      {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !row.is_active }),
      },
      { auth: true },
    )
    showToast(row.is_active ? '已下架' : '已上架', 'success')
    await loadList()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function removeBanner(row) {
  if (!window.confirm('确定删除该 Banner？')) return
  try {
    await apiJson(
      `/api/admin/marketing/home-banners/${row.id}?store_id=${storeId.value}`,
      { method: 'DELETE' },
      { auth: true },
    )
    showToast('已删除', 'success')
    await loadList()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(() => {
  if (!adminAccessToken.value) return
  void loadDishes()
  void loadMembershipTemplates()
  void loadList()
})
</script>

<template>
  <section class="tab-content animate-up">
    <div class="table-container">
      <div class="table-header">
        <h2 class="table-title">首页 Banner</h2>
        <button type="button" class="btn-primary" @click="openCreate">
          <Plus :size="18" /> 新建 Banner
        </button>
      </div>
      <p v-if="loading" class="hint">加载中…</p>
      <el-table v-else :data="list" stripe class="admin-table">
        <el-table-column label="图片" width="120">
          <template #default="{ row }">
            <img v-if="row.image_url" :src="row.image_url" alt="" class="banner-thumb" />
            <span v-else class="hint">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="备注标题" min-width="120" />
        <el-table-column label="跳转" width="120">
          <template #default="{ row }">{{ LINK_LABEL[row.link_type] || row.link_type }}</template>
        </el-table-column>
        <el-table-column prop="link_target" label="跳转目标" min-width="160" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="70" />
        <el-table-column label="状态" width="80">
          <template #default="{ row }">
            <span :class="row.is_active ? 'pill pill--ok' : 'pill pill--muted'">
              {{ row.is_active ? '上架' : '下架' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <button type="button" class="btn-link" @click="openEdit(row)">编辑</button>
            <button type="button" class="btn-link" @click="toggleActive(row)">
              {{ row.is_active ? '下架' : '上架' }}
            </button>
            <button type="button" class="btn-link btn-link--danger" @click="removeBanner(row)">
              删除
            </button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑 Banner' : '新建 Banner'"
      width="520px"
      destroy-on-close
    >
      <el-form label-width="96px" class="banner-form">
        <el-form-item label="备注标题">
          <el-input v-model="form.title" placeholder="仅管理端可见" maxlength="128" />
        </el-form-item>
        <el-form-item label="Banner 图" required>
          <el-upload
            :key="photoUploadKey"
            :auto-upload="false"
            :show-file-list="false"
            accept="image/*"
            @change="onPhotoUploadChange"
          >
            <div class="upload-box">
              <img v-if="form.image_url" :src="form.image_url" alt="" class="upload-preview" />
              <span v-else>{{ photoUploading ? '上传中…' : '点击上传图片' }}</span>
            </div>
          </el-upload>
        </el-form-item>
        <el-form-item label="跳转类型">
          <el-select v-model="form.link_type" style="width: 100%">
            <el-option value="none" label="不跳转" />
            <el-option value="dish" label="菜品详情" />
            <el-option value="tab" label="小程序 Tab 页" />
            <el-option value="webview" label="外链 H5" />
            <el-option value="member_card" label="卡包详情" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.link_type === 'dish'" label="选择菜品">
          <el-select v-model="form.link_target" filterable placeholder="选择菜品" style="width: 100%">
            <el-option
              v-for="opt in dishOptions"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
              :disabled="opt.disabled"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="form.link_type === 'member_card'" label="选择卡包">
          <el-select
            v-model="form.link_target"
            filterable
            placeholder="选择卡包模版"
            style="width: 100%"
          >
            <el-option
              v-for="opt in membershipTemplateOptions"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
              :disabled="opt.disabled"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="form.link_type === 'tab'" label="Tab 页面">
          <el-select v-model="form.link_target" style="width: 100%">
            <el-option
              v-for="opt in TAB_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :label="opt.label"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="form.link_type === 'webview'" label="外链 URL">
          <el-input v-model="form.link_target" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="上架">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button type="button" class="btn-secondary" @click="dialogVisible = false">取消</button>
        <button type="button" class="btn-primary" :disabled="saving" @click="saveBanner">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.hint {
  padding: 24px;
  color: var(--admin-muted, #64748b);
}
.pill {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}
.pill--ok {
  background: #dcfce7;
  color: #166534;
}
.pill--muted {
  background: #f1f5f9;
  color: #64748b;
}
.btn-link {
  background: none;
  border: none;
  color: var(--admin-primary, #0d9488);
  cursor: pointer;
  margin-right: 8px;
  font-size: 13px;
}
.btn-link--danger {
  color: #dc2626;
}
.banner-thumb {
  width: 96px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}
.upload-box {
  width: 320px;
  height: 120px;
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  cursor: pointer;
  overflow: hidden;
}
.upload-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>
