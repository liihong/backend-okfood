<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Search, Camera, Trash2, X } from 'lucide-vue-next'
import {
  apiJson,
  apiForm,
  adminAccessToken,
  dishImageDisplayUrl,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const dishList = ref([])
const categoriesList = ref([])
const dishesLoading = ref(false)
const dishModalSaving = ref(false)
const dishSearchQuery = ref('')

const MENU_IMG_FALLBACK =
  'https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&q=80&w=400'

const filteredDishes = computed(() => {
  const q = dishSearchQuery.value.trim().toLowerCase()
  const list = dishList.value
  if (!q) return list
  return list.filter((d) => (d.name || '').toLowerCase().includes(q))
})

function categoryLabel(categoryId) {
  if (categoryId == null || categoryId === '') return '未分类'
  const c = categoriesList.value.find((x) => x.id === categoryId)
  return c ? c.name : '未知分类'
}

const onDishImgError = (e) => {
  const el = e.target
  if (el && el.src !== MENU_IMG_FALLBACK) el.src = MENU_IMG_FALLBACK
}

const showDishModal = ref(false)
const isEditingDish = ref(false)
const dishForm = reactive({
  id: null,
  name: '',
  description: '',
  image_url: '',
  is_enabled: true,
  category_id: '',
})
const dishFileInput = ref(null)
const dishPhotoUploading = ref(false)

async function fetchCategoriesForDishes() {
  if (!adminAccessToken.value) return
  try {
    const data = await apiJson('/api/admin/categories', {}, { auth: true })
    categoriesList.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载分类失败', 'error')
  }
}

async function fetchDishes() {
  if (!adminAccessToken.value) return
  dishesLoading.value = true
  try {
    const data = await apiJson('/api/admin/dishes', {}, { auth: true })
    dishList.value = Array.isArray(data) ? data : []
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载菜品失败', 'error')
    dishList.value = []
  } finally {
    dishesLoading.value = false
  }
}

function resetDishForm() {
  dishForm.id = null
  dishForm.name = ''
  dishForm.description = ''
  dishForm.image_url = ''
  dishForm.is_enabled = true
  dishForm.category_id = ''
}

const openDishEditorAdd = () => {
  isEditingDish.value = false
  resetDishForm()
  showDishModal.value = true
}

const openDishEditorEdit = (row) => {
  isEditingDish.value = true
  dishForm.id = row.id
  dishForm.name = row.name || ''
  dishForm.description = row.description || ''
  dishForm.image_url = row.image_url || ''
  dishForm.is_enabled = row.is_enabled !== false
  dishForm.category_id = row.category_id != null ? String(row.category_id) : ''
  showDishModal.value = true
}

const closeDishModal = () => {
  showDishModal.value = false
}

const triggerDishPhotoPick = () => {
  if (dishPhotoUploading.value) return
  dishFileInput.value?.click()
}

const onDishPhotoChange = async (e) => {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  dishPhotoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      dishForm.image_url = url
      showToast('图片已上传到服务器', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (err) {
    const status = err && typeof err.status === 'number' ? err.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(err instanceof Error ? err.message : '上传失败', 'error')
  } finally {
    dishPhotoUploading.value = false
  }
}

async function saveDish() {
  if (!dishForm.name?.trim()) {
    showToast('请填写菜品名称', 'error')
    return
  }
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  const categoryId =
    dishForm.category_id === '' || dishForm.category_id == null
      ? null
      : parseInt(String(dishForm.category_id), 10)
  const body = {
    name: dishForm.name.trim(),
    description: (dishForm.description || '').trim() || null,
    image_url: (dishForm.image_url || '').trim() || null,
    is_enabled: Boolean(dishForm.is_enabled),
    category_id: Number.isFinite(categoryId) ? categoryId : null,
  }
  if (isEditingDish.value && dishForm.id != null) {
    body.id = dishForm.id
  }
  dishModalSaving.value = true
  try {
    await apiJson('/api/admin/dish', { method: 'POST', body: JSON.stringify(body) }, { auth: true })
    showToast(isEditingDish.value ? '菜品已更新' : '菜品已创建', 'success')
    closeDishModal()
    await fetchDishes()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    dishModalSaving.value = false
  }
}

async function deleteDish(row) {
  if (!row?.id) return
  if (!confirm('确定删除「' + row.name + '」？若仍被排期引用，接口将拒绝删除。')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  try {
    await apiJson('/api/admin/dish/' + row.id, { method: 'DELETE' }, { auth: true })
    showToast('已删除', 'success')
    await fetchDishes()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(() => {
  void fetchCategoriesForDishes()
  void fetchDishes()
})
</script>

<template>
  <section class="tab-content animate-up menu-section">
    <div class="dish-toolbar">
      <div class="dish-toolbar-search">
        <Search :size="18" />
        <input v-model="dishSearchQuery" type="search" placeholder="按菜品名称筛选…" />
      </div>
      <p v-if="dishesLoading" class="dish-toolbar-status">正在加载菜品库…</p>
      <p v-else class="dish-toolbar-status">共 {{ filteredDishes.length }} 道</p>
    </div>
    <div class="menu-grid">
      <div v-for="d in filteredDishes" :key="d.id" class="menu-card">
        <div class="menu-card-img">
          <img
            :src="dishImageDisplayUrl(d.image_url) || MENU_IMG_FALLBACK"
            :alt="d.name"
            loading="lazy"
            @error="onDishImgError"
          />
          <div class="menu-date-tag">#{{ d.id }}</div>
          <div class="menu-sync-badge" :class="{ 'menu-sync-badge--off': d.is_enabled === false }">
            {{ d.is_enabled !== false ? '上架' : '停用' }}
          </div>
        </div>
        <p class="menu-card-meta">{{ categoryLabel(d.category_id) }}</p>
        <div class="menu-card-body">
          <h4 class="menu-dish-title">【 {{ d.name }} 】</h4>
          <p class="menu-dish-desc">{{ d.description || '—' }}</p>
          <div class="menu-card-actions menu-card-actions--spread">
            <button type="button" class="menu-btn-ghost" @click="openDishEditorEdit(d)">编辑</button>
            <button type="button" class="menu-btn-danger" @click="deleteDish(d)">
              <Trash2 :size="16" stroke-width="2" /> 删除
            </button>
          </div>
        </div>
      </div>
      <button type="button" class="menu-card menu-add-card" @click="openDishEditorAdd">
        <span class="menu-add-plus">+</span>
        <span class="menu-add-label">新建菜品</span>
      </button>
    </div>

    <div v-if="showDishModal" class="modal-overlay menu-editor-overlay" @click.self="closeDishModal">
      <div class="modal-card menu-editor-card">
        <div class="modal-header">
          <div class="header-info">
            <h3 class="menu-editor-title-h3">
              {{ isEditingDish ? '编辑菜品' : '新建菜品' }}
            </h3>
            <p class="menu-editor-subtitle">DISH CATALOG · CRUD</p>
          </div>
          <button type="button" class="close-btn" @click="closeDishModal"><X :size="20" /></button>
        </div>
        <div class="modal-body menu-editor-body">
          <input
            ref="dishFileInput"
            type="file"
            class="menu-file-input-hidden"
            accept="image/*"
            @change="onDishPhotoChange"
          />
          <label class="menu-editor-label">展示图（可选）</label>
          <button
            type="button"
            class="menu-upload-sim"
            :disabled="dishPhotoUploading"
            @click="triggerDishPhotoPick"
          >
            <img
              v-if="dishForm.image_url"
              :src="dishImageDisplayUrl(dishForm.image_url)"
              alt=""
              class="menu-upload-preview"
            />
            <div v-else class="menu-upload-inner">
              <Camera :size="32" stroke-width="1.75" class="menu-upload-icon" />
              <p class="menu-upload-text">
                {{ dishPhotoUploading ? '正在上传…' : '点击上传至服务器，或下方粘贴外链' }}
              </p>
            </div>
            <span v-if="dishForm.image_url && !dishPhotoUploading" class="menu-upload-change-hint"
              >点击更换</span
            >
          </button>
          <label class="menu-editor-label" for="dish-image-url">图片链接（可选，支持 https外链）</label>
          <input
            id="dish-image-url"
            v-model="dishForm.image_url"
            type="url"
            class="menu-editor-input"
            placeholder="https://… 或上传后自动填入相对路径"
          />

          <label class="menu-editor-label" for="dish-name">菜品名称</label>
          <input
            id="dish-name"
            v-model="dishForm.name"
            type="text"
            class="menu-editor-input menu-editor-input-name"
            placeholder="如：盐葱鸡腿排能量碗"
          />

          <div class="menu-editor-row">
            <div class="menu-editor-field menu-editor-field-grow">
              <label class="menu-editor-label" for="dish-category">分类</label>
              <select id="dish-category" v-model="dishForm.category_id" class="menu-editor-input">
                <option value="">未分类</option>
                <option v-for="c in categoriesList" :key="c.id" :value="String(c.id)">
                  {{ c.name }} ({{ c.code }})
                </option>
              </select>
            </div>
            <div class="menu-editor-field dish-enabled-field">
              <label class="menu-editor-label" for="dish-enabled">状态</label>
              <label class="dish-switch">
                <input id="dish-enabled" v-model="dishForm.is_enabled" type="checkbox" />
                <span>{{ dishForm.is_enabled ? '启用' : '停用' }}</span>
              </label>
            </div>
          </div>

          <label class="menu-editor-label" for="dish-desc">配料 / 描述</label>
          <textarea
            id="dish-desc"
            v-model="dishForm.description"
            class="menu-editor-textarea"
            rows="3"
            placeholder="原切鸡腿肉、秘制盐葱酱、杂粮基底、时令蔬果。"
          ></textarea>

          <div class="menu-editor-footer-btns">
            <button type="button" class="menu-btn-draft" @click="closeDishModal">取消</button>
            <button
              type="button"
              class="menu-btn-save-sync"
              :disabled="dishModalSaving"
              @click="saveDish"
            >
              {{ dishModalSaving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
