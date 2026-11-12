<script setup>
defineOptions({ name: 'DrinksView' })
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Search, Camera, Trash2 } from 'lucide-vue-next'
import { apiJson, apiForm, adminAccessToken, dishImageDisplayUrl, handleAdminLogout } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const DRINK_IMG_FALLBACK =
  'https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&q=80&w=400'

const drinkList = ref([])
const drinksLoading = ref(false)
const drinkModalSaving = ref(false)
const drinkSearchQuery = ref('')
const showDrinkModal = ref(false)
const isEditingDrink = ref(false)
const drinkPhotoUploading = ref(false)

const drinkForm = reactive({
  id: null,
  name: '',
  description: '',
  image_url: '',
  is_enabled: true,
})

const filteredDrinks = computed(() => {
  const q = drinkSearchQuery.value.trim().toLowerCase()
  if (!q) return drinkList.value
  return drinkList.value.filter((item) => (item.name || '').toLowerCase().includes(q))
})

const drinkEditorPreviewDisplayUrl = computed(() => {
  const url = drinkForm.image_url
  if (!url || String(url).trim() === '') return ''
  return dishImageDisplayUrl(url) || ''
})

const drinkEditorPreviewSrcList = computed(() => {
  const url = drinkEditorPreviewDisplayUrl.value
  return url ? [url] : []
})

function onDrinkImgError(event) {
  const el = event.target
  if (el && el.src !== DRINK_IMG_FALLBACK) el.src = DRINK_IMG_FALLBACK
}

async function fetchDrinks() {
  if (!adminAccessToken.value) return
  drinksLoading.value = true
  try {
    const data = await apiJson('/api/admin/drinks', {}, { auth: true })
    drinkList.value = Array.isArray(data) ? data : []
  } catch (error) {
    const status = error && typeof error.status === 'number' ? error.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(error instanceof Error ? error.message : '加载饮品失败', 'error')
    drinkList.value = []
  } finally {
    drinksLoading.value = false
  }
}

function resetDrinkForm() {
  drinkForm.id = null
  drinkForm.name = ''
  drinkForm.description = ''
  drinkForm.image_url = ''
  drinkForm.is_enabled = true
}

function openDrinkEditorAdd() {
  isEditingDrink.value = false
  resetDrinkForm()
  showDrinkModal.value = true
}

function openDrinkEditorEdit(row) {
  isEditingDrink.value = true
  drinkForm.id = row.id
  drinkForm.name = row.name || ''
  drinkForm.description = row.description || ''
  drinkForm.image_url = row.image_url || ''
  drinkForm.is_enabled = row.is_enabled !== false
  showDrinkModal.value = true
}

function closeDrinkModal() {
  showDrinkModal.value = false
}

async function onDrinkPhotoUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  drinkPhotoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      drinkForm.image_url = url
      showToast('图片已上传到服务器', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (error) {
    const status = error && typeof error.status === 'number' ? error.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(error instanceof Error ? error.message : '上传失败', 'error')
  } finally {
    drinkPhotoUploading.value = false
  }
}

async function saveDrink() {
  if (!drinkForm.name?.trim()) {
    showToast('请填写饮品名称', 'error')
    return
  }
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  const body = {
    name: drinkForm.name.trim(),
    description: (drinkForm.description || '').trim() || null,
    image_url: (drinkForm.image_url || '').trim() || null,
    is_enabled: Boolean(drinkForm.is_enabled),
  }
  if (isEditingDrink.value && drinkForm.id != null) body.id = drinkForm.id
  drinkModalSaving.value = true
  try {
    await apiJson('/api/admin/drink', { method: 'POST', body: JSON.stringify(body) }, { auth: true })
    showToast(isEditingDrink.value ? '饮品已更新' : '饮品已创建', 'success')
    closeDrinkModal()
    await fetchDrinks()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    drinkModalSaving.value = false
  }
}

