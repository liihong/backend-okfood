<script setup>
/**
 * 租户小程序管理抽屉（分 Tab：品牌与首页 / 授权 / 代码发布）
 * 替代原单体 TenantSaasConfigDrawer，避免单文件臃肿。
 */
import { ref, computed, watch } from 'vue'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import TenantBrandConfigPanel from './TenantBrandConfigPanel.vue'
import TenantAuthorizerPanel from './TenantAuthorizerPanel.vue'
import TenantCodePublishPanel from './TenantCodePublishPanel.vue'
import {
  MINI_PROGRAM_TABS,
  DEFAULT_TEMPLATE_ID,
  createEmptyBrandForm,
  brandFormFromPayload,
  brandPayloadFromForm,
  defaultUserVersion,
} from './tenantMiniProgramConstants.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  tenant: { type: Object, default: null },
  /** 打开时定位的 Tab：brand | authorizer | publish */
  initialTab: { type: String, default: MINI_PROGRAM_TABS.brand },
})

const emit = defineEmits(['update:visible', 'saved'])

const drawerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const activeTab = ref(MINI_PROGRAM_TABS.brand)
const loading = ref(false)
const brandSaving = ref(false)
const authorizerLoading = ref(false)
const authorizerSaving = ref(false)
const preAuthLoading = ref(false)
const publishLoading = ref(false)
const committing = ref(false)
const qrcodeLoading = ref(false)

const brandForm = ref(createEmptyBrandForm())
const authorizer = ref({
  authorizer_appid: '',
  has_authorizer_refresh_token: false,
  has_authorizer_access_token: false,
  token_expires_at: '',
  authorized_at: '',
  authorizer_mode_active: false,
  component_platform_configured: false,
  component_ticket_present: false,
})
const authorizerForm = ref({
  authorizer_refresh_token: '',
  authorization_code: '',
  clear: false,
})
const preAuthLink = ref({
  authorization_url: '',
  redirect_uri: '',
  expires_in: 0,
  pre_auth_code: '',
})

const publishState = ref(null)
const templates = ref([])
const publishForm = ref({
  template_id: DEFAULT_TEMPLATE_ID,
  user_version: defaultUserVersion(),
  user_desc: 'SaaS 体验版',
})
const qrcodeDataUrl = ref('')

function resetAuthorizerFromPayload(data) {
  authorizer.value = {
    authorizer_appid: data?.authorizer_appid || '',
    has_authorizer_refresh_token: Boolean(data?.has_authorizer_refresh_token),
    has_authorizer_access_token: Boolean(data?.has_authorizer_access_token),
    token_expires_at: data?.token_expires_at || '',
    authorized_at: data?.authorized_at || '',
    authorizer_mode_active: Boolean(data?.authorizer_mode_active),
    component_platform_configured: Boolean(data?.component_platform_configured),
    component_ticket_present: Boolean(data?.component_ticket_present),
  }
  authorizerForm.value = {
    authorizer_refresh_token: '',
    authorization_code: '',
    clear: false,
  }
  preAuthLink.value = {
    authorization_url: '',
    redirect_uri: '',
    expires_in: 0,
    pre_auth_code: '',
  }
}

function handleAuthError(e) {
  const status = e && typeof e.status === 'number' ? e.status : 0
  if (status === 401) {
    alert('登录已过期，请重新登录')
    handleAdminLogout()
    return true
  }
  return false
}

async function loadBrandAndAuthorizer() {
  const tid = props.tenant?.id
  if (tid == null || !adminAccessToken.value) return
  loading.value = true
  authorizerLoading.value = true
  try {
    const [saas, auth] = await Promise.all([
      apiJson(`/api/admin/system/tenants/${tid}/saas-config`, {}, { auth: true }),
      apiJson(`/api/admin/system/tenants/${tid}/wx-authorizer`, {}, { auth: true }),
    ])
    brandForm.value = brandFormFromPayload(saas)
    resetAuthorizerFromPayload(auth)
  } catch (e) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
    authorizerLoading.value = false
  }
}

