<script setup>
defineOptions({ name: 'TenantMiniAuthorizerPage' })

import { ref, onMounted } from 'vue'
import TenantMiniProgramLayout from './TenantMiniProgramLayout.vue'
import TenantAuthorizerPanel from '../TenantAuthorizerPanel.vue'
import { useTenantMiniProgramPage } from '../../../composables/useTenantMiniProgramPage.js'
import { showToast } from '../../../composables/useToast.js'

const { tenantId, tenantName, api, backToTenants, toastError, ensureReady } = useTenantMiniProgramPage()

const loading = ref(false)
const saving = ref(false)
const preAuthLoading = ref(false)
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

async function load() {
  if (!ensureReady() || !api.value) return
  loading.value = true
  try {
    const data = await api.value.loadAuthorizer()
    resetAuthorizerFromPayload(data)
  } catch (e) {
    toastError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function saveAuthorizer() {
  if (!api.value) return
  saving.value = true
  try {
    const body = { clear: authorizerForm.value.clear === true }
    const rt = String(authorizerForm.value.authorizer_refresh_token || '').trim()
    if (rt) body.authorizer_refresh_token = rt
    const data = await api.value.patchAuthorizer(body)
    resetAuthorizerFromPayload(data)
    showToast('Authorizer 配置已保存', 'success')
  } catch (e) {
    toastError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

async function exchangeAuthorizerCode() {
  if (!api.value) return
  const code = String(authorizerForm.value.authorization_code || '').trim()
  if (!code) {
    showToast('请填写 authorization_code', 'error')
    return
  }
  saving.value = true
  try {
    const data = await api.value.exchangeAuthorizerCode(code)
    resetAuthorizerFromPayload(data)
    showToast('授权码已换取并落库', 'success')
  } catch (e) {
    toastError(e, '换取失败')
  } finally {
    saving.value = false
  }
}

async function refreshAuthorizerToken() {
  if (!api.value) return
  saving.value = true
  try {
    const data = await api.value.refreshAuthorizerToken()
    resetAuthorizerFromPayload(data)
    const domainErr = String(data?.domain_sync_error || '').trim()
    if (domainErr) {
      showToast(`access_token 已刷新；域名同步失败：${domainErr}`, 'success')
    } else if (data?.domain_sync?.synced_at) {
      showToast('access_token 已刷新，服务器域名已同步', 'success')
    } else {
      showToast('access_token 已刷新', 'success')
    }
  } catch (e) {
    toastError(e, '刷新失败')
  } finally {
    saving.value = false
  }
}

async function generatePreAuthLink() {
  if (!api.value) return
  preAuthLoading.value = true
  try {
    const data = await api.value.createPreAuthLink()
    preAuthLink.value = {
      authorization_url: data?.authorization_url || '',
      redirect_uri: data?.redirect_uri || '',
      expires_in: Number(data?.expires_in) || 0,
      pre_auth_code: data?.pre_auth_code || '',
    }
    showToast('授权链接已生成，请发给商户扫码授权', 'success')
  } catch (e) {
    toastError(e, '生成失败')
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

onMounted(() => {
  void load()
})
</script>

<template>
  <TenantMiniProgramLayout
    v-if="tenantId != null"
    :tenant-id="tenantId"
    :tenant-name="tenantName"
    @back="backToTenants"
  >
    <TenantAuthorizerPanel
      :authorizer="authorizer"
      :authorizer-form="authorizerForm"
      :pre-auth-link="preAuthLink"
      :loading="loading"
      :saving="saving"
      :pre-auth-loading="preAuthLoading"
      @generate-pre-auth="generatePreAuthLink"
      @copy-pre-auth="copyPreAuthLink"
      @exchange-code="exchangeAuthorizerCode"
      @save-token="saveAuthorizer"
      @refresh-token="refreshAuthorizerToken"
    />
  </TenantMiniProgramLayout>
</template>
