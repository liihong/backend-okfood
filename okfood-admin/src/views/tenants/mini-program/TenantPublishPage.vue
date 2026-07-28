<script setup>
defineOptions({ name: 'TenantMiniPublishPage' })

import { ref, onMounted } from 'vue'
import TenantMiniProgramLayout from './TenantMiniProgramLayout.vue'
import TenantCodePublishPanel from '../TenantCodePublishPanel.vue'
import TenantFormalReleasePanel from '../TenantFormalReleasePanel.vue'
import { useTenantMiniProgramPage } from '../../../composables/useTenantMiniProgramPage.js'
import { showToast } from '../../../composables/useToast.js'
import { DEFAULT_TEMPLATE_ID, defaultUserVersion } from '../tenantMiniProgramConstants.js'

const { tenantId, tenantName, api, backToTenants, toastError, ensureReady } = useTenantMiniProgramPage()

const publishLoading = ref(false)
const committing = ref(false)
const qrcodeLoading = ref(false)
const auditSubmitting = ref(false)
const auditRefreshing = ref(false)
const releasing = ref(false)
const categoriesLoading = ref(false)

const publishState = ref(null)
const templates = ref([])
const categories = ref([])
const publishForm = ref({
  template_id: DEFAULT_TEMPLATE_ID,
  user_version: defaultUserVersion(),
  user_desc: '',
})
const auditForm = ref({
  page_path: 'pages/home/index',
  page_title: '首页',
  version_desc: '',
  feedback_info: '',
})
const qrcodeDataUrl = ref('')

async function loadPublishState() {
  if (!api.value) return
  publishLoading.value = true
  try {
    publishState.value = await api.value.loadPublishState()
  } catch (e) {
    toastError(e, '发布状态加载失败')
  } finally {
    publishLoading.value = false
  }
}

async function loadTemplates() {
  if (!api.value) return
  try {
    const data = await api.value.loadTemplates()
    templates.value = Array.isArray(data?.items) ? data.items : []
    const defId = Number(data?.default_template_id) || DEFAULT_TEMPLATE_ID
    if (!templates.value.some((t) => Number(t.template_id) === Number(publishForm.value.template_id))) {
      publishForm.value.template_id = defId
    }
  } catch (e) {
    templates.value = []
    toastError(e, '模板列表加载失败')
  }
}

async function loadCategories() {
  if (!api.value) return
  categoriesLoading.value = true
  try {
    const data = await api.value.loadAuditCategories()
    categories.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    categories.value = []
    toastError(e, '类目加载失败')
  } finally {
    categoriesLoading.value = false
  }
}

async function initPage() {
  if (!ensureReady() || !api.value) return
  publishForm.value.user_desc = `${tenantName.value} SaaS 体验版`
  await Promise.all([loadPublishState(), loadTemplates(), loadCategories()])
}

async function commitCode() {
  if (!api.value) return
  const templateId = Math.floor(Number(publishForm.value.template_id))
  const userVersion = String(publishForm.value.user_version || '').trim()
  const userDesc = String(publishForm.value.user_desc || '').trim()
  if (!Number.isFinite(templateId) || templateId < 0) {
    showToast('请选择有效 template_id', 'error')
    return
  }
  if (!userVersion || !userDesc) {
    showToast('请填写版本号与描述', 'error')
    return
  }
  committing.value = true
  try {
    publishState.value = await api.value.commitCode({
      template_id: templateId,
      user_version: userVersion,
      user_desc: userDesc,
    })
    showToast('已上传体验版，可获取体验码', 'success')
    qrcodeDataUrl.value = ''
  } catch (e) {
    toastError(e, '上传失败')
    await loadPublishState()
  } finally {
    committing.value = false
  }
}

async function fetchQrcode() {
  if (!api.value) return
  qrcodeLoading.value = true
  try {
    const data = await api.value.fetchTrialQrcode()
    const b64 = String(data?.image_base64 || '').trim()
    const ct = String(data?.content_type || 'image/jpeg').trim() || 'image/jpeg'
    if (!b64) {
      showToast('未返回二维码数据', 'error')
      return
    }
    qrcodeDataUrl.value = `data:${ct};base64,${b64}`
    showToast('体验码已生成', 'success')
  } catch (e) {
    toastError(e, '拉取体验码失败')
  } finally {
    qrcodeLoading.value = false
  }
}

async function submitAudit(payload) {
  if (!api.value) return
  auditSubmitting.value = true
  try {
    publishState.value = await api.value.submitAudit(payload)
    showToast('已提交微信审核', 'success')
  } catch (e) {
    toastError(e, '提交审核失败')
    await loadPublishState()
  } finally {
    auditSubmitting.value = false
  }
}

async function refreshAuditStatus() {
  if (!api.value) return
  auditRefreshing.value = true
  try {
    publishState.value = await api.value.loadAuditStatus()
    showToast('审核状态已更新', 'success')
  } catch (e) {
    toastError(e, '查询审核状态失败')
  } finally {
    auditRefreshing.value = false
  }
}

async function releaseFormal() {
  if (!api.value) return
  releasing.value = true
  try {
    publishState.value = await api.value.releaseCode()
    showToast('已发布正式版', 'success')
  } catch (e) {
    toastError(e, '发布正式版失败')
    await loadPublishState()
  } finally {
    releasing.value = false
  }
}

onMounted(() => {
  void initPage()
})
</script>

<template>
  <TenantMiniProgramLayout
    v-if="tenantId != null"
    :tenant-id="tenantId"
    :tenant-name="tenantName"
    @back="backToTenants"
  >
    <section class="publish-section">
      <h3 class="section-title">体验版</h3>
      <TenantCodePublishPanel
        :publish-state="publishState"
        :templates="templates"
        :form="publishForm"
        :loading="publishLoading"
        :committing="committing"
        :qrcode-loading="qrcodeLoading"
        :qrcode-data-url="qrcodeDataUrl"
        @refresh="loadPublishState"
        @commit="commitCode"
        @fetch-qrcode="fetchQrcode"
        @reload-templates="loadTemplates"
      />
    </section>

    <el-divider />

    <section class="publish-section">
      <h3 class="section-title">正式版</h3>
      <TenantFormalReleasePanel
        :publish-state="publishState"
        :categories="categories"
        :form="auditForm"
        :loading="publishLoading || categoriesLoading"
        :submitting="auditSubmitting"
        :refreshing="auditRefreshing"
        :releasing="releasing"
        @refresh-status="refreshAuditStatus"
        @submit-audit="submitAudit"
        @release="releaseFormal"
        @reload-categories="loadCategories"
      />
    </section>
  </TenantMiniProgramLayout>
</template>

<style scoped>
.publish-section {
  margin-bottom: 8px;
}
.section-title {
  margin: 0 0 12px;
  font-size: 1rem;
  font-weight: 600;
  color: rgba(248, 250, 252, 0.92);
}
</style>
