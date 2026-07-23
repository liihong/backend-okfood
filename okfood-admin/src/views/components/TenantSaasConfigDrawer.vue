<script setup>
/**
 * 租户 SaaS 展示配置 + 微信第三方平台 authorizer 运维（平台管理员）
 */
import { ref, computed, watch } from 'vue'
import { apiJson, adminAccessToken, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  tenant: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const drawerVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const loading = ref(false)
const saving = ref(false)
const authorizerLoading = ref(false)
const authorizerSaving = ref(false)

const HOME_LAYOUT_PRESETS = [
  { value: 'standard-default', label: '标准（Banner+登录+会员卡+推荐）' },
  { value: 'standard-minimal', label: '极简（Banner+登录+点单按钮）' },
  { value: 'standard-catalog', label: '目录（Banner+宫格+主推）' },
]

const FEATURE_KEYS = [
  { key: 'douyinRedeem', label: '抖音核销' },
  { key: 'courierMode', label: '骑手模式' },
  { key: 'membershipCard', label: '会员卡' },
  { key: 'retailMenu', label: '零售菜单' },
  { key: 'leaveManagement', label: '请假管理' },
  { key: 'coupon', label: '优惠券' },
]

const form = ref({
  tenant_code: '',
  app_name: '',
  default_store_id: 1,
  home_template: 'default',
  home_layout_preset: 'standard-default',
  theme_primary_color: '#73B054',
  theme_page_bg: '#f7f5f0',
  features: {},
  share_home_title: '',
  share_order_title: '',
  share_mine_slogan: '',
  legal_agreement_title: '',
  legal_agreement_url: '',
  subscribe_delivery_tmpl_id: '',
})

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

function resetFormFromPayload(data) {
  const theme = data?.theme && typeof data.theme === 'object' ? data.theme : {}
  const features = data?.features && typeof data.features === 'object' ? data.features : {}
  const share = data?.share && typeof data.share === 'object' ? data.share : {}
  const legal = data?.legal && typeof data.legal === 'object' ? data.legal : {}
  form.value = {
    tenant_code: data?.tenant_code != null ? String(data.tenant_code) : '',
    app_name: data?.app_name != null ? String(data.app_name) : '',
    default_store_id: Number(data?.default_store_id) >= 1 ? Number(data.default_store_id) : 1,
    home_template: data?.home_template || 'default',
    home_layout_preset: data?.home_layout_preset || 'standard-default',
    theme_primary_color: theme.primaryColor || '#73B054',
    theme_page_bg: theme.pageBg || '#f7f5f0',
    features: { ...features },
    share_home_title: share.homeTitle || '',
    share_order_title: share.orderTitle || '',
    share_mine_slogan: share.mineSlogan || '',
    legal_agreement_title: legal.membershipAgreementTitle || '',
    legal_agreement_url: legal.membershipAgreementUrl || '',
    subscribe_delivery_tmpl_id: data?.subscribe_delivery_tmpl_id || '',
  }
  for (const f of FEATURE_KEYS) {
    if (form.value.features[f.key] === undefined) {
      form.value.features[f.key] = f.key !== 'douyinRedeem'
    }
  }
}

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
}

async function loadAll() {
  const tid = props.tenant?.id
  if (tid == null || !adminAccessToken.value) return
  loading.value = true
  authorizerLoading.value = true
  try {
    const [saas, auth] = await Promise.all([
      apiJson(`/api/admin/system/tenants/${tid}/saas-config`, {}, { auth: true }),
      apiJson(`/api/admin/system/tenants/${tid}/wx-authorizer`, {}, { auth: true }),
    ])
    resetFormFromPayload(saas)
    resetAuthorizerFromPayload(auth)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载 SaaS 配置失败', 'error')
  } finally {
    loading.value = false
    authorizerLoading.value = false
  }
}

watch(
  () => [props.visible, props.tenant?.id],
  ([vis]) => {
    if (vis && props.tenant?.id != null) void loadAll()
  },
)

