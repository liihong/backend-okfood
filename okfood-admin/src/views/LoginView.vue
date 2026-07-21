<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  apiJson,
  setAdminToken,
  syncAdminKindFromLoginPayload,
  rememberLogin,
  LOGIN_PRESET_USER,
  LOGIN_PRESET_PASSWORD,
  adminKind,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'
import companyLogo from '../assets/company-logo.png'

const router = useRouter()

const loginUsername = ref(LOGIN_PRESET_USER)
const loginPassword = ref(LOGIN_PRESET_PASSWORD)
const loginLoading = ref(false)
const loginError = ref(false)

const brandFeatures = [
  { label: '会员履约', emoji: '👥' },
  { label: '配送调度', emoji: '🚚' },
  { label: '财务透明', emoji: '💰' },
  { label: '订单统计', emoji: '📊' },
  { label: '续卡管理', emoji: '💳' },
]

const handleAdminLogin = async () => {
  if (loginLoading.value) return
  if (!loginUsername.value.trim() || !String(loginPassword.value ?? '').trim()) {
    showToast('请填写账号和密码', 'error')
    return
  }
  loginLoading.value = true
  loginError.value = false

  try {
    const data = await apiJson('/api/admin/login', {
      method: 'POST',
      body: JSON.stringify({
        username: loginUsername.value.trim(),
        password: loginPassword.value,
      }),
    })
    const token = data && data.access_token
    if (!token) throw new Error('登录响应缺少 access_token')
    setAdminToken(token)
    syncAdminKindFromLoginPayload(data)
    showToast('登录成功')
    await router.replace({
      name:
        adminKind.value === 'delivery'
          ? 'regions'
          : adminKind.value === 'system'
            ? 'system-tenants'
            : 'dashboard',
    })
  } catch (e) {
    loginError.value = true
    window.setTimeout(() => {
      loginError.value = false
    }, 500)
    showToast(e instanceof Error ? e.message : '登录失败', 'error')
  } finally {
    loginLoading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-wrapper">
      <div class="brand-side">
        <div class="brand-side-bg"></div>
        <div class="brand-side-content">
          <img
            class="brand-logo-mark"
            :src="companyLogo"
            alt="火源网络科技"
            width="160"
            height="160"
          />
          <h1>轻食解决方案管理系统</h1>
          <h2>火源网络科技</h2>
          <div class="brand-features">
            <div v-for="item in brandFeatures" :key="item.label" class="feature-item">
              <div class="feature-icon-wrap">
                <span class="feature-emoji" aria-hidden="true">{{ item.emoji }}</span>
              </div>
              <span>{{ item.label }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="form-side">
        <div class="form-container" :class="{ 'shake-err': loginError }">
          <div class="form-header">
            <h2>欢迎回来 &#128076;</h2>
            <p>请登录超级管家后台</p>
          </div>

          <form class="login-form" @submit.prevent="handleAdminLogin">
            <div class="form-group login-form-group">
              <label>管理员账号 / Account</label>
              <div class="input-box input-box--el">
                <el-input
                  v-model="loginUsername"
                  placeholder="Admin ID"
                  clearable
                  autocomplete="username"
                  class="login-el-field"
                >
                  <template #prefix>
                    <svg
                      class="input-icon"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                    >
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  </template>
                </el-input>
              </div>
            </div>

            <div class="form-group login-form-group">
              <label>登录密码 / Password</label>
              <div class="input-box input-box--el">
                <el-input
                  v-model="loginPassword"
                  type="password"
                  placeholder="********"
                  show-password
                  autocomplete="current-password"
                  class="login-el-field login-el-field--pwd"
                >
                  <template #prefix>
                    <svg
                      class="input-icon"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2.5"
                    >
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  </template>
                </el-input>
              </div>
            </div>

            <div class="form-extras">
              <el-checkbox v-model="rememberLogin" class="login-remember-el">记住登录</el-checkbox>
              <a href="#" class="forgot-link" @click.prevent>忘记密码？</a>
            </div>

            <button type="submit" class="btn-submit" :disabled="loginLoading">
              <template v-if="!loginLoading">进入管理台 &#128076;</template>
              <template v-else>
                <svg
                  class="loading-icon"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="3"
                  stroke-linecap="round"
                >
                  <path
                    d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"
                  />
                </svg>
                正在同步数据中...
              </template>
            </button>
          </form>
        </div>

        <div class="form-footer">
          <p>© 2026 OK FINE · NEW XIANG BRANCH · V2.0</p>
        </div>
      </div>
    </div>
  </div>
</template>
