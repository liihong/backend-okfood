<script setup>
defineOptions({ name: 'HomeBannersView' })
import { ref, onMounted, computed } from 'vue'
import { Plus, Upload } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
import { apiJson, apiForm, adminAccessToken, dishImageDisplayUrl, handleAdminLogout } from '../../admin/core.js'
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

const sortedList = computed(() =>
  [...list.value].sort(
    (a, b) =>
      (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0) ||
      (Number(a.id) || 0) - (Number(b.id) || 0),
  ),
)

/** 小程序实际会播的顺序：只含上架，排序与列表一致 */
const activePreview = computed(() => sortedList.value.filter((row) => row.is_active !== false))

function bannerSrc(url) {
  return dishImageDisplayUrl(url)
}

function linkTargetText(row) {
  const type = row?.link_type || 'none'
  const target = String(row?.link_target || '').trim()
  if (type === 'none' || !target) return '—'
  if (type === 'tab') return TAB_OPTIONS.find((item) => item.value === target)?.label || target
  if (type === 'dish') {
    const dish = dishes.value.find((item) => String(item.id) === target)
    return dish?.name || `菜品 #${target}`
  }
  if (type === 'member_card') {
    const card = membershipTemplates.value.find((item) => String(item.id) === target)
    return card?.name || card?.kind_label || `卡包 #${target}`
  }
  return target
}

