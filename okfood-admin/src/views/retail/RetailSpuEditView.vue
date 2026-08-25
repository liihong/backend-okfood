<script setup>
/**
 * 普通商品 SPU 新建/编辑页（全页布局，非弹窗）
 */
import { ElMessageBox } from 'element-plus'
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Camera, Plus } from 'lucide-vue-next'
import RetailRichTextEditor from '../../components/retail/RetailRichTextEditor.vue'
import { apiForm, apiJson, dishImageDisplayUrl } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

defineOptions({ name: 'RetailSpuEditView' })

const route = useRoute()
const router = useRouter()

const storeId = computed(() => {
  const raw = route.query.store_id
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : 1
})

const spuId = computed(() => {
  const raw = route.params.spuId
  if (raw == null || String(raw).trim() === '' || String(raw) === 'new') return null
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
})

const isEdit = computed(() => spuId.value != null)
const pageTitle = computed(() => (isEdit.value ? '编辑商品' : '新建商品'))

const loading = ref(false)
const saving = ref(false)
const coverUploading = ref(false)
const coverUploadKey = ref(0)
const categories = ref([])

const spuForm = ref({
  category_id: null,
  title: '',
  subtitle: '',
  detail_html: '',
  gallery_urls: [],
  purchase_notice: '',
  sort_order: 0,
  is_on_shelf: false,
})

const skus = ref([])

function emptySkuRow() {
  return {
    id: null,
    spec_label: '',
    sku_code: '',
    unit_price_yuan: '',
    list_price_yuan: '',
    stock_quantity: '',
    sort_order: 0,
    is_on_shelf: true,
  }
}

function resetForm() {
  spuForm.value = {
    category_id: null,
    title: '',
    subtitle: '',
    detail_html: '',
    gallery_urls: [],
    purchase_notice: '',
    sort_order: 0,
    is_on_shelf: false,
  }
  skus.value = [emptySkuRow()]
}

const coverUrl = computed(() => spuForm.value.gallery_urls?.[0] || '')

const extraGallery = computed(() => {
  const urls = spuForm.value.gallery_urls || []
  return urls.length > 1 ? urls.slice(1) : []
})

async function fetchCategories() {
  const sid = encodeURIComponent(String(storeId.value))
  const data = await apiJson(`/api/admin/catalog/retail-categories?store_id=${sid}`, {}, { auth: true })
  categories.value = Array.isArray(data) ? data : []
}

async function loadSpuDetail() {
  if (!spuId.value) {
    resetForm()
    return
  }
  loading.value = true
  try {
    const sid = encodeURIComponent(String(storeId.value))
    const data = await apiJson(`/api/admin/catalog/retail-spus/${spuId.value}?store_id=${sid}`, {}, { auth: true })
    spuForm.value = {
      category_id: data.category_id ?? null,
      title: data.title || '',
      subtitle: data.subtitle || '',
      detail_html: data.detail_html || '',
      gallery_urls: Array.isArray(data.gallery_urls) ? [...data.gallery_urls] : [],
      purchase_notice: data.purchase_notice || '',
      sort_order: Number(data.sort_order) || 0,
      is_on_shelf: Boolean(data.is_on_shelf),
    }
    const rows = Array.isArray(data.skus) ? data.skus : []
    skus.value = rows.length
      ? rows.map((s) => ({
          id: s.id,
          spec_label: s.spec_label || '',
          sku_code: s.sku_code || '',
          unit_price_yuan: s.unit_price_yuan ?? '',
          list_price_yuan: s.list_price_yuan ?? '',
          stock_quantity: s.stock_quantity != null ? String(s.stock_quantity) : '',
          sort_order: Number(s.sort_order) || 0,
          is_on_shelf: Boolean(s.is_on_shelf),
        }))
      : [emptySkuRow()]
  } catch (e) {
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    goBack()
  } finally {
    loading.value = false
  }
}

async function onCoverUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  coverUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      const rest = (spuForm.value.gallery_urls || []).slice(1)
      spuForm.value.gallery_urls = [url, ...rest]
      showToast('封面已上传', 'success')
    }
  } catch (e) {
    showToast(e instanceof Error ? e.message : '上传失败', 'error')
  } finally {
    coverUploading.value = false
    coverUploadKey.value += 1
  }
}

function removeCover() {
  const urls = [...(spuForm.value.gallery_urls || [])]
  if (!urls.length) return
  urls.shift()
  spuForm.value.gallery_urls = urls
}

function addGalleryUrl() {
  spuForm.value.gallery_urls = [...(spuForm.value.gallery_urls || []), '']
}

