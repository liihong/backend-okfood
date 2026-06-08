<script setup>
defineOptions({ name: 'MenuView' })
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
import { buildCategoryTree, categoryChildrenByParentCode, toCascaderOptions } from '../utils/categoryTree.js'

const dishList = ref([])
const categoriesList = ref([])
const dishesLoading = ref(false)
const dishModalSaving = ref(false)
const dishSearchQuery = ref('')
const dishCategoryFilter = ref(null)

const MENU_IMG_FALLBACK =
  'https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&q=80&w=400'

const filteredDishes = computed(() => {
  const q = dishSearchQuery.value.trim().toLowerCase()
  const list = dishList.value
  if (!q) return list
  return list.filter((d) => (d.name || '').toLowerCase().includes(q))
})

const activeCategories = computed(() =>
  categoriesList.value.filter((x) => x.is_active !== false),
)

const categoryTree = computed(() => buildCategoryTree(activeCategories.value))

const meatCategoryOptions = computed(() => categoryChildrenByParentCode(activeCategories.value, 'meat'))

const dishTypeCategoryOptions = computed(() => categoryChildrenByParentCode(activeCategories.value, 'dish_type'))

const dishFilterCascaderOptions = computed(() => {
  const uncategorized = { value: 0, label: '未分类' }
  return [uncategorized, ...toCascaderOptions(categoryTree.value, { leafOnly: false })]
})

function dishTypeLabel(d) {
  if (d.dish_type_category_id == null) return '未分类'
  const cat = categoriesList.value.find((c) => c.id === d.dish_type_category_id)
  return cat?.name || '未知'
}

const UNCategorized_MEAT_KEY = '__none__'

const dishesByMeatGroup = computed(() => {
  const byKey = new Map()
  const ordered = []

  for (const c of meatCategoryOptions.value) {
    const group = { key: c.id, label: c.name, dishes: [] }
    byKey.set(c.id, group)
    ordered.push(group)
  }

  const unassigned = { key: UNCategorized_MEAT_KEY, label: '未设置肉类', dishes: [] }

  for (const d of filteredDishes.value) {
    const key = d.meat_category_id ?? UNCategorized_MEAT_KEY
    if (key === UNCategorized_MEAT_KEY) {
      unassigned.dishes.push(d)
    } else if (byKey.has(key)) {
      byKey.get(key).dishes.push(d)
    } else {
      unassigned.dishes.push(d)
    }
  }

  const result = ordered.filter((g) => g.dishes.length > 0)
  if (unassigned.dishes.length > 0) result.push(unassigned)
  return result
})

const hasVisibleDishes = computed(() => dishesByMeatGroup.value.length > 0)

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
  single_order_price_yuan: '',
  image_url: '',
  is_enabled: true,
  meat_category_id: null,
  dish_type_category_id: null,
  spice_level: '',
  internal_view_sop: '',
})

const SPICE_ADMIN_LABELS = {
  '': '未标注',
  none: '不辣',
  mild: '微微辣',
  medium: '微辣',
  hot: '较辣',
}

function dishSpiceBadge(row) {
  const k = row && row.spice_level != null ? String(row.spice_level).trim().toLowerCase() : ''
  if (!k) return '未标注'
  return SPICE_ADMIN_LABELS[k] || '未标注'
}
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
    const params = new URLSearchParams()
    if (dishCategoryFilter.value != null && dishCategoryFilter.value !== '') {
      params.set('category_id', String(dishCategoryFilter.value))
    }
    const qs = params.toString()
    const path = qs ? `/api/admin/dishes?${qs}` : '/api/admin/dishes'
    const data = await apiJson(path, {}, { auth: true })
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
  dishForm.single_order_price_yuan = ''
  dishForm.image_url = ''
  dishForm.is_enabled = true
  dishForm.meat_category_id = null
  dishForm.dish_type_category_id = null
  dishForm.spice_level = ''
  dishForm.internal_view_sop = ''
}

const openDishEditorAdd = () => {
  isEditingDish.value = false
  resetDishForm()
  showDishModal.value = true
}

