<script setup>
/**
 * 普通商品新建 / 编辑：从商品列表右侧滑出，不切换路由。
 * 字段与保存接口与原全页表单一致。
 */
import { ElMessageBox } from 'element-plus'
import { computed, ref, watch } from 'vue'
import { Camera, Plus } from 'lucide-vue-next'
import RetailRichTextEditor from '../../components/retail/RetailRichTextEditor.vue'
import { apiForm, apiJson, dishImageDisplayUrl } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

defineOptions({ name: 'RetailSpuEditView' })

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  storeId: { type: Number, default: 1 },
  /** 为空表示新建 */
  spuId: { default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => {
  const n = Number(props.spuId)
  return Number.isFinite(n) && n > 0
})
const pageTitle = computed(() => (isEdit.value ? '编辑商品' : '新建商品'))
const pageSubtitle = computed(() =>
  isEdit.value ? '改完分类、规格和详情后保存，列表会一起更新' : '填写分类、封面、规格和详情，保存后出现在商品列表',
)

/** 关闭或再次打开时作废进行中的加载，避免旧数据写回 */
let loadToken = 0

const open = computed({
  get: () => props.modelValue,
    set: (v) => {
      if (!v) loadToken += 1
      emit('update:modelValue', Boolean(v))
    },
})

const loading = ref(false)
const saving = ref(false)
const coverUploading = ref(false)
const coverUploadKey = ref(0)
/** 正在上传的轮播下标（extraGallery 的 index），null 表示空闲 */
const galleryUploadingIndex = ref(null)
/** 用于上传后重置 el-upload，以便可重复选择同一文件 */
const galleryUploadKeys = ref({})
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
/** 点击封面时用同一张图打开预览，避免和「更换」上传抢点击 */
const coverPreviewList = computed(() => {
  const url = dishImageDisplayUrl(coverUrl.value)
  return url ? [url] : []
})

const extraGallery = computed(() => {
  const urls = spuForm.value.gallery_urls || []
  return urls.length > 1 ? urls.slice(1) : []
})

async function fetchCategories() {
  const sid = encodeURIComponent(String(props.storeId || 1))
  const data = await apiJson(`/api/admin/catalog/retail-categories?store_id=${sid}`, {}, { auth: true })
  categories.value = Array.isArray(data) ? data : []
}

async function loadSpuDetail() {
  if (!isEdit.value) {
    resetForm()
    return
  }
  const sid = encodeURIComponent(String(props.storeId || 1))
  const data = await apiJson(`/api/admin/catalog/retail-spus/${props.spuId}?store_id=${sid}`, {}, { auth: true })
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
}

/** 抽屉打开或切换商品时拉分类和详情 */
async function openAndLoad() {
  const token = ++loadToken
  loading.value = true
  resetForm()
  try {
    await fetchCategories()
    if (token !== loadToken) return
    await loadSpuDetail()
  } catch (e) {
    if (token !== loadToken) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    open.value = false
  } finally {
    if (token === loadToken) loading.value = false
  }
}

watch(
  () => (props.modelValue ? `${props.storeId}:${props.spuId ?? 'new'}` : ''),
  (key) => {
    if (!key) return
    void openAndLoad()
  },
)

/** 上传图片到 OSS，成功返回 url */
async function uploadImageFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  const data = await apiForm('/api/admin/upload', fd, { auth: true })
  return data && typeof data.url === 'string' ? data.url.trim() : ''
}

