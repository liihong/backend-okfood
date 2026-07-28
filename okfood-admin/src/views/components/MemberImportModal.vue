<script setup>
/**
 * 会员批量导入弹窗：上传 Excel → 预览校验 → 确认入库。
 * 与后端 /api/admin/members/import/* 接口配套。
 */
defineOptions({ name: 'MemberImportModal' })
import { ref, computed, watch } from 'vue'
import { X, Upload, Download, FileSpreadsheet, CheckCircle2, AlertCircle, SkipForward } from 'lucide-vue-next'
import { apiBlob, apiForm, apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const open = defineModel('open', { type: Boolean, default: false })
const emit = defineEmits(['imported'])

/** @typedef {'idle' | 'preview' | 'confirming'} ImportStep */

/** @type {import('vue').Ref<ImportStep>} */
const step = ref('idle')
const uploading = ref(false)
const confirming = ref(false)
const templateDownloading = ref(false)
/** @type {import('vue').Ref<File | null>} */
const selectedFile = ref(null)
/** @type {import('vue').Ref<object | null>} */
const previewData = ref(null)
const uploadKey = ref(0)

const previewRows = computed(() => {
  const rows = previewData.value?.rows
  return Array.isArray(rows) ? rows : []
})

const previewSummary = computed(() => previewData.value?.summary || { total: 0, ready: 0, error: 0, skip: 0 })

const readyRows = computed(() =>
  previewRows.value.filter((r) => r?.status === 'ready' && r?.data).map((r) => r.data),
)

const canConfirm = computed(() => readyRows.value.length > 0 && !confirming.value)

function resetState() {
  step.value = 'idle'
  selectedFile.value = null
  previewData.value = null
  uploading.value = false
  confirming.value = false
  uploadKey.value += 1
}

watch(open, (v) => {
  if (!v) resetState()
})

function statusLabel(status) {
  if (status === 'ready') return '可入库'
  if (status === 'skip') return '跳过'
  if (status === 'error') return '错误'
  return status || '—'
}

function statusClass(status) {
  if (status === 'ready') return 'member-import-status--ready'
  if (status === 'skip') return 'member-import-status--skip'
  if (status === 'error') return 'member-import-status--error'
  return ''
}

async function downloadTemplate() {
  if (templateDownloading.value) return
  templateDownloading.value = true
  try {
    const { blob } = await apiBlob('/api/admin/members/import/template.xlsx', {}, { auth: true })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '会员导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
    showToast('模板已下载', 'success')
  } catch (e) {
    const status = e?.status
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '下载模板失败', 'error')
  } finally {
    templateDownloading.value = false
  }
}

/** @param {import('element-plus').UploadFile} uploadFile */
async function onFileChange(uploadFile) {
  const raw = uploadFile?.raw
  if (!raw) return
  if (!/\.xlsx$/i.test(raw.name || '')) {
    showToast('请上传 .xlsx 格式的 Excel 文件', 'error')
    uploadKey.value += 1
    return
  }
  selectedFile.value = raw
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', raw)
    const data = await apiForm('/api/admin/members/import/preview', fd, { auth: true })
    previewData.value = data
    step.value = 'preview'
    const s = data?.summary
    if (s?.ready > 0) {
      showToast(`解析完成：${s.ready} 条可入库`, 'success')
    } else if (s?.error > 0) {
      showToast('解析完成，但无有效可入库数据，请修正错误后重试', 'error')
    } else {
      showToast('解析完成，无可入库数据（可能均已存在）', 'error')
    }
  } catch (e) {
    const status = e?.status
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '解析文件失败', 'error')
    selectedFile.value = null
    step.value = 'idle'
  } finally {
    uploading.value = false
    uploadKey.value += 1
  }
}

function backToUpload() {
  step.value = 'idle'
  previewData.value = null
  selectedFile.value = null
  uploadKey.value += 1
}

async function confirmImport() {
  if (!canConfirm.value) return
  confirming.value = true
  try {
    const result = await apiJson(
      '/api/admin/members/import/confirm',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows: readyRows.value }),
      },
      { auth: true },
    )
    const inserted = Number(result?.inserted) || 0
    const skipped = Number(result?.skipped) || 0
    const failed = Number(result?.failed) || 0
    let msg = `入库完成：成功 ${inserted} 条`
    if (skipped) msg += `，跳过 ${skipped} 条`
    if (failed) msg += `，失败 ${failed} 条`
    showToast(msg, inserted > 0 ? 'success' : 'error')
    if (inserted > 0) {
      emit('imported')
      open.value = false
    }
  } catch (e) {
    const status = e?.status
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '入库失败', 'error')
  } finally {
    confirming.value = false
  }
}