async function loadTemplates() {
  try {
    const data = await apiJson('/api/admin/system/wx-open/templates', {}, { auth: true })
    templates.value = Array.isArray(data?.items) ? data.items : []
    const defId = Number(data?.default_template_id) || DEFAULT_TEMPLATE_ID
    if (!templates.value.some((t) => Number(t.template_id) === Number(publishForm.value.template_id))) {
      publishForm.value.template_id = defId
    }
  } catch (e) {
    templates.value = []
    if (!handleAuthError(e)) {
      showToast(e instanceof Error ? e.message : '模板列表加载失败', 'error')
    }
  }
}

async function loadPublishState() {
  const tid = props.tenant?.id
  if (tid == null) return
  publishLoading.value = true
  try {
    publishState.value = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-code/publish-state`,
      {},
      { auth: true },
    )
    if (publishState.value?.last_user_version) {
      // 保留用户正在编辑的版本；仅在空时回填
      if (!String(publishForm.value.user_version || '').trim()) {
        publishForm.value.user_version = defaultUserVersion()
      }
    }
  } catch (e) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : '发布状态加载失败', 'error')
  } finally {
    publishLoading.value = false
  }
}

async function onOpen() {
  const tab = String(props.initialTab || MINI_PROGRAM_TABS.brand)
  activeTab.value = Object.values(MINI_PROGRAM_TABS).includes(tab) ? tab : MINI_PROGRAM_TABS.brand
  qrcodeDataUrl.value = ''
  publishForm.value = {
    template_id: DEFAULT_TEMPLATE_ID,
    user_version: defaultUserVersion(),
    user_desc: `${props.tenant?.name || '租户'} SaaS 体验版`,
  }
  await loadBrandAndAuthorizer()
  // 发布相关按需加载，减少打开抽屉时的请求
  if (activeTab.value === MINI_PROGRAM_TABS.publish) {
    await Promise.all([loadTemplates(), loadPublishState()])
  }
}

watch(
  () => [props.visible, props.tenant?.id, props.initialTab],
  ([vis]) => {
    if (vis && props.tenant?.id != null) void onOpen()
  },
)

watch(activeTab, async (tab) => {
  if (!props.visible || props.tenant?.id == null) return
  if (tab === MINI_PROGRAM_TABS.publish) {
    await Promise.all([loadTemplates(), loadPublishState()])
  }
})

async function saveBrand() {
  const tid = props.tenant?.id
  if (tid == null) return
  const code = String(brandForm.value.tenant_code || '').trim()
  if (code && !/^[a-zA-Z0-9_-]+$/.test(code)) {
    showToast('tenantId 仅允许字母、数字、下划线、连字符', 'error')
    return
  }
  brandSaving.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/saas-config`,
      { method: 'PATCH', body: JSON.stringify(brandPayloadFromForm(brandForm.value)) },
      { auth: true },
    )
    brandForm.value = brandFormFromPayload(data)
    showToast('品牌与首页已保存', 'success')
    emit('saved')
    // 同步刷新 ext 预览
    if (activeTab.value === MINI_PROGRAM_TABS.publish) {
      await loadPublishState()
    }
  } catch (e) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    brandSaving.value = false
  }
}

async function saveAuthorizer() {
  const tid = props.tenant?.id
  if (tid == null) return
  authorizerSaving.value = true
  try {
    const body = { clear: authorizerForm.value.clear === true }
    const rt = String(authorizerForm.value.authorizer_refresh_token || '').trim()
    if (rt) body.authorizer_refresh_token = rt
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-authorizer`,
      { method: 'PATCH', body: JSON.stringify(body) },
      { auth: true },
    )
    resetAuthorizerFromPayload(data)
    showToast('Authorizer 配置已保存', 'success')
    emit('saved')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    authorizerSaving.value = false
  }
}

async function exchangeAuthorizerCode() {
  const tid = props.tenant?.id
  const code = String(authorizerForm.value.authorization_code || '').trim()
  if (tid == null || !code) {
    showToast('请填写 authorization_code', 'error')
    return
  }
  authorizerSaving.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-authorizer/exchange-code`,
      { method: 'POST', body: JSON.stringify({ authorization_code: code }) },
      { auth: true },
    )
    resetAuthorizerFromPayload(data)
    showToast('授权码已换取并落库', 'success')
    emit('saved')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '换取失败', 'error')
  } finally {
    authorizerSaving.value = false
  }
}