async function saveSaas() {
  const tid = props.tenant?.id
  if (tid == null) return
  const code = String(form.value.tenant_code || '').trim()
  if (code && !/^[a-zA-Z0-9_-]+$/.test(code)) {
    showToast('tenantId 仅允许字母、数字、下划线、连字符', 'error')
    return
  }
  saving.value = true
  try {
    const body = {
      tenant_code: code || null,
      app_name: String(form.value.app_name || '').trim() || null,
      default_store_id: Math.max(1, Math.floor(Number(form.value.default_store_id) || 1)),
      home_template: String(form.value.home_template || 'default').trim() || 'default',
      home_layout_preset: form.value.home_layout_preset || 'standard-default',
      theme: {
        primaryColor: String(form.value.theme_primary_color || '').trim() || '#73B054',
        pageBg: String(form.value.theme_page_bg || '').trim() || '#f7f5f0',
      },
      features: { ...form.value.features },
      share: {
        homeTitle: String(form.value.share_home_title || '').trim(),
        orderTitle: String(form.value.share_order_title || '').trim(),
        mineSlogan: String(form.value.share_mine_slogan || '').trim(),
      },
      legal: {
        membershipAgreementTitle: String(form.value.legal_agreement_title || '').trim(),
        membershipAgreementUrl: String(form.value.legal_agreement_url || '').trim(),
      },
      subscribe_delivery_tmpl_id: String(form.value.subscribe_delivery_tmpl_id || '').trim() || null,
    }
    const data = await apiJson(
      `/api/admin/system/tenants/${tid}/saas-config`,
      { method: 'PATCH', body: JSON.stringify(body) },
      { auth: true },
    )
    resetFormFromPayload(data)
    showToast('SaaS 配置已保存', 'success')
    emit('saved')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
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
</script>

<template>
  <el-drawer
    v-model="drawerVisible"
    :title="tenant ? `SaaS 配置：${tenant.name}` : 'SaaS 配置'"
    size="680px"
    class="saas-drawer"
  >
    <div v-loading="loading" class="saas-drawer-body">
      <p class="saas-tip">
        此处配置会合并到小程序 <code>ext</code>，并通过 <code>GET /api/tenant/config</code> 下发。
        <strong>tenantId</strong> 须与 commit 时 <code>ext.tenantId</code> 一致。
      </p>

      <el-form label-position="top" class="saas-form">
        <el-divider content-position="left">基础</el-divider>
        <el-form-item label="外部 tenantId（tenants.code）">
          <el-input v-model="form.tenant_code" maxlength="64" placeholder="如 t_brand_a" />
        </el-form-item>
        <el-form-item label="小程序展示名称 appName">
          <el-input v-model="form.app_name" maxlength="128" placeholder="如：某某健康餐" />
        </el-form-item>
        <el-form-item label="默认门店 defaultStoreId">
          <el-input-number v-model="form.default_store_id" :min="1" :controls="true" class="w-full" />
        </el-form-item>
        <el-form-item label="首页模板 homeTemplate">
          <el-select v-model="form.home_template" style="width: 100%">
            <el-option label="default" value="default" />
            <el-option label="minimal" value="minimal" />
            <el-option label="catalog" value="catalog" />
          </el-select>
        </el-form-item>
        <el-form-item label="首页 layout 预设 homeLayoutPreset">
          <el-select v-model="form.home_layout_preset" style="width: 100%">
            <el-option
              v-for="p in HOME_LAYOUT_PRESETS"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>

        <el-divider content-position="left">主题 theme</el-divider>
        <el-form-item label="主色 primaryColor">
          <el-color-picker v-model="form.theme_primary_color" :show-alpha="false" />
          <el-input v-model="form.theme_primary_color" class="color-input" maxlength="16" />
        </el-form-item>
        <el-form-item label="页面背景 pageBg">
          <el-color-picker v-model="form.theme_page_bg" :show-alpha="false" />
          <el-input v-model="form.theme_page_bg" class="color-input" maxlength="16" />
        </el-form-item>

        <el-divider content-position="left">功能开关 features</el-divider>
        <div class="feature-grid">
          <el-form-item v-for="f in FEATURE_KEYS" :key="f.key" :label="f.label" class="feature-item">
            <el-switch v-model="form.features[f.key]" />
          </el-form-item>
        </div>

        <el-divider content-position="left">分享文案 share</el-divider>
        <el-form-item label="首页分享标题">
          <el-input v-model="form.share_home_title" maxlength="128" />
        </el-form-item>
        <el-form-item label="菜单页分享标题">
          <el-input v-model="form.share_order_title" maxlength="128" />
        </el-form-item>
        <el-form-item label="我的页 slogan">
          <el-input v-model="form.share_mine_slogan" maxlength="128" />
        </el-form-item>

        <el-divider content-position="left">法律协议 legal</el-divider>
        <el-form-item label="会员协议标题">
          <el-input v-model="form.legal_agreement_title" maxlength="256" />
        </el-form-item>
        <el-form-item label="会员协议 URL">
          <el-input v-model="form.legal_agreement_url" maxlength="512" placeholder="https://..." />
        </el-form-item>

        <el-divider content-position="left">订阅消息</el-divider>
        <el-form-item label="配送通知模板 ID">
          <el-input v-model="form.subscribe_delivery_tmpl_id" maxlength="128" />
        </el-form-item>
      </el-form>

      <el-divider content-position="left">微信第三方平台 · Authorizer</el-divider>
      <div v-loading="authorizerLoading" class="authorizer-block">
        <p class="saas-tip authorizer-tip">
          代运营小程序登录须落库 <code>authorizer_refresh_token</code>。
          服务器 .env 须配置 <code>WX_OPEN_COMPONENT_*</code>，回调 URL：
          <code>/api/wx/open/component/callback</code>
        </p>
        <el-descriptions :column="1" border size="small" class="auth-desc">
          <el-descriptions-item label="AppID">{{ authorizer.authorizer_appid || '—' }}</el-descriptions-item>
          <el-descriptions-item label="Authorizer 模式">
            <el-tag :type="authorizer.authorizer_mode_active ? 'success' : 'info'" size="small">
              {{ authorizer.authorizer_mode_active ? '已启用' : '未启用（走直连 Secret）' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="Refresh Token">
            {{ authorizer.has_authorizer_refresh_token ? '已落库' : '未配置' }}
          </el-descriptions-item>
          <el-descriptions-item label="Token 过期">{{ authorizer.token_expires_at || '—' }}</el-descriptions-item>
          <el-descriptions-item label="Component Ticket">
            <el-tag :type="authorizer.component_ticket_present ? 'success' : 'warning'" size="small">
              {{ authorizer.component_ticket_present ? '已落库' : '未就绪' }}
            </el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <el-form label-position="top" class="auth-form">
          <el-form-item label="authorization_code（授权完成后换取 token）">
            <el-input v-model="authorizerForm.authorization_code" type="password" show-password maxlength="512" />
            <el-button size="small" class="mt-8" :loading="authorizerSaving" @click="exchangeAuthorizerCode">
              用授权码换取并落库
            </el-button>
          </el-form-item>
          <el-form-item label="authorizer_refresh_token（运维手动粘贴）">
            <el-input
              v-model="authorizerForm.authorizer_refresh_token"
              type="password"
              show-password
              maxlength="512"
              placeholder="留空不改；填写则更新"
            />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="authorizerForm.clear">清除已落库的 authorizer token</el-checkbox>
          </el-form-item>
          <div class="auth-actions">
            <el-button size="small" :loading="authorizerSaving" @click="saveAuthorizer">保存 Token</el-button>
            <el-button
              size="small"
              type="primary"
              plain
              :loading="authorizerSaving"
              :disabled="!authorizer.has_authorizer_refresh_token"
              @click="refreshAuthorizerToken"
            >
              刷新 access_token
            </el-button>
          </div>
        </el-form>
      </div>
    </div>

    <template #footer>
      <div class="saas-footer">
        <el-button @click="drawerVisible = false">关闭</el-button>
        <el-button type="primary" :loading="saving" :disabled="loading" @click="saveSaas">保存 SaaS 配置</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<style scoped>
.saas-drawer-body {
  min-height: 240px;
  padding-bottom: 24px;
}
.saas-tip {
  margin: 0 0 16px;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.88);
}
.saas-tip code {
  font-size: 0.8rem;
  color: #fde047;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}
.feature-item {
  margin-bottom: 0;
}
.color-input {
  margin-left: 12px;
  max-width: 160px;
}
.w-full {
  width: 100%;
}
.authorizer-block {
  margin-top: 8px;
}
.authorizer-tip {
  margin-bottom: 12px;
}
.auth-desc {
  margin-bottom: 16px;
}
.auth-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.saas-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
.mt-8 {
  margin-top: 8px;
}
</style>
