<script setup>
defineOptions({ name: 'PurchaseNotesView' })

import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Search } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
import AdminTable from '../../components/AdminTable.vue'
import StatRollNumber from '../../components/StatRollNumber.vue'
import { handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import {
  createPurchaseNote,
  deletePurchaseNote,
  listPurchaseNotes,
  patchPurchaseNote,
} from '../../api/packaging/purchaseNotes.js'

const CATEGORIES = [
  { value: 'ingredient', label: '食材类' },
  { value: 'consumable', label: '耗材类' },
]
const METHODS = [
  { value: 'link', label: '采购链接', short: '链接' },
  { value: 'wechat', label: '微信', short: '微信' },
  { value: 'phone', label: '手机号', short: '手机号' },
  { value: 'other', label: '其他', short: '其他' },
]

const loading = ref(false)
const loaded = ref(false)
const saving = ref(false)
const rows = ref([])
const keyword = ref('')
const category = ref('')
const method = ref('')
const rollKey = ref(0)
const drawerOpen = ref(false)
const editingId = ref(null)
const tableHostRef = ref(null)
const tableHeight = ref(360)
const formRef = ref(null)
const form = reactive({
  category: 'ingredient',
  name: '',
  record_method: 'link',
  contact_value: '',
  platform: '',
  supplier_label: '',
  remark: '',
})

const countValue = computed(() => (loaded.value ? rows.value.length : null))
const emptyText = computed(() => {
  if (keyword.value.trim() || category.value || method.value) return '没有符合条件的资料'
  return '还没有采购资料'
})
const drawerTitle = computed(() => (editingId.value ? '编辑资料' : '新增资料'))
const contactLabel = computed(() => {
  if (form.record_method === 'wechat') return '微信号'
  if (form.record_method === 'phone') return '手机号'
  if (form.record_method === 'other') return '联系内容'
  return '链接'
})
const contactPlaceholder = computed(() => {
  if (form.record_method === 'wechat') return '如：okfood_supplier_01'
  if (form.record_method === 'phone') return '供应商手机号'
  if (form.record_method === 'other') return '写下怎么找到这家'
  return '粘贴淘宝、拼多多或 1688 链接'
})

const rules = computed(() => ({
  category: [{ required: true, message: '请选择分类', trigger: 'change' }],
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  record_method: [{ required: true, message: '请选择记录方式', trigger: 'change' }],
  contact_value: [{
    required: true,
    validator: (_rule, value, callback) => {
      const text = String(value || '').trim()
      if (!text) {
        callback(new Error(`请填写${contactLabel.value}`))
        return
      }
      if (form.record_method === 'link' && !/^https?:\/\//i.test(text)) {
        callback(new Error('采购链接需要以 http:// 或 https:// 开头'))
        return
      }
      callback()
    },
    trigger: 'blur',
  }],
}))

let searchTimer = 0
let resizeObserver = null

function measureTable() {
  const host = tableHostRef.value
  if (!host) return
  const next = Math.floor(host.clientHeight)
  if (next > 120) tableHeight.value = next
}

function queryString() {
  const params = new URLSearchParams()
  const q = keyword.value.trim()
  if (q) params.set('q', q)
  if (category.value) params.set('category', category.value)
  if (method.value) params.set('record_method', method.value)
  const text = params.toString()
  return text ? `?${text}` : ''
}

function toastError(error, fallback) {
  if (error && typeof error === 'object' && error.status === 401) {
    alert('登录已过期')
    handleAdminLogout()
    return
  }
  showToast(error instanceof Error ? error.message : fallback, 'error')
}

async function load() {
  loading.value = true
  try {
    const data = await listPurchaseNotes(queryString())
    rows.value = Array.isArray(data) ? data : []
    loaded.value = true
    rollKey.value += 1
  } catch (error) {
    toastError(error, '加载失败')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.category = 'ingredient'
  form.name = ''
  form.record_method = 'link'
  form.contact_value = ''
  form.platform = ''
  form.supplier_label = ''
  form.remark = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  drawerOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.category = row.category || 'ingredient'
  form.name = row.name || ''
  form.record_method = row.record_method || 'link'
  form.contact_value = row.contact_value || ''
  form.platform = row.platform || ''
  form.supplier_label = row.supplier_label || ''
  form.remark = row.remark || ''
  drawerOpen.value = true
}

function payload() {
  return {
    category: form.category,
    name: form.name.trim(),
    record_method: form.record_method,
    contact_value: form.contact_value.trim(),
    platform: form.platform.trim(),
    supplier_label: form.supplier_label.trim(),
    remark: form.remark.trim(),
  }
}

async function save() {
  const formEl = formRef.value
  if (!formEl) return
  try {
    await formEl.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await patchPurchaseNote(editingId.value, payload())
    } else {
      await createPurchaseNote(payload())
    }
    drawerOpen.value = false
    showToast('已保存', 'success')
    await load()
  } catch (error) {
    toastError(error, '保存失败')
  } finally {
    saving.value = false
  }
}

function onBeforeClose(done) {
  if (saving.value) return
  done()
}

function escapeMessageBoxHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `<p class="okfood-message-box__subject">删除「${escapeMessageBoxHtml(row.name)}」？</p><p class="okfood-message-box__detail">只去掉这条采购备忘，不影响库存和菜品。</p>`,
      '删除采购资料',
      {
        customClass: 'okfood-message-box okfood-message-box--delete',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'okfood-message-box__confirm--danger',
        cancelButtonClass: 'okfood-message-box__cancel',
        distinguishCancelAndClose: true,
        dangerouslyUseHTMLString: true,
      },
    )
  } catch {
    return
  }
  try {
    await deletePurchaseNote(row.id)
    showToast('已删除', 'success')
    await load()
  } catch (error) {
    toastError(error, '删除失败')
  }
}