function formatRowData(data) {
  if (!data) return '—'
  const parts = [
    data.name,
    data.phone,
    data.plan_type,
    data.address,
    `剩余${data.balance}/${data.meal_quota_total}`,
  ]
  return parts.filter(Boolean).join(' · ')
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="member-import-overlay" role="dialog" aria-modal="true" aria-labelledby="member-import-title">
      <div class="member-import-panel">
        <header class="member-import-header">
          <div class="member-import-header__title-wrap">
            <FileSpreadsheet :size="20" aria-hidden="true" />
            <h2 id="member-import-title" class="member-import-header__title">批量导入会员</h2>
          </div>
          <button type="button" class="member-import-close" aria-label="关闭" @click="open = false">
            <X :size="18" />
          </button>
        </header>

        <div class="member-import-body">
          <div class="member-import-toolbar">
            <el-button size="small" :loading="templateDownloading" @click="downloadTemplate">
              <Download :size="14" aria-hidden="true" style="margin-right: 4px; vertical-align: -2px" />
              下载导入模板
            </el-button>
            <p class="member-import-hint">
              请先下载模板填写会员信息，再上传 .xlsx 文件预览。同一手机号已存在时将自动跳过，不会覆盖已有档案。
            </p>
          </div>

          <div v-if="step === 'idle'" class="member-import-upload-zone">
            <el-upload
              :key="uploadKey"
              drag
              :auto-upload="false"
              :show-file-list="false"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              :disabled="uploading"
              @change="onFileChange"
            >
              <div v-loading="uploading" class="member-import-upload-inner">
                <Upload :size="32" stroke-width="1.5" aria-hidden="true" />
                <p class="member-import-upload-title">点击或拖拽上传 Excel 文件</p>
                <p class="member-import-upload-sub">仅支持 .xlsx，最大 5MB</p>
              </div>
            </el-upload>
          </div>

          <template v-else-if="step === 'preview'">
            <div class="member-import-summary">
              <span>共 {{ previewSummary.total }} 行</span>
              <span class="member-import-summary__ready">
                <CheckCircle2 :size="14" /> 可入库 {{ previewSummary.ready }}
              </span>
              <span class="member-import-summary__skip">
                <SkipForward :size="14" /> 跳过 {{ previewSummary.skip }}
              </span>
              <span class="member-import-summary__error">
                <AlertCircle :size="14" /> 错误 {{ previewSummary.error }}
              </span>
              <span v-if="selectedFile" class="member-import-file-name">{{ selectedFile.name }}</span>
            </div>

            <div class="member-import-table-wrap">
              <table class="member-import-table">
                <thead>
                  <tr>
                    <th>行号</th>
                    <th>状态</th>
                    <th>会员信息</th>
                    <th>说明</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in previewRows" :key="`${row.row_no}-${row.status}`">
                    <td>{{ row.row_no }}</td>
                    <td>
                      <span class="member-import-status" :class="statusClass(row.status)">
                        {{ statusLabel(row.status) }}
                      </span>
                    </td>
                    <td>{{ formatRowData(row.data) }}</td>
                    <td class="member-import-messages">
                      {{ (row.messages || []).join('；') || '—' }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

        <footer class="member-import-footer">
          <el-button v-if="step === 'preview'" size="small" @click="backToUpload">重新上传</el-button>
          <el-button size="small" @click="open = false">取消</el-button>
          <el-button
            v-if="step === 'preview'"
            type="primary"
            size="small"
            :loading="confirming"
            :disabled="!canConfirm"
            @click="confirmImport"
          >
            确认入库（{{ readyRows.length }} 条）
          </el-button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.member-import-overlay {
  position: fixed;
  inset: 0;
  z-index: 5000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}

.member-import-panel {
  width: min(920px, 100%);
  max-height: min(90vh, 820px);
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.member-import-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #e2e8f0;
}

.member-import-header__title-wrap {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #0f172a;
}

.member-import-header__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}

.member-import-close {
  border: none;
  background: transparent;
  cursor: pointer;
  color: #64748b;
  padding: 0.25rem;
  border-radius: 6px;
}

.member-import-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.member-import-body {
  flex: 1;
  overflow: auto;
  padding: 1rem 1.25rem;
}

.member-import-toolbar {
  margin-bottom: 1rem;
}

.member-import-hint {
  margin: 0.75rem 0 0;
  font-size: 0.8125rem;
  color: #64748b;
  line-height: 1.5;
}

.member-import-upload-zone :deep(.el-upload) {
  width: 100%;
}

.member-import-upload-zone :deep(.el-upload-dragger) {
  width: 100%;
  padding: 2rem 1rem;
  border-radius: 10px;
}

.member-import-upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: #475569;
}

.member-import-upload-title {
  margin: 0;
  font-weight: 600;
  color: #0f172a;
}

.member-import-upload-sub {
  margin: 0;
  font-size: 0.8125rem;
  color: #94a3b8;
}

.member-import-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1rem;
  align-items: center;
  margin-bottom: 0.75rem;
  font-size: 0.875rem;
  color: #334155;
}

.member-import-summary__ready {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: #15803d;
}

.member-import-summary__skip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: #b45309;
}

.member-import-summary__error {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  color: #b91c1c;
}

.member-import-file-name {
  margin-left: auto;
  color: #64748b;
  font-size: 0.8125rem;
}

.member-import-table-wrap {
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  max-height: 420px;
}

.member-import-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8125rem;
}

.member-import-table th,
.member-import-table td {
  padding: 0.5rem 0.65rem;
  border-bottom: 1px solid #f1f5f9;
  text-align: left;
  vertical-align: top;
}

.member-import-table th {
  background: #f8fafc;
  font-weight: 600;
  color: #475569;
  position: sticky;
  top: 0;
}

.member-import-status {
  display: inline-block;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.member-import-status--ready {
  background: #dcfce7;
  color: #166534;
}

.member-import-status--skip {
  background: #fef3c7;
  color: #92400e;
}

.member-import-status--error {
  background: #fee2e2;
  color: #991b1b;
}

.member-import-messages {
  color: #64748b;
  max-width: 220px;
}

.member-import-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  padding: 0.85rem 1.25rem;
  border-top: 1px solid #e2e8f0;
}
</style>
