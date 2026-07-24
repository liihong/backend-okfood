<script setup>
defineOptions({ name: 'HomeBannersView' })
import { ref, onMounted, computed } from 'vue'
import { Plus, Upload } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
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

/** 小程序首页 Banner 建议尺寸（设计稿 750 宽，展示高度约半屏） */
const BANNER_SIZE_HINT = '建议尺寸 750×750 px（1:1），JPG/PNG，单张 ≤ 500KB'

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
  try {
    await ElMessageBox.confirm('确定删除该 Banner？删除后不可恢复。', '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
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
        <el-button type="primary" @click="openCreate">
          <Plus :size="16" style="margin-right: 4px" />
          新建 Banner
        </el-button>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        :title="`小程序首页顶部轮播图。${BANNER_SIZE_HINT}；重要文案请放在画面中心，避免被裁切。`"
        class="banner-alert"
      />

      <el-table
        v-loading="loading"
        :data="list"
        stripe
        class="admin-table"
        empty-text="暂无 Banner，请点击「新建 Banner」"
      >
        <el-table-column label="图片" width="120">
          <template #default="{ row }">
            <img v-if="row.image_url" :src="row.image_url" alt="" class="banner-thumb" />
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="备注标题" min-width="120" show-overflow-tooltip />
        <el-table-column label="跳转" width="120">
          <template #default="{ row }">{{ LINK_LABEL[row.link_type] || row.link_type }}</template>
        </el-table-column>
        <el-table-column prop="link_target" label="跳转目标" min-width="160" show-overflow-tooltip />
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '上架' : '下架' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="primary" @click="toggleActive(row)">
              {{ row.is_active ? '下架' : '上架' }}
            </el-button>
            <el-button link type="danger" @click="removeBanner(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑 Banner' : '新建 Banner'"
      width="560px"
      align-center
      destroy-on-close
    >
      <el-form label-width="96px" class="banner-form" @submit.prevent="saveBanner">
        <el-form-item label="备注标题">
          <el-input v-model="form.title" placeholder="仅管理端可见" maxlength="128" clearable />
        </el-form-item>

        <el-form-item label="Banner 图" required>
          <div class="upload-wrap">
            <el-upload
              :key="photoUploadKey"
              :auto-upload="false"
              :show-file-list="false"
              accept="image/*"
              :disabled="photoUploading"
              @change="onPhotoUploadChange"
            >
              <div v-loading="photoUploading" class="upload-box">
                <img v-if="form.image_url" :src="form.image_url" alt="" class="upload-preview" />
                <div v-else class="upload-placeholder">
                  <Upload :size="28" stroke-width="1.75" />
                  <span>点击上传图片</span>
                </div>
              </div>
            </el-upload>
            <p class="upload-tip">{{ BANNER_SIZE_HINT }}</p>
            <el-button
              v-if="form.image_url"
              link
              type="danger"
              size="small"
              @click="form.image_url = ''"
            >
              移除图片
            </el-button>
          </div>
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
          <el-select
            v-model="form.link_target"
            filterable
            placeholder="选择菜品"
            style="width: 100%"
          >
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
          <el-input v-model="form.link_target" placeholder="https://..." clearable />
        </el-form-item>

        <el-form-item label="排序">
          <el-input-number
            v-model="form.sort_order"
            :min="0"
            :max="9999"
            controls-position="right"
          />
          <span class="field-hint">数字越小越靠前</span>
        </el-form-item>

        <el-form-item label="上架">
          <el-switch v-model="form.is_active" active-text="上架" inactive-text="下架" />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveBanner">保存</el-button>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.banner-alert {
  margin-bottom: 16px;
}

.muted {
  color: var(--el-text-color-placeholder, #94a3b8);
}

.banner-thumb {
  width: 64px;
  height: 64px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--el-border-color, #e2e8f0);
  display: block;
}

.upload-wrap {
  width: 100%;
}

.upload-box {
  width: 240px;
  height: 240px;
  border: 1px dashed var(--el-border-color, #cbd5e1);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--el-text-color-secondary, #64748b);
  cursor: pointer;
  overflow: hidden;
  background: var(--el-fill-color-blank, #fff);
  transition: border-color 0.2s;
}

.upload-box:hover {
  border-color: var(--el-color-primary, #0d9488);
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.upload-preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.upload-tip {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-text-color-secondary, #64748b);
}

.field-hint {
  margin-left: 12px;
  font-size: 12px;
  color: var(--el-text-color-secondary, #64748b);
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