async function deleteDrink(row) {
  if (!row?.id) return
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.name}」？仍被菜品配餐饮选用的饮品不能删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  try {
    await apiJson('/api/admin/drink/' + row.id, { method: 'DELETE' }, { auth: true })
    showToast('已删除', 'success')
    await fetchDrinks()
  } catch (error) {
    const status = error && typeof error.status === 'number' ? error.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(error instanceof Error ? error.message : '删除失败', 'error')
  }
}

onMounted(() => {
  void fetchDrinks()
})
</script>

<template>
  <section class="mkt-page tab-content animate-up menu-section">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">菜单管理</p>
        <h1 class="mkt-title">饮品管理</h1>
        <p class="mkt-intro">随餐饮在这里维护。菜品编辑里的配餐饮只从这份饮品库里选。</p>
      </div>
      <div class="dish-toolbar">
        <div class="dish-toolbar-filters">
          <el-input v-model="drinkSearchQuery" clearable placeholder="按饮品名称筛选…" class="dish-search">
            <template #prefix>
              <Search :size="16" stroke-width="2.25" class="dish-search__icon" aria-hidden="true" />
            </template>
          </el-input>
        </div>
        <div class="dish-toolbar-actions">
          <p v-if="drinksLoading" class="dish-toolbar-status">正在加载…</p>
          <p v-else class="dish-toolbar-status">
            共 <strong class="dish-toolbar-count">{{ filteredDrinks.length }}</strong> 款
          </p>
          <el-button type="primary" round class="dish-toolbar-create" @click="openDrinkEditorAdd">新建饮品</el-button>
        </div>
      </div>
    </header>

    <div v-if="drinksLoading && !drinkList.length" class="dish-catalog-empty">正在加载饮品库…</div>
    <div v-else-if="!filteredDrinks.length" class="dish-catalog-empty">
      <p>{{ drinkSearchQuery.trim() ? '没有匹配的饮品' : '暂无饮品' }}</p>
      <el-button v-if="!drinkSearchQuery.trim()" type="primary" round @click="openDrinkEditorAdd">
        新建第一款饮品
      </el-button>
    </div>

    <div v-else class="dish-compact-grid">
      <article
        v-for="item in filteredDrinks"
        :key="item.id"
        class="dish-compact-card"
        :class="{ 'dish-compact-card--off': item.is_enabled === false }"
      >
        <div class="dish-compact-card__img">
          <img
            :src="dishImageDisplayUrl(item.image_url) || DRINK_IMG_FALLBACK"
            :alt="item.name"
            loading="lazy"
            @error="onDrinkImgError"
          />
        </div>
        <div class="dish-compact-card__body">
          <div class="dish-compact-card__head">
            <h4 class="dish-compact-card__name" :title="item.name">{{ item.name }}</h4>
            <span
              class="dish-compact-card__status"
              :class="{ 'dish-compact-card__status--off': item.is_enabled === false }"
            >
              {{ item.is_enabled !== false ? '启用' : '停用' }}
            </span>
          </div>
          <p v-if="item.description" class="dish-compact-card__desc">{{ item.description }}</p>
          <div class="dish-compact-card__footer">
            <div class="dish-compact-card__actions">
              <button type="button" class="dish-compact-btn dish-compact-btn--edit" @click="openDrinkEditorEdit(item)">
                编辑
              </button>
              <button type="button" class="dish-compact-btn dish-compact-btn--delete" @click="deleteDrink(item)">
                <Trash2 :size="14" stroke-width="2" />
              </button>
            </div>
          </div>
        </div>
      </article>
    </div>

    <el-drawer
      v-model="showDrinkModal"
      direction="rtl"
      size="1080px"
      destroy-on-close
      :close-on-click-modal="true"
      class="dish-editor-drawer"
    >
      <template #header>
        <h3 class="menu-editor-title-h3">{{ isEditingDrink ? '编辑饮品' : '新建饮品' }}</h3>
      </template>

      <div class="dish-editor-drawer-body">
        <aside class="dish-editor-media">
          <div class="dish-editor-preview" :class="{ 'dish-editor-preview--has-image': !!drinkForm.image_url }">
            <el-image
              v-if="drinkForm.image_url"
              class="dish-editor-preview-el"
              :src="drinkEditorPreviewDisplayUrl"
              :preview-src-list="drinkEditorPreviewSrcList"
              fit="cover"
              preview-teleported
              hide-on-click-modal
            >
              <template #error>
                <div class="dish-editor-preview-placeholder dish-editor-preview-placeholder--small">
                  <span>图片加载失败</span>
                </div>
              </template>
            </el-image>
            <div v-else class="dish-editor-preview-placeholder">
              <Camera :size="40" stroke-width="1.75" />
              <p>{{ drinkPhotoUploading ? '正在上传…' : '暂无图片，可上传或在下方粘贴链接' }}</p>
            </div>
            <div v-if="drinkForm.image_url" class="dish-editor-preview-hover" aria-hidden="true">
              <span class="dish-editor-preview-hover-text">点击查看大图</span>
            </div>
          </div>
          <el-upload
            :show-file-list="false"
            :auto-upload="false"
            accept="image/*"
            class="dish-editor-upload-trigger"
            @change="onDrinkPhotoUploadChange"
          >
            <template #trigger>
              <el-button type="primary" round :loading="drinkPhotoUploading" :disabled="drinkPhotoUploading">
                {{ drinkForm.image_url ? '更换饮品图' : '上传饮品图' }}
              </el-button>
            </template>
          </el-upload>
          <label class="menu-editor-label" for="drink-image-url">图片链接（可选，支持 https外链）</label>
          <el-input
            id="drink-image-url"
            v-model="drinkForm.image_url"
            placeholder="https://… 或上传后自动填入相对路径"
            clearable
          />
        </aside>

        <div class="dish-editor-form-col">
          <label class="menu-editor-label" for="drink-name">饮品名称</label>
          <el-input id="drink-name" v-model="drinkForm.name" placeholder="如：柠檬气泡" clearable />

          <div class="drink-status-row">
            <label class="menu-editor-label" for="drink-enabled">状态</label>
            <div class="dish-switch-el">
              <el-switch id="drink-enabled" v-model="drinkForm.is_enabled" />
              <span>{{ drinkForm.is_enabled ? '启用' : '停用' }}</span>
            </div>
          </div>

          <label class="menu-editor-label" for="drink-desc">说明</label>
          <el-input
            id="drink-desc"
            v-model="drinkForm.description"
            type="textarea"
            :rows="4"
            class="drink-desc"
            placeholder="如：冷放、放袋侧。会员端暂不展示，给后厨和配餐饮识别用。"
          />
        </div>
      </div>

      <template #footer>
        <div class="dish-editor-drawer-footer">
          <el-button round @click="closeDrinkModal">取消</el-button>
          <el-button type="primary" round :loading="drinkModalSaving" @click="saveDrink">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.menu-section > .mkt-page-head {
  align-items: center;
}
.menu-section > .mkt-page-head .dish-toolbar {
  flex: 1;
  flex-wrap: nowrap;
  justify-content: flex-end;
  align-items: center;
  margin-bottom: 0;
  min-width: 0;
  gap: 0.75rem;
}
.dish-toolbar-filters,
.dish-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.dish-toolbar-actions {
  flex-shrink: 0;
}
.dish-toolbar-status {
  display: inline-flex;
  align-items: baseline;
  gap: 0.2rem;
  margin: 0;
  font-size: 13px;
  font-weight: 650;
  color: #5c6670;
  white-space: nowrap;
}
.dish-toolbar-count {
  font-size: 1.45rem;
  font-weight: 800;
  line-height: 1;
  letter-spacing: -0.04em;
  color: var(--el-color-primary);
}
.dish-toolbar-create.el-button {
  height: 32px;
  padding: 0 16px;
  font-weight: 700;
}
.dish-search {
  flex: 0 1 280px;
  width: 280px;
  max-width: 320px;
  min-width: 180px;
}
.dish-search :deep(.el-input__wrapper) {
  min-height: 32px;
  height: 32px;
  padding: 0 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 1px 2px rgba(25, 45, 55, 0.04);
}
.dish-search :deep(.el-input__wrapper.is-focus) {
  border-color: rgba(var(--el-color-primary-rgb, 232, 146, 124), 0.45);
  box-shadow: 0 0 0 3px rgba(var(--el-color-primary-rgb, 232, 146, 124), 0.14);
}
.dish-search__icon {
  color: #8b949e;
}
.dish-catalog-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem 1rem;
  color: #94a3b8;
  font-size: 13px;
  font-weight: 700;
}
.dish-catalog-empty p {
  margin: 0;
}
.dish-compact-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.55rem;
}
.dish-compact-card {
  display: flex;
  gap: 0.6rem;
  padding: 0.55rem 0.6rem;
  background: #fff;
  border: 1px solid #eef2f6;
  border-radius: 0.65rem;
}
.dish-compact-card--off {
  opacity: 0.72;
}
.dish-compact-card__img {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border-radius: 0.45rem;
  overflow: hidden;
  background: #f1f5f9;
}
.dish-compact-card__img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dish-compact-card__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.dish-compact-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.4rem;
}
.dish-compact-card__name {
  margin: 0;
  font-size: 13px;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.35;
}
.dish-compact-card__status {
  flex-shrink: 0;
  padding: 1px 6px;
  border-radius: 99px;
  font-size: 9px;
  font-weight: 900;
  background: #fef9c3;
  color: #0e5a44;
}
.dish-compact-card__status--off {
  background: #e2e8f0;
  color: #64748b;
}
.dish-compact-card__desc {
  margin: 0;
  font-size: 10px;
  color: #94a3b8;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.dish-compact-card__footer {
  margin-top: auto;
}
.dish-compact-card__actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.dish-compact-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 0.4rem;
  cursor: pointer;
  font-family: inherit;
}
.dish-compact-btn--edit {
  padding: 0.2rem 0.55rem;
  font-size: 10px;
  font-weight: 800;
  background: #f8fafc;
  color: #475569;
}
.dish-compact-btn--delete {
  padding: 0.2rem 0.35rem;
  background: #fff1f2;
  color: #e11d48;
}
.dish-editor-drawer :deep(.el-drawer) {
  border-top-left-radius: 22px;
  border-bottom-left-radius: 22px;
}
.dish-editor-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}
.dish-editor-drawer :deep(.el-drawer__footer) {
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  padding: 12px 20px 16px;
}
.menu-editor-title-h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
}
.dish-editor-drawer-body {
  display: flex;
  gap: 1.5rem;
  align-items: stretch;
}
.dish-editor-media {
  flex: 0 0 420px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.dish-editor-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  min-height: 360px;
  max-height: 460px;
  border-radius: 18px;
  border: 1px dashed #e6eaee;
  background: #f8fafc;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dish-editor-preview-el {
  width: 100%;
  height: 100%;
}
.dish-editor-preview-el :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dish-editor-preview-hover {
  pointer-events: none;
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0) 0%, rgba(15, 23, 42, 0.5) 100%);
  opacity: 0;
}
.dish-editor-preview--has-image:hover .dish-editor-preview-hover {
  opacity: 1;
}
.dish-editor-preview-hover-text {
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.95);
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 800;
}
.dish-editor-preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1.5rem;
  color: #94a3b8;
  text-align: center;
}
.dish-editor-upload-trigger,
.dish-editor-upload-trigger :deep(.el-upload),
.dish-editor-upload-trigger :deep(.el-button) {
  width: 100%;
}
.dish-editor-upload-trigger :deep(.el-button) {
  border-radius: 999px;
}
.dish-editor-form-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.menu-editor-label {
  margin: 18px 0 8px;
  color: #334155;
  font-size: 13px;
  font-weight: 700;
}
.dish-editor-form-col > .menu-editor-label:first-child,
.drink-status-row > .menu-editor-label {
  margin-top: 0;
}
.drink-status-row {
  margin-top: 18px;
}
.dish-switch-el {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.drink-desc {
  flex: 1;
}
.dish-editor-drawer-footer {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}
@media (max-width: 900px) {
  .dish-editor-drawer-body {
    flex-direction: column;
  }
  .dish-editor-media {
    flex-basis: auto;
    width: 100%;
  }
}
</style>