const openDishEditorEdit = async (row) => {
  isEditingDish.value = true
  dishForm.id = row.id
  dishForm.name = row.name || ''
  dishForm.description = row.description || ''
  dishForm.single_order_price_yuan =
    row.single_order_price_yuan != null && String(row.single_order_price_yuan).trim() !== ''
      ? String(row.single_order_price_yuan).trim()
      : ''
  dishForm.image_url = row.image_url || ''
  dishForm.is_enabled = row.is_enabled !== false
  dishForm.meat_category_id = row.meat_category_id != null ? row.meat_category_id : null
  dishForm.dish_type_category_id = row.dish_type_category_id != null ? row.dish_type_category_id : null
  dishForm.spice_level = row.spice_level != null ? String(row.spice_level).trim().toLowerCase() : ''
  dishForm.internal_view_sop = ''
  showDishModal.value = true
  if (!adminAccessToken.value || row.id == null) return
  try {
    const detail = await apiJson(`/api/admin/dish/${row.id}`, {}, { auth: true })
    if (detail && typeof detail === 'object') {
      dishForm.description = detail.description || dishForm.description
      dishForm.image_url = detail.image_url || dishForm.image_url
      dishForm.internal_view_sop =
        detail.internal_view_sop != null ? String(detail.internal_view_sop) : ''
      if (detail.spice_level != null) {
        dishForm.spice_level = String(detail.spice_level).trim().toLowerCase()
      }
      if (detail.single_order_price_yuan != null && String(detail.single_order_price_yuan).trim() !== '') {
        dishForm.single_order_price_yuan = String(detail.single_order_price_yuan).trim()
      }
      if (detail.meat_category_id != null) {
        dishForm.meat_category_id = detail.meat_category_id
      }
      if (detail.dish_type_category_id != null) {
        dishForm.dish_type_category_id = detail.dish_type_category_id
      }
    }
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载菜品详情失败', 'error')
  }
}

const closeDishModal = () => {
  showDishModal.value = false
}

const dishPhotoUploadKey = ref(0)

