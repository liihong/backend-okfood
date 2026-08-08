<script setup>
defineOptions({ name: 'RetailCatalogView' })
import { ref, computed, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { LayoutGrid, List, Plus } from 'lucide-vue-next'
import { apiJson, adminAccessToken, handleAdminLogout, dishImageDisplayUrl } from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const router = useRouter()
const storeId = ref(1)
const categories = ref([])
const spus = ref([])
const loadingCat = ref(false)
const loadingSpu = ref(false)
const filterCatId = ref(null)

const qs = computed(() => new URLSearchParams({ store_id: String(storeId.value || 1) }).toString())

function fmtPriceYuan(v) {
  if (v === null || v === undefined || String(v).trim() === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function priceRangeText(row) {
  const lo = fmtPriceYuan(row.price_min_yuan)
  const hi = fmtPriceYuan(row.price_max_yuan)
  if (lo == null) return '—'
  if (hi == null || hi === lo) return `¥${lo}`
  return `¥${lo} ~ ¥${hi}`
}

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

async function fetchSpus() {
  if (!adminAccessToken.value) return
  loadingSpu.value = true
  try {
    const p = new URLSearchParams({ store_id: String(storeId.value || 1) })
    if (filterCatId.value != null) p.set('category_id', String(filterCatId.value))
    const data = await apiJson(`/api/admin/catalog/retail-spus?${p.toString()}`, {}, { auth: true })
    spus.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '商品加载失败', 'error')
  } finally {
    loadingSpu.value = false
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
  try {
    await ElMessageBox.confirm(
      `确定删除分类「${row.name}」？若该分类下仍有商品，将无法删除。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-categories/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchCategories()
    await fetchSpus()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

function openSpuCreate() {
  router.push({
    name: 'menu-retail-spu-new',
    query: { store_id: String(storeId.value || 1) },
  })
}

function openSpuEdit(row) {
  router.push({
    name: 'menu-retail-spu-edit',
    params: { spuId: String(row.id) },
    query: { store_id: String(storeId.value || 1) },
  })
}

async function removeSpu(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除商品「${row.title}」？需先删除全部规格 SKU。`,
      '删除确认',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-spus/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchSpus()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

async function toggleSpuShelf(row) {
  const sid = encodeURIComponent(String(storeId.value || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-spus/${row.id}?store_id=${sid}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_on_shelf: !row.is_on_shelf }),
    }, { auth: true })
    row.is_on_shelf = !row.is_on_shelf
  } catch (e) {
    showToast(e instanceof Error ? e.message : '操作失败', 'error')
  }
}

async function reloadAll() {
  await Promise.all([fetchCategories(), fetchSpus()])
}

onMounted(reloadAll)
onActivated(() => {
  void fetchSpus()
})
</script>

<template>
  <div class="retail-page tab-content animate-up page-content-shell">
    <!-- 商品分类 -->
    <section class="retail-section">
      <div class="retail-section-bar">
        <h3 class="retail-section-title">
          <List :size="18" stroke-width="2.5" aria-hidden="true" />
          商品分类
        </h3>
        <el-button type="primary" @click="openCatCreate">
          <Plus :size="14" stroke-width="3" aria-hidden="true" style="margin-right:4px" />
          新建分类
        </el-button>
      </div>

      <div class="retail-main-card" v-loading="loadingCat">
        <el-table :data="categories" border stripe empty-text="暂无分类">
          <el-table-column prop="name" label="名称" min-width="160" />
          <el-table-column prop="sort_order" label="排序" width="80" align="center" />
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
                {{ row.is_active ? '是' : '否' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="140" align="center">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openCatEdit(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click="removeCategory(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- 商品 SPU 列表 -->
    <section class="retail-section">
      <div class="retail-section-bar">
        <h3 class="retail-section-title">
          <LayoutGrid :size="18" stroke-width="2.5" aria-hidden="true" />
          普通商品
        </h3>
        <div class="retail-section-actions">
          <el-select
            v-model="filterCatId"
            clearable
            placeholder="全部分类"
            class="retail-select-filter"
            @change="fetchSpus"
          >
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
          <el-button type="primary" @click="openSpuCreate">
            <Plus :size="14" stroke-width="3" aria-hidden="true" style="margin-right:4px" />
            新建商品
          </el-button>
        </div>
      </div>

      <div class="retail-main-card" v-loading="loadingSpu">
        <el-table :data="spus" border stripe empty-text="暂无商品">
          <el-table-column label="封面" width="72" align="center">
            <template #default="{ row }">
              <img
                v-if="row.cover_image_url"
                :src="dishImageDisplayUrl(row.cover_image_url)"
                alt=""
                class="retail-thumb"
              />
              <div v-else class="retail-juice retail-juice--placeholder" :class="juiceBottleClass(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="title" label="商品名称" min-width="140" />
          <el-table-column label="分类" width="100">
            <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
          </el-table-column>
          <el-table-column label="规格数" width="72" align="center">
            <template #default="{ row }">{{ row.sku_count ?? 0 }}</template>
          </el-table-column>
          <el-table-column label="价格" width="120">
            <template #default="{ row }">{{ priceRangeText(row) }}</template>
          </el-table-column>
          <el-table-column label="上架" width="80" align="center">
            <template #default="{ row }">
              <el-switch :model-value="row.is_on_shelf" @change="toggleSpuShelf(row)" />
            </template>
          </el-table-column>
          <el-table-column prop="sort_order" label="排序" width="72" align="center" />
          <el-table-column label="操作" width="140" align="center" fixed="right">
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openSpuEdit(row)">编辑</el-button>
              <el-button type="danger" link size="small" @click="removeSpu(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </section>

    <!-- 分类弹窗 -->
    <el-dialog v-model="catDialog" title="商品分类" width="420px" destroy-on-close>
      <el-form label-width="80px">
        <el-form-item label="名称" required>
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
  </div>
</template>

<style scoped>
.retail-page {
  --retail-primary: #0d5c46;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.retail-section-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.retail-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.retail-section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.retail-select-filter {
  width: 160px;
}
.retail-main-card {
  background: #fff;
  border-radius: 12px;
  border: 1px solid #eaedf1;
  padding: 12px;
}
.retail-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 8px;
}
.retail-juice--placeholder {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  margin: 0 auto;
}
.retail-juice--orange {
  background: linear-gradient(145deg, #fdba74, #ea580c);
}
.retail-juice--green {
  background: linear-gradient(145deg, #86efac, #16a34a);
}
.retail-juice--pink {
  background: linear-gradient(145deg, #f9a8d4, #db2777);
}
</style>