async function onCopy(row) {
  const text = String(row.contact_value || '').trim()
  if (!text) {
    showToast('没有可复制的内容', 'error')
    return
  }
  try {
    await navigator.clipboard.writeText(text)
    showToast('已复制', 'success')
  } catch {
    showToast('复制失败，请手动选择', 'error')
  }
}

function categoryLabel(value) {
  return CATEGORIES.find((item) => item.value === value)?.label || value
}

function methodShort(value) {
  return METHODS.find((item) => item.value === value)?.short || value
}

function methodTagType(value) {
  if (value === 'wechat') return 'success'
  if (value === 'phone') return 'warning'
  if (value === 'other') return 'info'
  return 'primary'
}

watch([keyword, category, method], () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    void load()
  }, 250)
})

watch(
  () => form.record_method,
  () => {
    formRef.value?.clearValidate('contact_value')
  },
)

onMounted(() => {
  measureTable()
  if (typeof ResizeObserver !== 'undefined' && tableHostRef.value) {
    resizeObserver = new ResizeObserver(() => measureTable())
    resizeObserver.observe(tableHostRef.value)
  }
  void load()
})

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
  resizeObserver?.disconnect()
})
</script>

<template>
  <section class="purchase-notes-page members-view-fill tab-content animate-up">
    <header class="purchase-notes-head">
      <div class="purchase-notes-head__copy">
        <p class="mkt-kicker">库存管理</p>
        <div class="purchase-notes-title-row">
          <h1 class="mkt-title">采购资料</h1>
          <span class="purchase-notes-count">
            <StatRollNumber :value="countValue" :replay-key="rollKey" />
            <span>条</span>
          </span>
        </div>
        <p class="mkt-intro">独立记录食材和耗材的采购链接或联系方式，不关联菜品、库存和供应商。</p>
      </div>
      <div class="purchase-notes-head__side">
        <el-button type="primary" round @click="openCreate">新增资料</el-button>
      </div>
    </header>

    <div class="table-container table-container--members-fill purchase-notes-card">
      <div class="purchase-notes-toolbar">
        <el-input
          v-model="keyword"
          clearable
          class="purchase-notes-search"
          placeholder="搜索名称、链接、微信或备注"
        >
          <template #prefix>
            <Search :size="15" :stroke-width="2.25" aria-hidden="true" />
          </template>
        </el-input>
        <el-select v-model="category" clearable placeholder="全部分类" class="purchase-notes-select">
          <el-option v-for="item in CATEGORIES" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="method" clearable placeholder="全部方式" class="purchase-notes-select">
          <el-option v-for="item in METHODS" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <p class="purchase-notes-shown">
          显示
          <StatRollNumber :value="countValue" :replay-key="rollKey" />
          条
        </p>
      </div>
      <div ref="tableHostRef" class="members-table-host">
        <AdminTable
          variant="members"
          class="members-el-table-body-scroll"
          size="small"
          row-key="id"
          :height="tableHeight"
          :data="rows"
          :loading="loading"
          :stripe="false"
          :border="false"
          :empty-text="emptyText"
        >
          <el-table-column label="名称" min-width="168">
            <template #default="{ row }">
              <div class="purchase-notes-name">
                <div class="purchase-notes-name__title">{{ row.name }}</div>
                <div v-if="row.supplier_label" class="purchase-notes-name__sub">{{ row.supplier_label }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="分类" width="108">
            <template #default="{ row }">
              <el-tag
                :type="row.category === 'consumable' ? 'warning' : 'success'"
                effect="light"
                round
              >
                {{ categoryLabel(row.category) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="采购信息" min-width="240">
            <template #default="{ row }">
              <div class="purchase-notes-contact">
                <el-tag size="small" effect="light" round :type="methodTagType(row.record_method)">
                  {{ methodShort(row.record_method) }}
                </el-tag>
                <el-tooltip
                  :content="row.contact_value"
                  placement="top"
                  :show-after="400"
                  :disabled="!row.contact_value"
                >
                  <a
                    v-if="row.record_method === 'link'"
                    class="purchase-notes-contact__value purchase-notes-contact__value--link"
                    :href="row.contact_value"
                    target="_blank"
                    rel="noopener noreferrer"
                  >{{ row.contact_value }}</a>
                  <span v-else class="purchase-notes-contact__value">{{ row.contact_value }}</span>
                </el-tooltip>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="平台" width="110" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.platform">{{ row.platform }}</span>
              <span v-else class="purchase-notes-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }">
              <el-tooltip
                v-if="row.remark"
                :content="row.remark"
                placement="top"
                :show-after="400"
              >
                <span class="purchase-notes-ellipsis">{{ row.remark }}</span>
              </el-tooltip>
              <span v-else class="purchase-notes-muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="168" fixed="right">
            <template #default="{ row }">
              <div class="purchase-notes-actions">
                <el-button link type="primary" @click="onCopy(row)">复制</el-button>
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button link type="danger" @click="onDelete(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </AdminTable>
      </div>
    </div>

    <el-drawer
      v-model="drawerOpen"
      direction="rtl"
      size="min(460px, 100vw)"
      append-to-body
      destroy-on-close
      :close-on-click-modal="!saving"
      :before-close="onBeforeClose"
      class="purchase-note-drawer"
    >
      <template #header>
        <div class="purchase-note-drawer__head">
          <p class="purchase-note-drawer__kicker">采购资料</p>
          <h2 class="purchase-note-drawer__title">{{ drawerTitle }}</h2>
          <p class="purchase-note-drawer__sub">只记录查找和联系信息，保存后不会影响库存或菜品。</p>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        class="purchase-note-form"
        @submit.prevent
      >
        <section class="okfood-mem-edit-sec">
          <div class="okfood-mem-edit-sec-head">
            <span class="okfood-mem-edit-bar" aria-hidden="true" />
            <h3 class="okfood-mem-edit-sec-title">基本信息</h3>
          </div>
          <div class="purchase-note-grid">
            <el-form-item label="分类" prop="category">
              <el-select v-model="form.category" class="purchase-note-full">
                <el-option v-for="item in CATEGORIES" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" maxlength="64" placeholder="如：螺旋意面" />
            </el-form-item>
          </div>
        </section>

        <section class="okfood-mem-edit-sec">
          <div class="okfood-mem-edit-sec-head">
            <span class="okfood-mem-edit-bar" aria-hidden="true" />
            <h3 class="okfood-mem-edit-sec-title">采购信息</h3>
          </div>
          <el-form-item label="记录方式" prop="record_method">
            <el-radio-group v-model="form.record_method" class="purchase-note-methods">
              <el-radio-button v-for="item in METHODS" :key="item.value" :value="item.value">
                {{ item.label }}
              </el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="contactLabel" prop="contact_value">
            <el-input v-model="form.contact_value" maxlength="500" :placeholder="contactPlaceholder" />
          </el-form-item>
          <div class="purchase-note-grid">
            <el-form-item label="平台">
              <el-input v-model="form.platform" maxlength="32" placeholder="如：淘宝、微信" />
            </el-form-item>
            <el-form-item label="简称 / 供应方">
              <el-input v-model="form.supplier_label" maxlength="64" placeholder="选填，便于确认" />
            </el-form-item>
          </div>
        </section>

        <section class="okfood-mem-edit-sec">
          <div class="okfood-mem-edit-sec-head">
            <span class="okfood-mem-edit-bar" aria-hidden="true" />
            <h3 class="okfood-mem-edit-sec-title">补充说明</h3>
          </div>
          <el-form-item label="备注">
            <el-input
              v-model="form.remark"
              type="textarea"
              maxlength="500"
              show-word-limit
              :autosize="{ minRows: 3, maxRows: 6 }"
              placeholder="如规格、包装数量、联系时要说明的内容"
            />
          </el-form-item>
        </section>
      </el-form>

      <template #footer>
        <div class="purchase-note-drawer__foot">
          <el-button round :disabled="saving" @click="drawerOpen = false">取消</el-button>
          <el-button type="primary" round :loading="saving" @click="save">保存</el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<style scoped>
.purchase-notes-page {
  gap: 0.85rem;
  overflow: hidden;
  min-width: 0;
}

.purchase-notes-head {
  display: flex;
  flex-shrink: 0;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
}

.purchase-notes-head__copy {
  min-width: 0;
}

.purchase-notes-head__side {
  flex-shrink: 0;
}

.purchase-notes-title-row {
  display: flex;
  align-items: baseline;
  gap: 0.55rem;
  min-width: 0;
}

.purchase-notes-count,
.purchase-notes-shown {
  display: inline-flex;
  align-items: baseline;
  gap: 0.15rem;
  white-space: nowrap;
}

.purchase-notes-count {
  padding: 0.12rem 0.55rem 0.16rem;
  border-radius: 999px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 800;
}

.purchase-notes-count :deep(.stat-roll),
.purchase-notes-shown :deep(.stat-roll) {
  font-weight: 800;
  color: var(--el-color-primary);
}

.purchase-notes-card {
  background: #fff;
}

.purchase-notes-card.table-container--members-fill > .members-table-host::after {
  content: none;
}

.purchase-notes-toolbar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  overflow-x: auto;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.purchase-notes-search {
  width: 280px;
  flex: 0 0 280px;
}

.purchase-notes-select {
  width: 132px;
  flex: 0 0 132px;
}

.purchase-notes-shown {
  margin-left: auto;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.purchase-notes-page :deep(.el-table__header th.el-table__cell:hover) {
  background-color: var(--okfood-el-table-header-bg) !important;
  color: var(--okfood-el-table-header-text) !important;
}

.purchase-notes-name__title,
.purchase-notes-ellipsis,
.purchase-notes-contact__value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.purchase-notes-name__title {
  font-weight: 700;
  color: #1e293b;
}

.purchase-notes-name__sub,
.purchase-notes-muted {
  color: #94a3b8;
  font-size: 12px;
  line-height: 1.4;
}

.purchase-notes-contact {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.purchase-notes-contact .el-tag {
  flex-shrink: 0;
}

.purchase-notes-contact__value {
  min-width: 0;
  color: #334155;
}

.purchase-notes-contact__value--link {
  color: var(--el-color-primary);
  text-decoration: none;
}

.purchase-notes-contact__value--link:hover {
  text-decoration: underline;
}

.purchase-notes-actions {
  display: flex;
  align-items: center;
  white-space: nowrap;
}

.purchase-notes-ellipsis {
  display: inline-block;
  max-width: 100%;
  vertical-align: bottom;
}

@media (max-width: 720px) {
  .purchase-notes-head {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>

<style>
.purchase-note-drawer.el-drawer {
  background: #fff;
}

.purchase-note-drawer .el-drawer__header {
  margin-bottom: 0;
  padding: 16px 18px 12px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
}

.purchase-note-drawer .el-drawer__body {
  padding: 12px 14px;
  background: #f8fafc;
}

.purchase-note-drawer .el-drawer__footer {
  padding: 12px 18px 16px;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
}

.purchase-note-drawer__kicker {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #94a3b8;
}

.purchase-note-drawer__title {
  margin: 2px 0 0;
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: #1e293b;
}

.purchase-note-drawer__sub {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.purchase-note-drawer__foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.purchase-note-form .okfood-mem-edit-sec + .okfood-mem-edit-sec {
  margin-top: 10px;
}

.purchase-note-form .el-form-item {
  margin-bottom: 12px;
}

.purchase-note-form .el-form-item:last-child {
  margin-bottom: 0;
}

.purchase-note-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 12px;
}

.purchase-note-full {
  width: 100%;
}

.purchase-note-methods {
  display: flex;
  width: 100%;
}

.purchase-note-methods .el-radio-button {
  flex: 1;
}

.purchase-note-methods .el-radio-button__inner {
  width: 100%;
  padding-left: 0;
  padding-right: 0;
}

@media (max-width: 520px) {
  .purchase-note-grid {
    grid-template-columns: 1fr;
  }
}
</style>
