<script setup>
/**
 * 租户小程序 · 代授权（Authorizer）面板
 * 仅运维代开发小程序；OK饭等未授权租户保持「未启用（走直连 Secret）」。
 */
defineProps({
  authorizer: { type: Object, required: true },
  authorizerForm: { type: Object, required: true },
  preAuthLink: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  preAuthLoading: { type: Boolean, default: false },
})

const emit = defineEmits([
  'generate-pre-auth',
  'copy-pre-auth',
  'exchange-code',
  'save-token',
  'refresh-token',
])
</script>

<template>
  <div v-loading="loading" class="authorizer-panel">
    <p class="panel-tip">
      传统模式：平台生成授权链接 → 商户扫码 → 自动落库 authorizer token。
      服务器须配置 <code>WX_OPEN_COMPONENT_*</code> 与 <code>BASE_URL</code>。
      回调：<code>/api/wx/open/component/callback</code>；完成页：
      <code>/api/wx/open/authorize/callback</code>。
      <strong>未授权租户（含 OK饭直连）不会走代调用。</strong>
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

    <el-alert
      v-if="!authorizer.component_platform_configured || !authorizer.component_ticket_present"
      type="warning"
      :closable="false"
      show-icon
      class="auth-prereq-alert"
      title="暂无法生成授权链接"
    >
      <ul class="auth-prereq-list">
        <li v-if="!authorizer.component_platform_configured">
          服务器 .env 未配置 <code>WX_OPEN_COMPONENT_APPID</code> / <code>WX_OPEN_COMPONENT_SECRET</code>
        </li>
        <li v-if="!authorizer.component_ticket_present">
          <code>component_verify_ticket</code> 未就绪。请到租户管理页顶部「微信第三方平台」面板处理。
        </li>
      </ul>
    </el-alert>

    <div class="pre-auth-block">
      <div class="pre-auth-head">
        <strong>传统模式 · 生成授权链接</strong>
        <el-button
          type="primary"
          size="small"
          :loading="preAuthLoading"
          :disabled="!authorizer.component_platform_configured || !authorizer.component_ticket_present"
          @click="emit('generate-pre-auth')"
        >
          生成授权链接
        </el-button>
      </div>
      <p class="panel-tip pre-auth-tip">
        为当前租户申请 <code>pre_auth_code</code>（约 10 分钟有效）。授权成功后可在此刷新状态确认。
      </p>
      <el-input
        v-if="preAuthLink.authorization_url"
        :model-value="preAuthLink.authorization_url"
        type="textarea"
        :rows="3"
        readonly
        class="pre-auth-url"
      />
      <div v-if="preAuthLink.authorization_url" class="pre-auth-meta">
        <span>有效期约 {{ preAuthLink.expires_in }} 秒</span>
        <el-button size="small" @click="emit('copy-pre-auth')">复制链接</el-button>
        <el-link :href="preAuthLink.authorization_url" type="primary" target="_blank" rel="noopener">
          新窗口打开
        </el-link>
      </div>
    </div>

    <el-form label-position="top" class="auth-form">
      <el-form-item label="authorization_code（授权完成后换取 token）">
        <el-input v-model="authorizerForm.authorization_code" type="password" show-password maxlength="512" />
        <el-button size="small" class="mt-8" :loading="saving" @click="emit('exchange-code')">
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
        <el-button size="small" :loading="saving" @click="emit('save-token')">保存 Token</el-button>
        <el-button
          size="small"
          type="primary"
          plain
          :loading="saving"
          :disabled="!authorizer.has_authorizer_refresh_token"
          @click="emit('refresh-token')"
        >
          刷新 access_token
        </el-button>
      </div>
    </el-form>
  </div>
</template>

<style scoped>
.panel-tip {
  margin: 0 0 16px;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.88);
}
.panel-tip code {
  font-size: 0.8rem;
  color: #fde047;
}
.auth-desc {
  margin-bottom: 16px;
}
.auth-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.pre-auth-block {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.18);
}
.pre-auth-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.pre-auth-tip {
  margin-bottom: 10px;
}
.pre-auth-url {
  margin-bottom: 8px;
}
.pre-auth-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 0.82rem;
  color: rgba(226, 232, 240, 0.75);
}
.auth-prereq-alert {
  margin-bottom: 12px;
}
.auth-prereq-list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.6;
}
.mt-8 {
  margin-top: 8px;
}
</style>
