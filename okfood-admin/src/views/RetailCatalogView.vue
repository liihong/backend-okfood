<script setup>
import { ref, computed, onMounted } from 'vue'
import { Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout, dishImageDisplayUrl } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const storeId = ref(1)
const categories = ref([])
const products = ref([])
const loadingCat = ref(false)
const loadingProd = ref(false)
const filterCatId = ref(null)

const qs = computed(() => new URLSearchParams({ store_id: String(storeId.value || 1) }).toString())

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
  <div class="page-wrap">
    <div class="page-toolbar">
      <div class="field">
        <span class="label">门店 ID</span>
        <el-input-number v-model="storeId" :min="1" controls-position="right" @change="reloadAll" />
      </div>
    </div>

    <el-alert
      type="info"
      title="本期仅上架目录：不产生订单、不参加配送与小程展示；为多 SKU（多条商品记录）备货配置。"
      show-icon
      class="banner"
    />

    <el-card shadow="never" class="blk">
      <template #header>
        <div class="card-head">
          <span>商品分类（多 SKU 先建分类）</span>
          <el-button type="primary" size="small" @click="openCatCreate">
            <Plus :size="14" /> 新建分类
          </el-button>
        </div>
      </template>
      <el-table v-loading="loadingCat" :data="categories" size="small" empty-text="暂无分类">
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="sort_order" label="排序" width="80" align="center" />
        <el-table-column label="启用" width="72" align="center">
          <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openCatEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeCategory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="blk">
      <template #header>
        <div class="card-head">
          <span>普通商品 SKU</span>
          <div class="head-actions">
            <el-select
              v-model="filterCatId"
              placeholder="全部分类"
              clearable
              style="width: 140px"
              @change="fetchProducts"
            >
              <el-option
                v-for="c in categories"
                :key="c.id"
                :label="c.name"
                :value="c.id"
              />
            </el-select>
            <el-button type="primary" size="small" @click="openProdCreate">
              <Plus :size="14" /> 上架 SKU
            </el-button>
          </div>
        </div>
      </template>
      <el-table v-loading="loadingProd" :data="products" size="small" empty-text="暂无商品">
        <el-table-column label="封面" width="72" align="center">
          <template #default="{ row }">
            <img
              v-if="row.cover_image_url"
              :src="dishImageDisplayUrl(row.cover_image_url)"
              alt=""
              class="thumb"
            />
            <span v-else>—</span>
          </template>
        </el-table-column>
        <el-table-column prop="sku_code" label="SKU" width="100" />
        <el-table-column prop="title" label="标题" min-width="140" />
        <el-table-column label="分类" width="96">
          <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
        </el-table-column>
        <el-table-column prop="unit_price_yuan" label="售价(元)" width="88" align="right" />
        <el-table-column prop="list_price_yuan" label="划线价" width="88" align="right" />
        <el-table-column label="上架" width="72" align="center">
          <template #default="{ row }">{{ row.is_on_shelf ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="72" align="center" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openProdEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="removeProduct(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="catDialog" :title="catEditingId ? '编辑分类' : '新建分类'" width="400px">
      <el-form label-width="72px">
        <el-form-item label="名称">
          <el-input v-model="catForm.name" maxlength="128" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="catForm.sort_order" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="catForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog = false">取消</el-button>
        <el-button type="primary" :loading="catSaving" @click="saveCategory">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="prodDialog" :title="prodEditingId ? '编辑商品' : '上架商品'" width="520px">
      <el-form label-width="104px">
        <el-form-item label="所属分类">
          <el-select v-model="prodForm.category_id" clearable placeholder="可选" style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="SKU 编码">
          <el-input v-model="prodForm.sku_code" maxlength="64" placeholder="可空，便于备货统计" />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="prodForm.title" maxlength="256" />
        </el-form-item>
        <el-form-item label="副标题">
          <el-input v-model="prodForm.subtitle" maxlength="512" />
        </el-form-item>
        <el-form-item label="销售价">
          <el-input v-model="prodForm.unit_price_yuan" placeholder="元，如 99.00" />
        </el-form-item>
        <el-form-item label="划线价">
          <el-input v-model="prodForm.list_price_yuan" placeholder="可空" />
        </el-form-item>
        <el-form-item label="封面 URL">
          <el-input v-model="prodForm.cover_image_url" placeholder="/static/uploads/..." />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="prodForm.sort_order" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="上架">
          <el-switch v-model="prodForm.is_on_shelf" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="prodDialog = false">取消</el-button>
        <el-button type="primary" :loading="prodSaving" @click="saveProduct">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-wrap {
  padding: 0 24px 40px;
  max-width: 1200px;
}
.page-toolbar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  align-items: center;
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
.banner {
  margin-bottom: 16px;
}
.blk {
  margin-bottom: 20px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.head-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.thumb {
  width: 44px;
  height: 44px;
  object-fit: cover;
  border-radius: 8px;
  background: #f5f5f5;
}
</style>
