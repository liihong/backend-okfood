<script setup>
defineOptions({ name: 'TenantMiniAuthorizerPage' })

import { ref, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import TenantMiniProgramLayout from './TenantMiniProgramLayout.vue'
import TenantAuthorizerPanel from '../TenantAuthorizerPanel.vue'
import { useTenantMiniProgramPage } from '../../../composables/useTenantMiniProgramPage.js'
import { showToast } from '../../../composables/useToast.js'
import { ALBUM_WRITE_ONLY_PRIVACY_TEXT } from './albumWritePrivacy.js'

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
const privacySetting = ref(null)
const privacyLoading = ref(false)
const privacySyncing = ref(false)
const privacyError = ref('')

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

async function loadPrivacySetting() {
  if (!api.value || !authorizer.value.authorizer_mode_active) {
    privacySetting.value = null
    privacyError.value = ''
    return
  }
  privacyLoading.value = true
  privacyError.value = ''
  try {
    privacySetting.value = await api.value.loadPrivacySetting()
  } catch (e) {
    privacySetting.value = null
    privacyError.value = e?.message || '查询隐私指引失败'
  } finally {
    privacyLoading.value = false
  }
}

async function load() {
  if (!ensureReady() || !api.value) return
  loading.value = true
  try {
    const data = await api.value.loadAuthorizer()
    resetAuthorizerFromPayload(data)
    await loadPrivacySetting()
  } catch (e) {
    toastError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function syncAlbumPrivacy() {
  if (!api.value || !authorizer.value.authorizer_mode_active) return
  try {
    await ElMessageBox.confirm(
      `将为该小程序更新开发版用户隐私保护指引，写入「相册（仅写入）」：${ALBUM_WRITE_ONLY_PRIVACY_TEXT}。若尚未配置过隐私指引，会一并提交 OK饭 模板（手机号、位置、选点、头像、相册仅写入）；已有其它权限的用途保持不变。开发版提交后即更新，现网需再提交版本审核并发布。`,
      '更新隐私指引',
      { type: 'warning', confirmButtonText: '更新隐私指引', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  privacySyncing.value = true
  try {
    const data = await api.value.syncAlbumWritePrivacy()
    const wroteTemplate = Boolean(data?.used_default_template)
    showToast(
      wroteTemplate ? '已提交 OK饭 隐私模板（含相册仅写入）' : '相册（仅写入）隐私指引已更新',
      'success',
    )
    await loadPrivacySetting()
  } catch (e) {
    toastError(e, '更新隐私指引失败')
  } finally {
    privacySyncing.value = false
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
    await loadPrivacySetting()
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
    await loadPrivacySetting()
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
    await loadPrivacySetting()
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
      :privacy-setting="privacySetting"
      :privacy-loading="privacyLoading"
      :privacy-syncing="privacySyncing"
      :privacy-error="privacyError"
      @generate-pre-auth="generatePreAuthLink"
      @copy-pre-auth="copyPreAuthLink"
      @exchange-code="exchangeAuthorizerCode"
      @save-token="saveAuthorizer"
      @refresh-token="refreshAuthorizerToken"
      @sync-album-privacy="syncAlbumPrivacy"
      @refresh-privacy="loadPrivacySetting"
    />
  </TenantMiniProgramLayout>
</template>