function removeGalleryUrl(index) {
  const next = [...(spuForm.value.gallery_urls || [])]
  // index 0 为封面，轮播从 1 起
  next.splice(index + 1, 1)
  spuForm.value.gallery_urls = next
}

function updateExtraGallery(index, value) {
  const next = [...(spuForm.value.gallery_urls || [])]
  if (!next.length && index === 0) {
    next.push(value)
  } else {
    next[index + 1] = value
  }
  spuForm.value.gallery_urls = next
}

function addSkuRow() {
  skus.value.push(emptySkuRow())
}

function removeSkuRow(index) {
  if (skus.value.length <= 1) {
    showToast('至少保留一个规格', 'error')
    return
  }
  skus.value.splice(index, 1)
}

function parsePrice(raw) {
  const s = String(raw || '').trim()
  if (!s) return null
  const n = Number(s)
  if (!Number.isFinite(n) || n < 0) return NaN
  return n.toFixed(2)
}

function goBack() {
  // 离开编辑页时清掉 KeepAlive 缓存，避免下次点「新建」带出上一份 SKU
  resetForm()
  router.push({
    name: 'menu-retail-catalog',
    query: { store_id: String(storeId.value) },
  })
}

async function handleSave() {
  const title = String(spuForm.value.title || '').trim()
  if (!title) {
    showToast('请填写商品名称', 'error')
    return
  }
  if (!spuForm.value.category_id) {
    showToast('请选择所属分类', 'error')
    return
  }

  saving.value = true
  const sid = encodeURIComponent(String(storeId.value))
  const gallery = (spuForm.value.gallery_urls || []).map((u) => String(u || '').trim()).filter(Boolean)

  const skuRows = []
  for (const [idx, row] of skus.value.entries()) {
    const price = parsePrice(row.unit_price_yuan)
    if (price == null || Number.isNaN(Number(price))) {
      showToast('请填写有效的销售价', 'error')
      saving.value = false
      return
    }
    const listRaw = String(row.list_price_yuan || '').trim()
    let list_py = null
    if (listRaw) {
      const lp = parsePrice(listRaw)
      if (Number.isNaN(Number(lp))) {
        showToast('划线价须为非负数字', 'error')
        saving.value = false
        return
      }
      list_py = lp
    }
    const skuPayload = {
      spec_label: String(row.spec_label || '').trim() || null,
      sku_code: String(row.sku_code || '').trim() || null,
      unit_price_yuan: price,
      list_price_yuan: list_py,
      sort_order: idx,
      is_on_shelf: Boolean(row.is_on_shelf),
    }
    if (row.id) skuPayload.id = row.id
    const stockRaw = String(row.stock_quantity || '').trim()
    if (stockRaw) {
      const sq = Math.floor(Number(stockRaw))
      if (!Number.isFinite(sq) || sq < 0) {
        showToast('库存须为非负整数', 'error')
        saving.value = false
        return
      }
      skuPayload.stock_quantity = sq
    } else {
      skuPayload.stock_quantity = null
    }
    skuRows.push(skuPayload)
  }

  const bundlePayload = {
    category_id: spuForm.value.category_id,
    title,
    subtitle: String(spuForm.value.subtitle || '').trim() || null,
    detail_html: spuForm.value.detail_html || null,
    gallery_urls: gallery.length ? gallery : null,
    purchase_notice: String(spuForm.value.purchase_notice || '').trim() || null,
    sort_order: Number(spuForm.value.sort_order) || 0,
    is_on_shelf: Boolean(spuForm.value.is_on_shelf),
    skus: skuRows,
  }

  try {
    if (spuId.value) {
      await apiJson(`/api/admin/catalog/retail-spus/${spuId.value}/bundle?store_id=${sid}`, {
        method: 'PUT',
        body: JSON.stringify(bundlePayload),
      }, { auth: true })
    } else {
      await apiJson(`/api/admin/catalog/retail-spus/bundle?store_id=${sid}`, {
        method: 'POST',
        body: JSON.stringify(bundlePayload),
      }, { auth: true })
    }
    showToast('已保存')
    goBack()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function deleteSku(row, index) {
  if (!row.id) {
    removeSkuRow(index)
    return
  }
  try {
    await ElMessageBox.confirm(
      '确定删除该规格 SKU？若已有订单记录将无法删除，请改为下架。',
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
  const sid = encodeURIComponent(String(storeId.value))
  try {
    await apiJson(`/api/admin/catalog/retail-products/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    skus.value.splice(index, 1)
    if (!skus.value.length) skus.value.push(emptySkuRow())
    showToast('SKU 已删除')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await fetchCategories()
    await loadSpuDetail()
  } finally {
    loading.value = false
  }
})

/** KeepAlive：商品 id 变了才重载，避免切走再回来把刚加的 SKU 清掉 */
watch(spuId, () => {
  void loadSpuDetail()
})

onActivated(() => {
  void fetchCategories()
})
</script>

<template>
  <div class="retail-spu-edit page-content-shell">
    <header class="retail-spu-edit__header">
      <div class="retail-spu-edit__header-row">
        <el-button link type="primary" class="retail-spu-edit__back" @click="goBack">
          <ArrowLeft :size="16" stroke-width="2" />
          返回
        </el-button>
        <h1 class="retail-spu-edit__title">{{ pageTitle }}</h1>
      </div>
    </header>

    <div v-loading="loading" class="retail-spu-edit__body">
      <!-- 基础信息 + 封面（紧凑横排） -->
      <section class="retail-spu-edit__card">
        <div class="retail-spu-edit__main-row">
          <div class="retail-spu-edit__media-compact">
            <el-upload
              :key="coverUploadKey"
              class="retail-spu-edit__cover-upload"
              :show-file-list="false"
              :auto-upload="false"
              accept="image/*"
              @change="onCoverUploadChange"
            >
              <div class="retail-spu-edit__cover-box" :class="{ 'retail-spu-edit__cover-box--empty': !coverUrl }">
                <img
                  v-if="coverUrl"
                  :src="dishImageDisplayUrl(coverUrl)"
                  alt=""
                  class="retail-spu-edit__cover-img"
                />
                <div v-else class="retail-spu-edit__cover-placeholder">
                  <Camera :size="24" stroke-width="1.5" />
                  <span>{{ coverUploading ? '上传中' : '封面' }}</span>
                </div>
                <div v-if="coverUrl" class="retail-spu-edit__cover-mask">更换</div>
              </div>
            </el-upload>
            <el-button v-if="coverUrl" type="danger" link size="small" @click="removeCover">移除</el-button>
            <el-button type="primary" link size="small" @click="addGalleryUrl">+ 轮播</el-button>
          </div>

          <el-form label-position="top" size="default" class="retail-spu-edit__form">
            <div class="retail-spu-edit__form-grid">
              <el-form-item label="所属分类" required class="span-2">
                <el-select v-model="spuForm.category_id" placeholder="请选择" style="width: 100%">
                  <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="商品名称" required class="span-2">
                <el-input v-model="spuForm.title" maxlength="256" placeholder="如：轻断食果蔬汁" />
              </el-form-item>
              <el-form-item label="副标题" class="span-2">
                <el-input v-model="spuForm.subtitle" maxlength="512" placeholder="卖点简述" />
              </el-form-item>
              <el-form-item label="排序">
                <el-input-number v-model="spuForm.sort_order" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
              <el-form-item label="上架">
                <el-switch v-model="spuForm.is_on_shelf" />
              </el-form-item>
              <el-form-item label="购买须知" class="span-2">
                <el-input
                  v-model="spuForm.purchase_notice"
                  type="textarea"
                  :rows="2"
                  placeholder="配送说明、保存方式等"
                />
              </el-form-item>
            </div>
          </el-form>
        </div>

        <div v-if="extraGallery.length" class="retail-spu-edit__gallery-list">
          <div v-for="(url, gi) in extraGallery" :key="gi" class="retail-spu-edit__gallery-row">
            <span class="retail-spu-edit__gallery-label">轮播{{ gi + 2 }}</span>
            <el-input
              :model-value="url"
              placeholder="https://"
              clearable
              size="small"
              @update:model-value="(v) => updateExtraGallery(gi, v)"
            />
            <el-button type="danger" link size="small" @click="removeGalleryUrl(gi)">删</el-button>
          </div>
        </div>
      </section>

      <!-- 规格 SKU（优先展示） -->
      <section class="retail-spu-edit__card retail-spu-edit__card--sku">
        <div class="retail-spu-edit__sku-head">
          <h3 class="retail-spu-edit__card-title">规格 SKU</h3>
          <el-button type="primary" size="small" @click="addSkuRow">
            <Plus :size="14" style="margin-right: 2px" />
            添加规格
          </el-button>
        </div>
        <el-table :data="skus" border size="small" class="retail-spu-edit__sku-table">
          <el-table-column label="规格名" min-width="100">
            <template #default="{ row }">
              <el-input v-model="row.spec_label" placeholder="如 1日体验" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="SKU编码" width="96">
            <template #default="{ row }">
              <el-input v-model="row.sku_code" size="small" placeholder="可选" />
            </template>
          </el-table-column>
          <el-table-column label="销售价" width="88">
            <template #default="{ row }">
              <el-input v-model="row.unit_price_yuan" size="small" placeholder="元" />
            </template>
          </el-table-column>
          <el-table-column label="划线价" width="88">
            <template #default="{ row }">
              <el-input v-model="row.list_price_yuan" size="small" placeholder="可空" />
            </template>
          </el-table-column>
          <el-table-column label="库存" width="76">
            <template #default="{ row }">
              <el-input v-model="row.stock_quantity" size="small" placeholder="不限" />
            </template>
          </el-table-column>
          <el-table-column label="上架" width="64" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_on_shelf" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="60" align="center" fixed="right">
            <template #default="{ row, $index }">
              <el-button type="danger" link size="small" @click="deleteSku(row, $index)">删</el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <!-- 详情介绍（置底）；等数据加载完再挂载，避免遮罩下初始化导致无法输入 -->
      <section class="retail-spu-edit__card">
        <h3 class="retail-spu-edit__card-title">详情介绍</h3>
        <RetailRichTextEditor v-if="!loading" v-model="spuForm.detail_html" />
      </section>
    </div>

    <footer class="retail-spu-edit__footer">
      <el-button @click="goBack">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存商品</el-button>
    </footer>
  </div>
</template>

<style scoped>
.retail-spu-edit {
  --retail-primary: #0d5c46;
  padding-bottom: 12px;
}

.retail-spu-edit__header {
  margin-bottom: 12px;
}

.retail-spu-edit__header-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.retail-spu-edit__back {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding-left: 0;
  font-weight: 600;
  flex-shrink: 0;
}

.retail-spu-edit__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
}

.retail-spu-edit__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.retail-spu-edit__card {
  background: #fff;
  border: 1px solid #eaedf1;
  border-radius: 10px;
  padding: 12px 16px;
}

.retail-spu-edit__card--sku {
  padding-bottom: 10px;
}

.retail-spu-edit__card-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.retail-spu-edit__main-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.retail-spu-edit__media-compact {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  width: 108px;
}

.retail-spu-edit__cover-upload {
  width: 108px;
}

.retail-spu-edit__cover-upload :deep(.el-upload) {
  width: 108px;
  display: block;
}

.retail-spu-edit__cover-box {
  position: relative;
  width: 108px;
  height: 108px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px dashed #cbd5e1;
  background: #f8fafc;
  cursor: pointer;
  transition: border-color 0.2s;
}

.retail-spu-edit__cover-box:hover {
  border-color: var(--retail-primary);
}

.retail-spu-edit__cover-box--empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.retail-spu-edit__cover-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.retail-spu-edit__cover-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #94a3b8;
  font-size: 12px;
  text-align: center;
}

.retail-spu-edit__cover-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.45);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  opacity: 0;
  transition: opacity 0.2s;
}

.retail-spu-edit__cover-box:hover .retail-spu-edit__cover-mask {
  opacity: 1;
}

.retail-spu-edit__form {
  flex: 1;
  min-width: 0;
}

.retail-spu-edit__form :deep(.el-form-item) {
  margin-bottom: 10px;
}

.retail-spu-edit__form :deep(.el-form-item__label) {
  padding-bottom: 2px;
  line-height: 1.2;
  font-size: 12px;
}

.retail-spu-edit__form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 12px;
}

.retail-spu-edit__form-grid .span-2 {
  grid-column: span 2;
}

@media (max-width: 720px) {
  .retail-spu-edit__main-row {
    flex-direction: column;
  }
  .retail-spu-edit__media-compact {
    flex-direction: row;
    width: 100%;
    justify-content: flex-start;
  }
  .retail-spu-edit__form-grid {
    grid-template-columns: 1fr;
  }
  .retail-spu-edit__form-grid .span-2 {
    grid-column: span 1;
  }
}

.retail-spu-edit__gallery-list {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.retail-spu-edit__gallery-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retail-spu-edit__gallery-label {
  flex-shrink: 0;
  width: 48px;
  font-size: 12px;
  color: #64748b;
}

.retail-spu-edit__sku-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.retail-spu-edit__footer {
  position: sticky;
  bottom: 0;
  z-index: 10;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
  padding: 10px 0;
  background: linear-gradient(180deg, rgba(248, 250, 252, 0) 0%, #f8fafc 30%);
}
</style>