const onDishPhotoUploadChange = async (uploadFile) => {
  const file = uploadFile?.raw
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
    dishPhotoUploadKey.value += 1
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
  const meatCategoryId =
    dishForm.meat_category_id === '' || dishForm.meat_category_id == null
      ? null
      : parseInt(String(dishForm.meat_category_id), 10)
  const dishTypeCategoryId =
    dishForm.dish_type_category_id === '' || dishForm.dish_type_category_id == null
      ? null
      : parseInt(String(dishForm.dish_type_category_id), 10)
  const priceStr = String(dishForm.single_order_price_yuan ?? '').trim()
  let single_order_price_yuan = null
  if (priceStr !== '') {
    const n = Number(priceStr)
    if (!Number.isFinite(n) || n < 0) {
      showToast('单点价格需为大于等于 0 的数字', 'error')
      return
    }
    single_order_price_yuan = n
  }
  const spiceRaw = String(dishForm.spice_level ?? '').trim().toLowerCase()
  const body = {
    name: dishForm.name.trim(),
    description: (dishForm.description || '').trim() || null,
    image_url: (dishForm.image_url || '').trim() || null,
    is_enabled: Boolean(dishForm.is_enabled),
    meat_category_id: Number.isFinite(meatCategoryId) ? meatCategoryId : null,
    dish_type_category_id: Number.isFinite(dishTypeCategoryId) ? dishTypeCategoryId : null,
    single_order_price_yuan,
    spice_level: spiceRaw === '' ? null : spiceRaw,
    internal_view_sop: (dishForm.internal_view_sop || '').trim() || null,
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
      <div class="dish-toolbar-filters">
        <div class="dish-toolbar-search">
          <Search :size="18" />
          <el-input
            v-model="dishSearchQuery"
            type="search"
            clearable
            placeholder="按菜品名称筛选…"
            class="dish-toolbar-search-input"
          />
        </div>
        <el-cascader
          v-model="dishCategoryFilter"
          :options="dishFilterCascaderOptions"
          :props="{ emitPath: false, checkStrictly: true }"
          clearable
          placeholder="全部分类"
          class="dish-toolbar-category"
          @change="fetchDishes"
        />
      </div>
      <div class="dish-toolbar-actions">
        <p v-if="dishesLoading" class="dish-toolbar-status">正在加载…</p>
        <p v-else class="dish-toolbar-status">共 {{ filteredDishes.length }} 道</p>
        <button type="button" class="dish-toolbar-add-btn" @click="openDishEditorAdd">+ 新建菜品</button>
      </div>
    </div>

    <div v-if="dishesLoading && !dishList.length" class="dish-catalog-empty">正在加载菜品库…</div>
    <div v-else-if="!hasVisibleDishes" class="dish-catalog-empty">
      <p>暂无菜品</p>
      <button type="button" class="dish-toolbar-add-btn" @click="openDishEditorAdd">新建第一道菜品</button>
    </div>

    <div v-else class="dish-catalog">
      <section
        v-for="group in dishesByMeatGroup"
        :key="group.key"
        class="dish-meat-section"
      >
        <header class="dish-meat-section__head">
          <h3 class="dish-meat-section__title">{{ group.label }}</h3>
          <span class="dish-meat-section__count">{{ group.dishes.length }} 道</span>
        </header>

        <div class="dish-compact-grid">
          <article
            v-for="d in group.dishes"
            :key="d.id"
            class="dish-compact-card"
            :class="{ 'dish-compact-card--off': d.is_enabled === false }"
          >
            <div class="dish-compact-card__img">
              <img
                :src="dishImageDisplayUrl(d.image_url) || MENU_IMG_FALLBACK"
                :alt="d.name"
                loading="lazy"
                @error="onDishImgError"
              />
            </div>
            <div class="dish-compact-card__body">
              <div class="dish-compact-card__head">
                <h4 class="dish-compact-card__name" :title="d.name">{{ d.name }}</h4>
                <span
                  class="dish-compact-card__status"
                  :class="{ 'dish-compact-card__status--off': d.is_enabled === false }"
                >
                  {{ d.is_enabled !== false ? '上架' : '停用' }}
                </span>
              </div>
              <p class="dish-compact-card__meta">
                <span>{{ dishTypeLabel(d) }}</span>
                <span class="dish-compact-card__dot">·</span>
                <span>辣度 {{ dishSpiceBadge(d) }}</span>
                <span v-if="d.single_order_price_yuan != null && String(d.single_order_price_yuan).trim() !== ''" class="dish-compact-card__dot">·</span>
                <span
                  v-if="d.single_order_price_yuan != null && String(d.single_order_price_yuan).trim() !== ''"
                  class="dish-compact-card__price"
                >
                  ¥{{ d.single_order_price_yuan }}
                </span>
              </p>
              <p v-if="d.description" class="dish-compact-card__desc">{{ d.description }}</p>
              <div class="dish-compact-card__actions">
                <button type="button" class="dish-compact-btn dish-compact-btn--edit" @click="openDishEditorEdit(d)">
                  编辑
                </button>
                <button type="button" class="dish-compact-btn dish-compact-btn--delete" @click="deleteDish(d)">
                  <Trash2 :size="14" stroke-width="2" />
                </button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div
      v-if="showDishModal"
      class="modal-overlay menu-editor-overlay"
      v-esc-close="closeDishModal"
      @click.self="closeDishModal"
    >
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
          <el-upload
            :key="dishPhotoUploadKey"
            class="menu-dish-photo-upload"
            :show-file-list="false"
            :auto-upload="false"
            accept="image/*"
            @change="onDishPhotoUploadChange"
          >
            <button
              type="button"
              class="menu-upload-sim"
              :disabled="dishPhotoUploading"
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
          </el-upload>
          <label class="menu-editor-label" for="dish-image-url">图片链接（可选，支持 https外链）</label>
          <el-input
            id="dish-image-url"
            v-model="dishForm.image_url"
            class="menu-editor-input-el"
            placeholder="https://… 或上传后自动填入相对路径"
            clearable
          />

          <label class="menu-editor-label" for="dish-name">菜品名称</label>
          <el-input
            id="dish-name"
            v-model="dishForm.name"
            class="menu-editor-input-el menu-editor-input-name"
            placeholder="如：盐葱鸡腿排能量碗"
            clearable
          />

          <div class="menu-editor-row">
            <div class="menu-editor-field menu-editor-field-grow">
              <label class="menu-editor-label" for="dish-meat-category">肉类</label>
              <el-select
                id="dish-meat-category"
                v-model="dishForm.meat_category_id"
                class="menu-editor-input-el"
                clearable
                placeholder="请选择肉类"
              >
                <el-option
                  v-for="c in meatCategoryOptions"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </div>
            <div class="menu-editor-field menu-editor-field-grow">
              <label class="menu-editor-label" for="dish-type-category">菜品分类</label>
              <el-select
                id="dish-type-category"
                v-model="dishForm.dish_type_category_id"
                class="menu-editor-input-el"
                clearable
                placeholder="请选择菜品分类"
              >
                <el-option
                  v-for="c in dishTypeCategoryOptions"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </div>
            <div class="menu-editor-field dish-enabled-field">
              <label class="menu-editor-label" for="dish-enabled">状态</label>
              <div class="dish-switch-el">
                <el-switch id="dish-enabled" v-model="dishForm.is_enabled" />
                <span>{{ dishForm.is_enabled ? '启用' : '停用' }}</span>
              </div>
            </div>
          </div>

          <label class="menu-editor-label" for="dish-desc">配料 / 描述</label>
          <el-input
            id="dish-desc"
            v-model="dishForm.description"
            type="textarea"
            :rows="3"
            class="menu-editor-textarea-el"
            placeholder="原切鸡腿肉、秘制盐葱酱、杂粮基底、时令蔬果。"
          />

          <label class="menu-editor-label" for="dish-spice">辣度（会员端可见）</label>
          <el-select id="dish-spice" v-model="dishForm.spice_level" class="menu-editor-input-el" clearable placeholder="未标注">
            <el-option label="未标注" value="" />
            <el-option label="不辣" value="none" />
            <el-option label="微微辣" value="mild" />
            <el-option label="微辣" value="medium" />
            <el-option label="较辣" value="hot" />
          </el-select>

          <label class="menu-editor-label" for="dish-internal-sop">内部操作说明（仅后台，不对会员展示）</label>
          <el-input
            id="dish-internal-sop"
            v-model="dishForm.internal_view_sop"
            type="textarea"
            :rows="3"
            class="menu-editor-textarea-el"
            placeholder="备餐衔接、内部话术等；会员可见信息请写在配料/描述中。"
          />

          <label class="menu-editor-label" for="dish-single-price">单点价格（元，可选）</label>
          <el-input
            id="dish-single-price"
            v-model="dishForm.single_order_price_yuan"
            class="menu-editor-input-el"
            placeholder="留空表示未定价，会员端显示「待公布」"
            clearable
          />

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

<style scoped>
.dish-toolbar-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}
.dish-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}
.dish-toolbar-add-btn {
  padding: 0.45rem 0.9rem;
  border: none;
  border-radius: 0.55rem;
  background: #0e5a44;
  color: #fff;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  transition: filter 0.2s;
}
.dish-toolbar-add-btn:hover {
  filter: brightness(1.06);
}
.dish-toolbar-category {
  width: 200px;
  min-width: 160px;
}
.dish-toolbar-search-input {
  flex: 1;
  min-width: 0;
}

