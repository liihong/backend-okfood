<script setup>
defineOptions({ name: 'RetailCatalogView' })
import { ref, computed, onMounted } from 'vue'
import { Info, LayoutGrid, List, Plus, X } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout, dishImageDisplayUrl } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const storeId = ref(1)
const categories = ref([])
const products = ref([])
const loadingCat = ref(false)
const loadingProd = ref(false)
const filterCatId = ref(null)
/** 顶部说明横条是否展示 */
const bannerVisible = ref(true)

const qs = computed(() => new URLSearchParams({ store_id: String(storeId.value || 1) }).toString())

function fmtPriceYuan(v) {
  if (v === null || v === undefined || String(v).trim() === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 无封面图时：拟物果蔬瓶渐变（仅展示） */
function juiceBottleClass(row) {
  const t = `${row.title || ''}${row.subtitle || ''}`
  if (t.includes('3日') || t.includes('液断') || t.includes('绿')) return 'retail-juice--green'
  if (t.includes('粉') || t.includes('蜜桃') || t.includes('莓')) return 'retail-juice--pink'
  return 'retail-juice--orange'
}

async function fetchCategories() {
  if (!adminAccessToken.value) return
  loadingCat.value = true
  try {
    const data = await apiJson(`/api/admin/catalog/retail-categories?${qs.value}`, {}, { auth: true })
    categories.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '分类加载失败', 'error')
  } finally {
    loadingCat.value = false
  }
}

async function fetchProducts() {
  if (!adminAccessToken.value) return
  loadingProd.value = true
  try {
    const p = new URLSearchParams({ store_id: String(storeId.value || 1) })
    if (filterCatId.value != null) p.set('category_id', String(filterCatId.value))
    const data = await apiJson(`/api/admin/catalog/retail-products?${p.toString()}`, {}, { auth: true })
    products.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '商品加载失败', 'error')
  } finally {
    loadingProd.value = false
  }
}

function categoryName(id) {
  if (id == null || id === '') return '—'
  const c = categories.value.find((x) => x.id === id)
  return c ? c.name : '—'
}

const catDialog = ref(false)
const catSaving = ref(false)
const catEditingId = ref(null)
const catForm = ref({ name: '', sort_order: 0, is_active: true })

function openCatCreate() {
  catEditingId.value = null
  catForm.value = { name: '', sort_order: 0, is_active: true }
  catDialog.value = true
}

function openCatEdit(row) {
  catEditingId.value = row.id
  catForm.value = { name: row.name, sort_order: row.sort_order, is_active: row.is_active }
  catDialog.value = true
}