async function onCoverUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  coverUploading.value = true
  try {
    const url = await uploadImageFile(file)
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

async function onGalleryUploadChange(index, uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  galleryUploadingIndex.value = index
  try {
    const url = await uploadImageFile(file)
    if (url) {
      updateExtraGallery(index, url)
      showToast('轮播图已上传', 'success')
    }
  } catch (e) {
    showToast(e instanceof Error ? e.message : '上传失败', 'error')
  } finally {
    galleryUploadingIndex.value = null
    galleryUploadKeys.value = {
      ...galleryUploadKeys.value,
      [index]: (galleryUploadKeys.value[index] || 0) + 1,
    }
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

function closeDrawer() {
  open.value = false
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
  const sid = encodeURIComponent(String(props.storeId || 1))
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
    if (isEdit.value) {
      await apiJson(`/api/admin/catalog/retail-spus/${props.spuId}/bundle?store_id=${sid}`, {
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
    emit('saved')
    closeDrawer()
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
        customClass: 'okfood-message-box',
      },
    )
  } catch {
    return
  }
  const sid = encodeURIComponent(String(props.storeId || 1))
  try {
    await apiJson(`/api/admin/catalog/retail-products/${row.id}?store_id=${sid}`, { method: 'DELETE' }, { auth: true })
    skus.value.splice(index, 1)
    if (!skus.value.length) skus.value.push(emptySkuRow())
    showToast('SKU 已删除')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

function onBeforeClose(done) {
  if (saving.value) return
  done()
}
</script>

<template>
  <el-drawer
    v-model="open"
    direction="rtl"
    size="min(960px, 96vw)"
    append-to-body
    destroy-on-close
    :close-on-click-modal="true"
    :before-close="onBeforeClose"
    class="retail-spu-drawer"
  >
    <template #header>
      <div class="retail-spu-drawer__head">
        <h3 class="retail-spu-drawer__title">{{ pageTitle }}</h3>
        <p class="retail-spu-drawer__subtitle">{{ pageSubtitle }}</p>
      </div>
    </template>

    <div v-loading="loading" class="retail-spu-drawer__body">
      <el-card shadow="never" class="retail-spu-drawer__card">
        <div class="retail-spu-drawer__main">
          <div class="retail-spu-drawer__media">
            <div
              class="retail-spu-drawer__cover"
              :class="{ 'retail-spu-drawer__cover--empty': !coverUrl, 'retail-spu-drawer__cover--has': !!coverUrl }"
            >
              <el-image
                v-if="coverUrl"
                class="retail-spu-drawer__cover-img"
                :src="dishImageDisplayUrl(coverUrl)"
                :preview-src-list="coverPreviewList"
                fit="cover"
                preview-teleported
                hide-on-click-modal
                alt="商品封面"
              >
                <template #error>
                  <div class="retail-spu-drawer__cover-placeholder">图片加载失败</div>
                </template>
              </el-image>
              <el-upload
                v-else
                :key="coverUploadKey"
                class="retail-spu-drawer__cover-upload"
                :show-file-list="false"
                :auto-upload="false"
                accept="image/*"
                @change="onCoverUploadChange"
              >
                <div class="retail-spu-drawer__cover-placeholder">
                  <Camera :size="28" stroke-width="1.75" />
                  <span>{{ coverUploading ? '上传中' : '封面' }}</span>
                </div>
              </el-upload>
              <!-- 遮罩不拦截点击，由 el-image 打开大图 -->
              <div v-if="coverUrl" class="retail-spu-drawer__cover-mask" aria-hidden="true">点击查看大图</div>
            </div>
            <div class="retail-spu-drawer__media-actions">
              <el-upload
                v-if="coverUrl"
                :key="`replace-${coverUploadKey}`"
                class="retail-spu-drawer__replace"
                :show-file-list="false"
                :auto-upload="false"
                accept="image/*"
                @change="onCoverUploadChange"
              >
                <el-button type="primary" link size="small">更换</el-button>
              </el-upload>
              <el-button v-if="coverUrl" type="danger" link size="small" @click="removeCover">移除</el-button>
              <el-button type="primary" link size="small" @click="addGalleryUrl">添加轮播</el-button>
            </div>
          </div>

          <el-form label-position="top" class="retail-spu-drawer__form">
            <div class="retail-spu-drawer__grid">
              <el-form-item label="所属分类" required>
                <el-select v-model="spuForm.category_id" placeholder="请选择" style="width: 100%">
                  <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="排序">
                <el-input-number v-model="spuForm.sort_order" :min="0" controls-position="right" style="width: 100%" />
              </el-form-item>
              <el-form-item label="上架">
                <div class="retail-spu-drawer__switch">
                  <el-switch v-model="spuForm.is_on_shelf" />
                  <span>{{ spuForm.is_on_shelf ? '上架' : '下架' }}</span>
                </div>
              </el-form-item>
              <el-form-item label="商品名称" required class="span-3">
                <el-input v-model="spuForm.title" maxlength="256" placeholder="如：轻断食果蔬汁" clearable />
              </el-form-item>
              <el-form-item label="副标题" class="span-3">
                <el-input v-model="spuForm.subtitle" maxlength="512" placeholder="卖点简述" clearable />
              </el-form-item>
              <el-form-item label="购买须知" class="span-3">
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

        <div v-if="extraGallery.length" class="retail-spu-drawer__gallery">
          <div v-for="(url, gi) in extraGallery" :key="gi" class="retail-spu-drawer__gallery-item">
            <el-upload
              :key="`g-${gi}-${galleryUploadKeys[gi] || 0}`"
              class="retail-spu-drawer__gallery-upload"
              :show-file-list="false"
              :auto-upload="false"
              :disabled="galleryUploadingIndex === gi"
              accept="image/*"
              @change="(f) => onGalleryUploadChange(gi, f)"
            >
              <div class="retail-spu-drawer__gallery-box" :class="{ 'retail-spu-drawer__gallery-box--empty': !url }">
                <img v-if="url" :src="dishImageDisplayUrl(url)" alt="" class="retail-spu-drawer__gallery-img" />
                <div v-else class="retail-spu-drawer__cover-placeholder">
                  <Camera :size="16" stroke-width="1.75" />
                  <span>{{ galleryUploadingIndex === gi ? '上传中' : '上传' }}</span>
                </div>
                <div v-if="url" class="retail-spu-drawer__cover-mask">更换</div>
              </div>
            </el-upload>
            <div class="retail-spu-drawer__gallery-meta">
              <span>轮播 {{ gi + 2 }}</span>
              <el-button type="danger" link size="small" @click="removeGalleryUrl(gi)">删除</el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="never" class="retail-spu-drawer__card">
        <div class="retail-spu-drawer__sku-head">
          <h3 class="retail-spu-drawer__card-title">规格 SKU</h3>
          <el-button type="primary" round size="small" @click="addSkuRow">
            <Plus :size="14" stroke-width="2.5" />
            添加规格
          </el-button>
        </div>
        <el-table :data="skus" border size="small" class="retail-spu-drawer__sku-table">
          <el-table-column label="规格名" min-width="120">
            <template #default="{ row }">
              <el-input v-model="row.spec_label" placeholder="如 1日体验" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="SKU编码" width="110">
            <template #default="{ row }">
              <el-input v-model="row.sku_code" size="small" placeholder="可选" />
            </template>
          </el-table-column>
          <el-table-column label="销售价" width="96">
            <template #default="{ row }">
              <el-input v-model="row.unit_price_yuan" size="small" placeholder="元" />
            </template>
          </el-table-column>
          <el-table-column label="划线价" width="96">
            <template #default="{ row }">
              <el-input v-model="row.list_price_yuan" size="small" placeholder="可空" />
            </template>
          </el-table-column>
          <el-table-column label="库存" width="84">
            <template #default="{ row }">
              <el-input v-model="row.stock_quantity" size="small" placeholder="不限" />
            </template>
          </el-table-column>
          <el-table-column label="上架" width="72" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.is_on_shelf" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="72" align="center" fixed="right">
            <template #default="{ row, $index }">
              <el-button type="danger" link size="small" @click="deleteSku(row, $index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never" class="retail-spu-drawer__card">
        <h3 class="retail-spu-drawer__card-title">详情介绍</h3>
        <RetailRichTextEditor v-if="open && !loading" v-model="spuForm.detail_html" height="260px" />
      </el-card>
    </div>

    <template #footer>
      <div class="retail-spu-drawer__footer">
        <el-button round :disabled="saving" @click="closeDrawer">取消</el-button>
        <el-button type="primary" round :loading="saving" @click="handleSave">保存商品</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.retail-spu-drawer__head {
  min-width: 0;
  padding-right: 12px;
}

.retail-spu-drawer__title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.3;
  color: #1d1f21;
}

.retail-spu-drawer__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.45;
  font-weight: 500;
  color: #5c6670;
}

.retail-spu-drawer__body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 240px;
}

.retail-spu-drawer__card {
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.retail-spu-drawer__card :deep(.el-card__body) {
  padding: 16px;
}

.retail-spu-drawer__card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #1d1f21;
}

.retail-spu-drawer__main {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.retail-spu-drawer__media {
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.retail-spu-drawer__cover-upload,
.retail-spu-drawer__cover-upload :deep(.el-upload) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.retail-spu-drawer__cover,
.retail-spu-drawer__gallery-box {
  position: relative;
  overflow: hidden;
  border: 1px dashed rgba(15, 23, 42, 0.16);
  background: #f8fafc;
  cursor: pointer;
}

.retail-spu-drawer__cover {
  width: 240px;
  height: 240px;
  border-radius: 18px;
}

.retail-spu-drawer__cover--has {
  cursor: zoom-in;
}

.retail-spu-drawer__cover--empty,
.retail-spu-drawer__gallery-box--empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.retail-spu-drawer__cover:hover,
.retail-spu-drawer__gallery-box:hover {
  border-color: var(--el-color-primary);
}

.retail-spu-drawer__cover-img {
  width: 100%;
  height: 100%;
}

.retail-spu-drawer__cover-img :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.retail-spu-drawer__gallery-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.retail-spu-drawer__cover-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #94a3b8;
  font-size: 12px;
  font-weight: 650;
}

.retail-spu-drawer__cover-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.42);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.retail-spu-drawer__cover .retail-spu-drawer__cover-mask {
  pointer-events: none;
  align-items: flex-end;
  padding-bottom: 14px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0) 42%, rgba(15, 23, 42, 0.48) 100%);
}