.dish-catalog {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
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

.dish-meat-section__head {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
  padding-bottom: 0.45rem;
  border-bottom: 2px solid #e2e8f0;
}
.dish-meat-section__title {
  margin: 0;
  font-size: 15px;
  font-weight: 900;
  color: #0e5a44;
  letter-spacing: 0.02em;
}
.dish-meat-section__count {
  font-size: 11px;
  font-weight: 800;
  color: #94a3b8;
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
  transition: box-shadow 0.2s, border-color 0.2s;
}
.dish-compact-card:hover {
  border-color: #cbd5e1;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.04);
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
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
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

.dish-compact-card__meta {
  margin: 0;
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  line-height: 1.4;
}
.dish-compact-card__dot {
  margin: 0 0.15rem;
  color: #cbd5e1;
}
.dish-compact-card__price {
  color: #0f766e;
  font-weight: 800;
}

.dish-compact-card__desc {
  margin: 0;
  font-size: 10px;
  color: #94a3b8;
  line-height: 1.4;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
}

.dish-compact-card__actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.15rem;
}
.dish-compact-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 0.4rem;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}
.dish-compact-btn--edit {
  padding: 0.2rem 0.55rem;
  font-size: 10px;
  font-weight: 800;
  background: #f8fafc;
  color: #475569;
}
.dish-compact-btn--edit:hover {
  background: #e2e8f0;
}
.dish-compact-btn--delete {
  padding: 0.2rem 0.35rem;
  background: #fff1f2;
  color: #e11d48;
}
.dish-compact-btn--delete:hover {
  background: #ffe4e6;
}

.menu-dish-photo-upload {
  display: block;
  width: 100%;
}
.menu-dish-photo-upload :deep(.el-upload) {
  display: block;
  width: 100%;
}
.menu-editor-input-el {
  width: 100%;
}
.menu-editor-textarea-el {
  width: 100%;
}
.dish-switch-el {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
</style>