async function refreshAuthorizerToken() {
  const tid = props.tenant?.id
  if (tid == null) return
  authorizerSaving.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-authorizer/refresh`,
      { method: 'POST', body: '{}' },
      { auth: true },
    )
    resetAuthorizerFromPayload(data)
    showToast('access_token 已刷新', 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '刷新失败', 'error')
  } finally {
    authorizerSaving.value = false
  }
}

async function generatePreAuthLink() {
  const tid = props.tenant?.id
  if (tid == null) return
  preAuthLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-authorizer/pre-auth-link`,
      { method: 'POST', body: '{}' },
      { auth: true },
    )
    preAuthLink.value = {
      authorization_url: data?.authorization_url || '',
      redirect_uri: data?.redirect_uri || '',
      expires_in: Number(data?.expires_in) || 0,
      pre_auth_code: data?.pre_auth_code || '',
    }
    showToast('授权链接已生成，请发给商户扫码授权', 'success')
  } catch (e) {
    showToast(e instanceof Error ? e.message : '生成失败', 'error')
  } finally {
    preAuthLoading.value = false
  }
}

async function copyPreAuthLink() {
  const url = String(preAuthLink.value.authorization_url || '').trim()
  if (!url) {
    showToast('请先生成授权链接', 'error')
    return
  }
  try {
    await navigator.clipboard.writeText(url)
    showToast('授权链接已复制', 'success')
  } catch {
    showToast('复制失败，请手动选中链接复制', 'error')
  }
}

async function commitCode() {
  const tid = props.tenant?.id
  if (tid == null) return
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
    publishState.value = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-code/commit`,
      {
        method: 'POST',
        body: JSON.stringify({
          template_id: templateId,
          user_version: userVersion,
          user_desc: userDesc,
        }),
      },
      { auth: true },
    )
    showToast('已上传体验版，可获取体验码', 'success')
    emit('saved')
    qrcodeDataUrl.value = ''
  } catch (e) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : '上传失败', 'error')
    await loadPublishState()
  } finally {
    committing.value = false
  }
}

async function fetchQrcode() {
  const tid = props.tenant?.id
  if (tid == null) return
  qrcodeLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/wx-code/trial-qrcode`,
      {},
      { auth: true },
    )
    const b64 = String(data?.image_base64 || '').trim()
    const ct = String(data?.content_type || 'image/jpeg').trim() || 'image/jpeg'
    if (!b64) {
      showToast('未返回二维码数据', 'error')
      return
    }
    qrcodeDataUrl.value = `data:${ct};base64,${b64}`
    showToast('体验码已生成', 'success')
  } catch (e) {
    if (handleAuthError(e)) return
    showToast(e instanceof Error ? e.message : '拉取体验码失败', 'error')
  } finally {
    qrcodeLoading.value = false
  }
}
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="tenant ? `小程序管理：${tenant.name}` : '小程序管理'"
    size="720px"
    class="mini-program-drawer"
  >
    <el-tabs v-model="activeTab" class="mini-tabs">
      <el-tab-pane label="品牌与首页" :name="MINI_PROGRAM_TABS.brand">
        <TenantBrandConfigPanel
          v-loading="loading"
          :form="brandForm"
          :saving="brandSaving"
          @save="saveBrand"
        />
      </el-tab-pane>
      <el-tab-pane label="授权" :name="MINI_PROGRAM_TABS.authorizer">
        <TenantAuthorizerPanel
          :authorizer="authorizer"
          :authorizer-form="authorizerForm"
          :pre-auth-link="preAuthLink"
          :loading="authorizerLoading"
          :saving="authorizerSaving"
          :pre-auth-loading="preAuthLoading"
          @generate-pre-auth="generatePreAuthLink"
          @copy-pre-auth="copyPreAuthLink"
          @exchange-code="exchangeAuthorizerCode"
          @save-token="saveAuthorizer"
          @refresh-token="refreshAuthorizerToken"
        />
      </el-tab-pane>
      <el-tab-pane label="代码发布" :name="MINI_PROGRAM_TABS.publish">
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
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <div class="drawer-footer">
        <el-button @click="drawerVisible = false">关闭</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.mini-tabs {
  min-height: 360px;
}
.drawer-footer {
  display: flex;
  justify-content: flex-end;
}
</style>