/** 切换跳转类型时清掉旧目标，避免菜品 id 被当成外链提交 */
function onLinkTypeChange() {
  form.value.link_target = ''
}

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
  <section class="hb-page tab-content animate-up">
    <header class="hb-page-head">
      <div class="hb-page-head__bar">
        <div class="hb-page-head__copy">
          <p class="hb-kicker">小程序营销</p>
          <h1 class="hb-title">首页 Banner</h1>
        </div>
        <el-button class="hb-add" type="primary" round size="large" @click="openCreate">
          <Plus :size="16" />
          新建 Banner
        </el-button>
      </div>
      <p class="hb-intro">
        配置小程序首页顶部轮播。{{ BANNER_SIZE_HINT }}。重要文案放在画面中心，避免被裁切。数字越小越靠前。
      </p>
    </header>

    <article v-if="activePreview.length" class="hb-card">
      <header class="hb-card__head">
        <span class="hb-card__title">小程序轮播顺序</span>
        <span class="hb-card__hint">{{ activePreview.length }} 张上架 · 点击可编辑</span>
      </header>
      <div class="hb-rail">
        <button
          v-for="(row, index) in activePreview"
          :key="row.id"
          type="button"
          class="hb-rail__item"
          @click="openEdit(row)"
        >
          <img v-if="bannerSrc(row.image_url)" :src="bannerSrc(row.image_url)" alt="" />
          <span v-else class="hb-rail__empty">无图</span>
          <span class="hb-rail__index">{{ index + 1 }}</span>
          <span class="hb-rail__meta">
            <strong>{{ row.title || '未命名' }}</strong>
            <em>{{ LINK_LABEL[row.link_type] || '不跳转' }} · {{ linkTargetText(row) }}</em>
          </span>
        </button>
      </div>
    </article>

    <article class="hb-card">
      <header class="hb-card__head">
        <span class="hb-card__title">全部 Banner</span>
        <span class="hb-card__hint">含已下架</span>
      </header>
      <div class="hb-table-wrap">
        <el-table
          v-loading="loading"
          :data="sortedList"
          class="admin-table"
          empty-text="暂无 Banner，请点击右上角新建"
        >
          <el-table-column label="图片" width="108">
            <template #default="{ row }">
              <img v-if="bannerSrc(row.image_url)" :src="bannerSrc(row.image_url)" alt="" class="hb-thumb" />
              <span v-else class="hb-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="备注标题" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.title || '—' }}</template>
          </el-table-column>
          <el-table-column label="跳转" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="hb-link">{{ LINK_LABEL[row.link_type] || row.link_type || '不跳转' }}</span>
              <span class="hb-link-target">{{ linkTargetText(row) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="80" align="center" />
          <el-table-column label="状态" width="96" align="center">
            <template #default="{ row }">
              <el-tag round effect="light" :type="row.is_active ? 'success' : 'info'">
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
    </article>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑 Banner' : '新建 Banner'"
      width="min(92vw, 560px)"
      align-center
      destroy-on-close
      class="hb-dialog"
    >
      <el-form label-position="top" class="hb-form" @submit.prevent="saveBanner">
        <el-form-item label="备注标题">
          <el-input v-model="form.title" placeholder="仅管理端可见" maxlength="128" clearable />
        </el-form-item>

        <el-form-item label="Banner 图" required>
          <div class="hb-upload">
            <el-upload
              :key="photoUploadKey"
              :auto-upload="false"
              :show-file-list="false"
              accept="image/*"
              :disabled="photoUploading"
              @change="onPhotoUploadChange"
            >
              <div v-loading="photoUploading" class="hb-upload__box">
                <img v-if="bannerSrc(form.image_url)" :src="bannerSrc(form.image_url)" alt="" class="hb-upload__preview" />
                <div v-else class="hb-upload__placeholder">
                  <Upload :size="28" stroke-width="1.75" />
                  <span>点击上传图片</span>
                </div>
              </div>
            </el-upload>
            <p class="hb-upload__tip">{{ BANNER_SIZE_HINT }}</p>
            <el-button
              v-if="form.image_url"
              link
              type="danger"
              @click="form.image_url = ''"
            >
              移除图片
            </el-button>
          </div>
        </el-form-item>

        <el-form-item label="跳转类型">
          <el-select v-model="form.link_type" style="width: 100%" @change="onLinkTypeChange">
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
          <el-select v-model="form.link_target" filterable placeholder="选择卡包模版" style="width: 100%">
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
          <el-select v-model="form.link_target" placeholder="选择页面" style="width: 100%">
            <el-option v-for="opt in TAB_OPTIONS" :key="opt.value" :value="opt.value" :label="opt.label" />
          </el-select>
        </el-form-item>

        <el-form-item v-else-if="form.link_type === 'webview'" label="外链 URL">
          <el-input v-model="form.link_target" placeholder="https://..." clearable />
        </el-form-item>

        <div class="hb-form__row">
          <el-form-item label="排序">
            <el-input-number v-model="form.sort_order" :min="0" :max="9999" controls-position="right" />
            <p class="hb-hint">数字越小越靠前</p>
          </el-form-item>
          <el-form-item label="上架">
            <el-switch v-model="form.is_active" active-text="上架" inactive-text="下架" />
          </el-form-item>
        </div>
      </el-form>

      <template #footer>
        <el-button round @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" round :loading="saving" @click="saveBanner">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.hb-page {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  max-width: min(72rem, 100%);
  color: #1d1f21;
}
.hb-page-head {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}
.hb-page-head__bar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.25rem;
}
.hb-page-head__copy {
  min-width: 0;
}
.hb-kicker {
  margin: 0 0 0.2rem;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--el-color-primary);
}
.hb-title {
  margin: 0;
  font-size: 1.65rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.hb-intro {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: #5c6670;
  white-space: nowrap;
}
.hb-add {
  flex-shrink: 0;
  font-weight: 800;
}
.hb-add :deep(span) {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.hb-card {
  padding: 1.05rem 1.15rem 1.15rem;
  border-radius: 22px;
  border: 1px solid rgba(255, 255, 255, 0.82);
  background: rgba(255, 255, 255, 0.72);
  box-shadow:
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 14px 36px rgba(25, 45, 55, 0.06);
  backdrop-filter: saturate(1.15) blur(14px);
  -webkit-backdrop-filter: saturate(1.15) blur(14px);
}
.hb-card__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.9rem;
  padding-bottom: 0.7rem;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.hb-card__title {
  font-size: 15px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hb-card__hint {
  font-size: 12px;
  font-weight: 600;
  color: #8b949e;
}
.hb-rail {
  display: flex;
  gap: 0.75rem;
  overflow-x: auto;
  padding-bottom: 0.15rem;
}
.hb-rail__item {
  position: relative;
  flex: 0 0 168px;
  height: 168px;
  padding: 0;
  border: 0;
  border-radius: 18px;
  overflow: hidden;
  cursor: pointer;
  background: #f4f6f8;
  box-shadow: 0 8px 18px rgba(25, 45, 55, 0.08);
}
.hb-rail__item img,
.hb-rail__empty {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.hb-rail__empty {
  display: grid;
  place-items: center;
  color: #94a3b8;
  font-size: 12px;
}
.hb-rail__index {
  position: absolute;
  top: 8px;
  left: 8px;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(29, 31, 33, 0.72);
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  line-height: 22px;
}
.hb-rail__meta {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 28px 10px 8px;
  background: linear-gradient(180deg, transparent, rgba(15, 23, 42, 0.72));
  color: #fff;
  text-align: left;
}
.hb-rail__meta strong,
.hb-rail__meta em {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: normal;
}
.hb-rail__meta strong {
  font-size: 13px;
}
.hb-rail__meta em {
  font-size: 11px;
  opacity: 0.86;
}
.hb-table-wrap {
  border-radius: 16px;
  overflow: hidden;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.06);
}
.hb-thumb {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 14px;
  display: block;
  background: #f4f6f8;
}
.hb-muted {
  color: #94a3b8;
}
.hb-link,
.hb-link-target {
  display: block;
}
.hb-link {
  font-weight: 700;
}
.hb-link-target {
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
}
.hb-upload__box {
  width: 220px;
  height: 220px;
  border: 1px dashed color-mix(in srgb, var(--el-color-primary) 45%, #e2e8f0);
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  cursor: pointer;
  overflow: hidden;
  background: #fff;
}
.hb-upload__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
}
.hb-upload__preview {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.hb-upload__tip,
.hb-hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}
.hb-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}
.hb-form :deep(.el-form-item__label) {
  font-weight: 700;
  color: #334155;
}
.hb-form :deep(.el-input__wrapper),
.hb-form :deep(.el-select__wrapper) {
  min-height: 40px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}
@media (max-width: 900px) {
  .hb-page-head__bar,
  .hb-form__row {
    display: flex;
    flex-direction: column;
    align-items: stretch;
  }
  .hb-intro {
    white-space: normal;
  }
}
</style>

<style>
.hb-dialog.el-dialog {
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.82);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 18px 48px rgba(25, 45, 55, 0.12);
}
.hb-dialog .el-dialog__header {
  margin-right: 0;
  padding: 16px 20px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.hb-dialog .el-dialog__title {
  font-weight: 800;
  letter-spacing: -0.02em;
}
.hb-dialog .el-dialog__body {
  padding-top: 16px;
}
.hb-dialog .el-dialog__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}
.hb-dialog .el-input__wrapper,
.hb-dialog .el-select__wrapper {
  min-height: 40px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #e2e8f0 inset;
}
.hb-dialog .el-form-item__label {
  font-weight: 700;
  color: #334155;
}
</style>