async function saveCategory() {
  const name = String(catForm.value.name || '').trim()
  if (!name) {
    showToast('请输入分类名称', 'error')
    return
  }
  catSaving.value = true
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    if (catEditingId.value) {
      await apiJson(`/api/admin/catalog/retail-categories/${catEditingId.value}?store_id=${sid}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name,
          sort_order: Number(catForm.value.sort_order) || 0,
          is_active: Boolean(catForm.value.is_active),
        }),
      }, { auth: true })
    } else {
      await apiJson(`/api/admin/catalog/retail-categories?store_id=${sid}`, {
        method: 'POST',
        body: JSON.stringify({
          name,
          sort_order: Number(catForm.value.sort_order) || 0,
          is_active: Boolean(catForm.value.is_active),
        }),
      }, { auth: true })
    }
    showToast('已保存')
    catDialog.value = false
    await fetchCategories()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    catSaving.value = false
  }
}

async function removeCategory(row) {
  if (!window.confirm(`删除分类「${row.name}」？（下有商品时会失败）`)) return
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-categories/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchCategories()
    await fetchProducts()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

const prodDialog = ref(false)
const prodSaving = ref(false)
const prodEditingId = ref(null)
const prodForm = ref({
  category_id: null,
  sku_code: '',
  title: '',
  subtitle: '',
  unit_price_yuan: '',
  list_price_yuan: '',
  cover_image_url: '',
  sort_order: 0,
  is_on_shelf: false,
})

function openProdCreate() {
  prodEditingId.value = null
  prodForm.value = {
    category_id: null,
    sku_code: '',
    title: '',
    subtitle: '',
    unit_price_yuan: '',
    list_price_yuan: '',
    cover_image_url: '',
    sort_order: 0,
    is_on_shelf: false,
  }
  prodDialog.value = true
}

function openProdEdit(row) {
  prodEditingId.value = row.id
  prodForm.value = {
    category_id: row.category_id,
    sku_code: row.sku_code || '',
    title: row.title || '',
    subtitle: row.subtitle || '',
    unit_price_yuan: row.unit_price_yuan ?? '',
    list_price_yuan: row.list_price_yuan ?? '',
    cover_image_url: row.cover_image_url || '',
    sort_order: row.sort_order,
    is_on_shelf: row.is_on_shelf,
  }
  prodDialog.value = true
}

async function saveProduct() {
  const title = String(prodForm.value.title || '').trim()
  const priceRaw = String(prodForm.value.unit_price_yuan || '').trim()
  if (!title) {
    showToast('请填写商品名称', 'error')
    return
  }
  if (!priceRaw) {
    showToast('请填写销售价', 'error')
    return
  }
  const px = Number(priceRaw)
  if (!Number.isFinite(px) || px < 0) {
    showToast('销售价须为非负数字', 'error')
    return
  }
  const listRaw = String(prodForm.value.list_price_yuan || '').trim()
  let list_py = null
  if (listRaw) {
    const lp = Number(listRaw)
    if (!Number.isFinite(lp) || lp < 0) {
      showToast('划线价须为非负数字', 'error')
      return
    }
    list_py = lp.toFixed(2)
  }

  prodSaving.value = true
  const sid = encodeURIComponent(String(storeId.value || 1))
  const payload = {
    category_id: prodForm.value.category_id,
    sku_code: String(prodForm.value.sku_code || '').trim() || null,
    title,
    subtitle: String(prodForm.value.subtitle || '').trim() || null,
    unit_price_yuan: px.toFixed(2),
    list_price_yuan: list_py,
    cover_image_url: String(prodForm.value.cover_image_url || '').trim() || null,
    sort_order: Number(prodForm.value.sort_order) || 0,
    is_on_shelf: Boolean(prodForm.value.is_on_shelf),
  }
  try {
    if (prodEditingId.value) {
      const patch = {}
      patch.category_id = prodForm.value.category_id != null && prodForm.value.category_id !== '' ? prodForm.value.category_id : null
      patch.sku_code = payload.sku_code
      patch.title = payload.title
      patch.subtitle = payload.subtitle
      patch.unit_price_yuan = payload.unit_price_yuan
      patch.list_price_yuan = list_py === null ? null : payload.list_price_yuan
      patch.cover_image_url = payload.cover_image_url
      patch.sort_order = payload.sort_order
      patch.is_on_shelf = payload.is_on_shelf
      await apiJson(`/api/admin/catalog/retail-products/${prodEditingId.value}?store_id=${sid}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      }, { auth: true })
    } else {
      await apiJson(`/api/admin/catalog/retail-products?store_id=${sid}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      }, { auth: true })
    }
    showToast('已保存')
    prodDialog.value = false
    await fetchProducts()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    prodSaving.value = false
  }
}

async function removeProduct(row) {
  if (!window.confirm(`确定删除商品「${row.title}」？`)) return
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-products/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchProducts()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

async function reloadAll() {
  await fetchCategories()
  await fetchProducts()
}

onMounted(reloadAll)
</script>

<template>
  <div class="retail-page tab-content animate-up page-content-shell">
    <!-- 页眉 -->
    <header class="retail-header">
      <div class="page-heading">
        <h2 class="page-title">普通商品管理</h2>
        <p class="page-subtitle">Ordinary Product Configuration Panel</p>
      </div>
      <div class="retail-store-selector">
        <label for="retail-store-id">门店 ID</label>
        <el-input-number
          id="retail-store-id"
          v-model="storeId"
          :min="1"
          controls-position="right"
          class="retail-store-input"
          @change="reloadAll"
        />
      </div>
    </header>

    <!-- 提示横条 -->
    <div v-show="bannerVisible" class="retail-alert">
      <div class="retail-alert-content">
        <Info :size="18" stroke-width="2.5" aria-hidden="true" />
        <span>本期仅上架目录：不产生订单、不参加配送与小程序展示；为多 SKU（多条商品记录）备货配置。</span>
      </div>
      <button type="button" class="retail-alert-close" aria-label="关闭提示" @click="bannerVisible = false">
        <X :size="16" stroke-width="2.5" />
      </button>
    </div>

    <!-- 商品分类 -->
    <section class="retail-section">
      <div class="retail-section-bar">
        <h3 class="retail-section-title">
          <List :size="18" stroke-width="2.5" aria-hidden="true" />
          商品分类（多 SKU 先建分类）
        </h3>
        <button type="button" class="retail-btn-primary" @click="openCatCreate">
          <Plus :size="14" stroke-width="3" aria-hidden="true" />
          新建分类
        </button>
      </div>

      <div class="retail-main-card" v-loading="loadingCat">
        <div class="retail-table-scroll">
          <table class="retail-table">
            <thead>
              <tr>
                <th class="retail-th">名称</th>
                <th class="retail-th retail-th--center">排序</th>
                <th class="retail-th retail-th--center">启用</th>
                <th class="retail-th retail-th--actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!loadingCat && !categories.length">
                <td colspan="4" class="retail-empty">暂无分类</td>
              </tr>
              <tr v-for="row in categories" :key="row.id">
                <td class="retail-name-cell">{{ row.name }}</td>
                <td>
                  <div class="retail-cell-center">
                    <span class="retail-sort-readonly">{{ row.sort_order ?? 0 }}</span>
                  </div>
                </td>
                <td>
                  <div class="retail-cell-center">
                    <span
                      class="retail-switch"
                      :class="{ 'retail-switch--on': row.is_active }"
                      role="img"
                      :aria-label="row.is_active ? '已启用' : '未启用'"
                    >
                      <span class="retail-switch-knob" />
                    </span>
                  </div>
                </td>
                <td>
                  <div class="retail-actions">
                    <button type="button" class="retail-btn-action retail-btn-action--edit" @click="openCatEdit(row)">
                      编辑
                    </button>
                    <button type="button" class="retail-btn-action retail-btn-action--delete" @click="removeCategory(row)">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 普通商品 SKU -->
    <section class="retail-section">
      <div class="retail-section-bar">
        <h3 class="retail-section-title">
          <LayoutGrid :size="18" stroke-width="2.5" aria-hidden="true" />
          普通商品 SKU
        </h3>
        <div class="retail-section-actions">
          <el-select
            v-model="filterCatId"
            clearable
            placeholder="全部分类"
            class="retail-select-filter"
            @change="fetchProducts"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
          <button type="button" class="retail-btn-primary" @click="openProdCreate">
            <Plus :size="14" stroke-width="3" aria-hidden="true" />
            上架 SKU
          </button>
        </div>
      </div>

      <div class="retail-main-card" v-loading="loadingProd">
        <div class="retail-table-scroll">
          <table class="retail-table">
            <thead>
              <tr>
                <th class="retail-th retail-th--center">封面</th>
                <th class="retail-th">SKU 编码</th>
                <th class="retail-th">标题</th>
                <th class="retail-th">分类</th>
                <th class="retail-th">售价明细</th>
                <th class="retail-th retail-th--center">上架</th>
                <th class="retail-th retail-th--center">排序</th>
                <th class="retail-th retail-th--actions">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!loadingProd && !products.length">
                <td colspan="8" class="retail-empty">暂无商品</td>
              </tr>
              <tr v-for="row in products" :key="row.id">
                <td>
                  <div class="retail-cell-center">
                    <img
                      v-if="row.cover_image_url"
                      :src="dishImageDisplayUrl(row.cover_image_url)"
                      alt=""
                      class="retail-cover-img"
                    />
                    <div
                      v-else
                      class="retail-juice"
                      :class="juiceBottleClass(row)"
                      :title="row.title"
                    />
                  </div>
                </td>
                <td class="retail-sku-code">{{ row.sku_code || '—' }}</td>
                <td>
                  <div class="retail-identity">
                    <span class="retail-prod-title">{{ row.title || '—' }}</span>
                    <span v-if="row.subtitle" class="retail-prod-sub">{{ row.subtitle }}</span>
                  </div>
                </td>
                <td>
                  <span class="retail-cat-badge">{{ categoryName(row.category_id) }}</span>
                </td>
                <td>
                  <div class="retail-price-stack">
                    <span v-if="fmtPriceYuan(row.unit_price_yuan)" class="retail-sales-price">
                      ¥ {{ fmtPriceYuan(row.unit_price_yuan) }}
                    </span>
                    <span v-else class="retail-sales-price retail-sales-price--empty">—</span>
                    <span v-if="fmtPriceYuan(row.list_price_yuan)" class="retail-list-price">
                      划线 ¥ {{ fmtPriceYuan(row.list_price_yuan) }}
                    </span>
                  </div>
                </td>
                <td>
                  <div class="retail-cell-center">
                    <span
                      class="retail-switch"
                      :class="{ 'retail-switch--on': row.is_on_shelf }"
                      role="img"
                      :aria-label="row.is_on_shelf ? '已上架' : '未上架'"
                    >
                      <span class="retail-switch-knob" />
                    </span>
                  </div>
                </td>
                <td>
                  <div class="retail-cell-center">
                    <span class="retail-sort-readonly">{{ row.sort_order ?? 0 }}</span>
                  </div>
                </td>
                <td>
                  <div class="retail-actions">
                    <button type="button" class="retail-btn-action retail-btn-action--edit" @click="openProdEdit(row)">
                      编辑
                    </button>
                    <button type="button" class="retail-btn-action retail-btn-action--delete" @click="removeProduct(row)">
                      删除
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 新建/编辑分类 -->
    <el-dialog
      v-model="catDialog"
      class="retail-template-dialog retail-template-dialog--narrow"
      width="460px"
      align-center
      destroy-on-close
      :show-close="false"
    >
      <template #header>
        <div class="retail-modal-header">
          <h3 class="retail-modal-title">{{ catEditingId ? '编辑分类' : '新建分类' }}</h3>
          <button type="button" class="retail-modal-close" aria-label="关闭" @click="catDialog = false">
            <X :size="16" stroke-width="2.5" />
          </button>
        </div>
      </template>
      <div class="retail-modal-body">
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">名称</label>
          <el-input v-model="catForm.name" maxlength="128" class="retail-form-control" placeholder="如：果蔬汁" />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">排序</label>
          <el-input-number
            v-model="catForm.sort_order"
            :min="0"
            controls-position="right"
            class="retail-form-control retail-form-control--number"
          />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">启用</label>
          <el-switch v-model="catForm.is_active" class="retail-form-switch" />
        </div>
      </div>
      <template #footer>
        <div class="retail-modal-footer">
          <button type="button" class="retail-btn-modal retail-btn-modal--cancel" @click="catDialog = false">取消</button>
          <button
            type="button"
            class="retail-btn-modal retail-btn-modal--submit"
            :disabled="catSaving"
            @click="saveCategory"
          >
            {{ catSaving ? '提交中…' : '保存' }}
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- 上架/编辑商品 -->
    <el-dialog
      v-model="prodDialog"
      class="retail-template-dialog"
      width="580px"
      align-center
      destroy-on-close
      :show-close="false"
    >
      <template #header>
        <div class="retail-modal-header">
          <h3 class="retail-modal-title">{{ prodEditingId ? '编辑商品 SKU' : '上架商品' }}</h3>
          <button type="button" class="retail-modal-close" aria-label="关闭" @click="prodDialog = false">
            <X :size="16" stroke-width="2.5" />
          </button>
        </div>
      </template>
      <div class="retail-modal-body">
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">所属分类</label>
          <el-select v-model="prodForm.category_id" clearable placeholder="可选" class="retail-form-control">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">SKU 编码</label>
          <el-input
            v-model="prodForm.sku_code"
            maxlength="64"
            class="retail-form-control"
            placeholder="可空，便于备货统计"
          />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">标题</label>
          <el-input v-model="prodForm.title" maxlength="256" class="retail-form-control" placeholder="如：果蔬汁1日体验" />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">副标题</label>
          <el-input
            v-model="prodForm.subtitle"
            maxlength="512"
            class="retail-form-control"
            placeholder="如：新鲜榨取一日轻盈方案"
          />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">销售价</label>
          <el-input v-model="prodForm.unit_price_yuan" class="retail-form-control" placeholder="元，如 99.00" />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">划线价</label>
          <el-input v-model="prodForm.list_price_yuan" class="retail-form-control" placeholder="可空" />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">封面 URL</label>
          <div class="retail-upload-inline">
            <el-input v-model="prodForm.cover_image_url" class="retail-form-control" placeholder="/static/uploads/..." />
          </div>
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">排序</label>
          <el-input-number
            v-model="prodForm.sort_order"
            :min="0"
            controls-position="right"
            class="retail-form-control retail-form-control--number"
          />
        </div>
        <div class="retail-form-row retail-form-row--center">
          <label class="retail-form-label">上架</label>
          <el-switch v-model="prodForm.is_on_shelf" class="retail-form-switch" />
        </div>
      </div>
      <template #footer>
        <div class="retail-modal-footer">
          <button type="button" class="retail-btn-modal retail-btn-modal--cancel" @click="prodDialog = false">取消</button>
          <button
            type="button"
            class="retail-btn-modal retail-btn-modal--submit"
            :disabled="prodSaving"
            @click="saveProduct"
          >
            {{ prodSaving ? '提交中…' : prodEditingId ? '保存' : '保存' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.retail-page {
  --retail-primary: #0d5c46;
  --retail-primary-hover: #0a4635;
  --retail-border: #eaedf1;
  --retail-muted: #64748b;
  --retail-danger-bg: #fef2f2;
  --retail-danger-text: #ef4444;
  --retail-info-bg: #f0fdf4;
  --retail-info-text: #166534;
  --retail-info-border: #bbf7d0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 页眉白卡片（参考稿 header-section） */
.retail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
  padding: 24px 32px;
  background: #fff;
  border-radius: 28px;
  border: 1px solid var(--retail-border);
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.05);
}

.retail-store-selector {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f1f5f9;
  padding: 6px 14px;
  border-radius: 14px;
  border: 1px solid var(--retail-border);
}

.retail-store-selector label {
  font-size: 12px;
  font-weight: 800;
  color: var(--retail-muted);
  white-space: nowrap;
}

.retail-store-input {
  width: 120px;
}

.retail-store-input :deep(.el-input__wrapper) {
  background: transparent;
  box-shadow: none;
  padding: 0;
}

/* 提示横条 */
.retail-alert {
  background: var(--retail-info-bg);
  border: 1px solid var(--retail-info-border);
  border-radius: 20px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.retail-alert-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--retail-info-text);
  line-height: 1.5;
}

.retail-alert-content svg {
  flex-shrink: 0;
  color: var(--retail-primary);
  margin-top: 2px;
}

.retail-alert-close {
  background: transparent;
  border: none;
  color: var(--retail-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
  flex-shrink: 0;
}

.retail-alert-close:hover {
  opacity: 1;
}

.retail-section {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.retail-section-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.retail-section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
  color: #0f172a;
  display: flex;
  align-items: center;
  gap: 8px;
}

.retail-section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.retail-btn-primary {
  background: var(--retail-primary);
  color: #fff;
  border: none;
  padding: 10px 20px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 4px 12px -2px rgba(13, 92, 70, 0.2);
  transition: all 0.2s ease;
}

.retail-btn-primary:hover {
  background: var(--retail-primary-hover);
  transform: translateY(-1px);
}

.retail-select-filter {
  width: 140px;
}

.retail-select-filter :deep(.el-select__wrapper) {
  padding: 8px 16px;
  border-radius: 10px;
  border: 1px solid var(--retail-border);
  background: #fff;
  font-size: 12px;
  font-weight: 700;
  box-shadow: none;
}

.retail-main-card {
  background: #fff;
  border-radius: 28px;
  border: 1px solid var(--retail-border);
  padding: 24px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.04);
  min-height: 80px;
}

.retail-table-scroll {
  width: 100%;
  overflow-x: auto;
}

.retail-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.retail-th {
  background: #f8fafc;
  color: var(--retail-muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 14px 20px;
  border-bottom: 2px solid var(--retail-border);
  white-space: nowrap;
}

.retail-th--center {
  text-align: center;
}

.retail-th--actions {
  text-align: right;
}

.retail-table td {
  padding: 18px 20px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--retail-border);
  vertical-align: middle;
  color: #0f172a;
}

.retail-table tbody tr:hover {
  background: #f8fafc;
}

.retail-empty {
  text-align: center;
  color: #94a3b8;
  padding: 2.5rem 1rem !important;
}

.retail-name-cell {
  font-weight: 800;
}

.retail-cell-center {
  display: flex;
  justify-content: center;
}

/* 拟物果蔬瓶封面 */
.retail-juice {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  position: relative;
  overflow: hidden;
  box-shadow: 0 4px 10px -2px rgba(15, 23, 42, 0.1);
}

.retail-juice::after {
  content: '';
  position: absolute;
  width: 14px;
  height: 24px;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.5);
  right: 8px;
  bottom: 6px;
}

.retail-juice--orange {
  background: linear-gradient(135deg, #f97316 0%, #facc15 100%);
}

.retail-juice--green {
  background: linear-gradient(135deg, #10b981 0%, #34d399 100%);
}

.retail-juice--pink {
  background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%);
}

.retail-cover-img {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 12px;
  background: #f5f5f5;
}

.retail-sku-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  color: var(--retail-muted);
}

.retail-identity {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.retail-prod-title {
  font-weight: 800;
  font-size: 14px;
}

.retail-prod-sub {
  font-size: 11px;
  font-weight: 500;
  color: var(--retail-muted);
}

.retail-cat-badge {
  background: #e0f2fe;
  color: #0369a1;
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
  display: inline-block;
}

.retail-price-stack {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.retail-sales-price {
  font-size: 14px;
  font-weight: 800;
  color: var(--retail-primary);
  font-family: ui-monospace, monospace;
}

.retail-sales-price--empty {
  color: var(--retail-muted);
  font-weight: 700;
}

.retail-list-price {
  font-size: 11px;
  color: var(--retail-muted);
  text-decoration: line-through;
  font-family: ui-monospace, monospace;
}

.retail-sort-readonly {
  display: inline-block;
  min-width: 60px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--retail-border);
  background: #f8fafc;
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.retail-switch {
  display: inline-block;
  position: relative;
  width: 44px;
  height: 24px;
  background: #cbd5e1;
  border-radius: 34px;
  flex-shrink: 0;
}

.retail-switch--on {
  background: var(--retail-primary);
}

.retail-switch-knob {
  position: absolute;
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
  transition: transform 0.3s;
}

.retail-switch--on .retail-switch-knob {
  transform: translateX(20px);
}

.retail-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.retail-btn-action {
  border: none;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s;
}

.retail-btn-action--edit {
  background: #f1f5f9;
  color: #0f172a;
}

.retail-btn-action--edit:hover {
  background: #e2e8f0;
}

.retail-btn-action--delete {
  background: var(--retail-danger-bg);
  color: var(--retail-danger-text);
}

.retail-btn-action--delete:hover {
  background: #fecaca;
}

/* ── 弹窗（与会员卡模版弹窗同款结构） ── */
.retail-template-dialog :deep(.el-dialog) {
  border-radius: 24px;
  overflow: hidden;
  border: 1px solid var(--retail-border);
  box-shadow: 0 24px 64px -12px rgba(15, 23, 42, 0.25);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  margin: 0;
}

.retail-template-dialog :deep(.el-dialog__header),
.retail-template-dialog :deep(.el-dialog__body),
.retail-template-dialog :deep(.el-dialog__footer) {
  padding: 0;
  margin: 0;
}

.retail-template-dialog :deep(.el-dialog__body) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.retail-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--retail-border);
}

.retail-modal-title {
  margin: 0;
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}

.retail-modal-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: #f1f5f9;
  color: var(--retail-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.retail-modal-close:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.retail-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: calc(90vh - 120px);
}

.retail-form-row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.retail-form-row--center {
  align-items: center;
}

.retail-form-label {
  text-align: right;
  font-size: 13px;
  font-weight: 800;
  color: #0f172a;
  padding-top: 8px;
}

.retail-form-row--center .retail-form-label {
  padding-top: 0;
}

.retail-form-control {
  width: 100%;
}

.retail-form-control :deep(.el-input__wrapper) {
  padding: 12px 16px;
  border-radius: 10px;
  box-shadow: 0 0 0 1px var(--retail-border) inset;
  background: #fff;
}

.retail-form-control :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--retail-primary) inset,
    0 0 0 3px rgba(13, 92, 70, 0.08);
}

.retail-form-control :deep(.el-input__inner) {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.retail-form-control--number :deep(.el-input__wrapper) {
  padding: 8px 12px;
}

.retail-upload-inline {
  width: 100%;
  min-width: 0;
}

.retail-form-switch.is-checked :deep(.el-switch__core) {
  background-color: var(--retail-primary);
  border-color: var(--retail-primary);
}

.retail-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 14px 20px;
  border-top: 1px solid var(--retail-border);
  background: #f8fafc;
  border-bottom-left-radius: 24px;
  border-bottom-right-radius: 24px;
}

.retail-btn-modal {
  padding: 10px 24px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.retail-btn-modal--cancel {
  background: #fff;
  color: var(--retail-muted);
  border: 1px solid var(--retail-border);
}

.retail-btn-modal--cancel:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.retail-btn-modal--submit {
  background: var(--retail-primary);
  color: #fff;
  box-shadow: 0 4px 12px -2px rgba(13, 92, 70, 0.25);
}

.retail-btn-modal--submit:hover:not(:disabled) {
  background: var(--retail-primary-hover);
}

.retail-btn-modal--submit:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
</style>