.retail-spu-drawer__cover:hover .retail-spu-drawer__cover-mask,
.retail-spu-drawer__gallery-box:hover .retail-spu-drawer__cover-mask {
  opacity: 1;
}

.retail-spu-drawer__media-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 2px 8px;
  width: 100%;
}

.retail-spu-drawer__replace :deep(.el-upload) {
  display: inline-flex;
}

.retail-spu-drawer__form {
  flex: 1;
  min-width: 0;
}

.retail-spu-drawer__form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.retail-spu-drawer__form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  line-height: 1.2;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}

.retail-spu-drawer__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(120px, 0.7fr) minmax(120px, 0.7fr);
  gap: 0 12px;
}

.retail-spu-drawer__grid .span-3 {
  grid-column: 1 / -1;
}

.retail-spu-drawer__switch {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  color: #334155;
  font-size: 13px;
  font-weight: 650;
}

.retail-spu-drawer__gallery {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 4px;
  padding-top: 12px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.retail-spu-drawer__gallery-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.retail-spu-drawer__gallery-upload,
.retail-spu-drawer__gallery-upload :deep(.el-upload) {
  width: 76px;
  display: block;
}

.retail-spu-drawer__gallery-box {
  width: 76px;
  height: 76px;
  border-radius: 14px;
}

.retail-spu-drawer__gallery-meta {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  color: #64748b;
}

.retail-spu-drawer__sku-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.retail-spu-drawer__sku-head .el-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.retail-spu-drawer__card-title + :deep(.retail-rich-editor) {
  margin-top: 10px;
}

.retail-spu-drawer__card :deep(.retail-rich-editor) {
  border-radius: 14px;
  border-color: rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.retail-spu-drawer__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 760px) {
  .retail-spu-drawer__main {
    flex-direction: column;
  }

  .retail-spu-drawer__media {
    flex-direction: row;
    flex-basis: auto;
    width: 100%;
    justify-content: flex-start;
    align-items: flex-end;
  }

  .retail-spu-drawer__cover {
    width: 180px;
    height: 180px;
  }

  .retail-spu-drawer__grid {
    grid-template-columns: 1fr;
  }

  .retail-spu-drawer__grid .span-3 {
    grid-column: auto;
  }
}
</style>

<style>
/* 抽屉节点 teleport 到 body，且 class 落在 .el-drawer 自身，不能用后代选择器 */
.retail-spu-drawer.el-drawer {
  border-top-left-radius: 22px;
  border-bottom-left-radius: 22px;
  overflow: hidden;
  background: #f7fafb;
}

.retail-spu-drawer .el-drawer__header {
  align-items: flex-start;
  margin-bottom: 0;
  padding: 16px 20px 14px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(255, 255, 255, 0.92);
}

.retail-spu-drawer .el-drawer__body {
  padding: 14px 16px 18px;
  background: #f7fafb;
}

.retail-spu-drawer .el-drawer__footer {
  padding: 12px 20px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  background: rgba(255, 255, 255, 0.94);
}
</style>
