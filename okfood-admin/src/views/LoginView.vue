<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  apiJson,
  setAdminToken,
  rememberLogin,
  LOGIN_PRESET_USER,
  LOGIN_PRESET_PASSWORD,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const router = useRouter()

const loginUsername = ref(LOGIN_PRESET_USER)
const loginPassword = ref(LOGIN_PRESET_PASSWORD)
const showPassword = ref(false)
const loginLoading = ref(false)
const loginError = ref(false)

const handleAdminLogin = async () => {
  if (loginLoading.value) return
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
    showToast('登录成功')
    await router.replace({ name: 'dashboard' })
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
          <div class="logo-box brand-logo-mark">&#128076;</div>
          <h1>OK Fine</h1>
          <p>Digital Management Center</p>
          <div class="brand-features">
            <div class="feature-item">
              <div class="feature-emoji">&#128202;</div>
              <span>数据实时</span>
            </div>
            <div class="feature-item">
              <div class="feature-emoji">&#128666;</div>
              <span>调度智能</span>
            </div>
            <div class="feature-item">
              <div class="feature-emoji">&#128176;</div>
              <span>财务透明</span>
            </div>
          </div>
        </div>
      </div>

      <div class="form-side">
        <div class="form-container" :class="{ 'shake-err': loginError }">
          <div class="form-header">
            <h2>欢迎回来 &#128076;</h2>
            <p>请登录 OK Fine 超级管家后台</p>
          </div>

          <form class="login-form" @submit.prevent="handleAdminLogin">
            <div class="form-group login-form-group">
              <label>管理员账号 / Account</label>
              <div class="input-box">
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
                <input
                  v-model="loginUsername"
                  type="text"
                  placeholder="Admin ID"
                  required
                  autocomplete="username"
                />
              </div>
            </div>

            <div class="form-group login-form-group">
              <label>登录密码 / Password</label>
              <div class="input-box">
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
                <input
                  v-model="loginPassword"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="********"
                  required
                  autocomplete="current-password"
                />
                <button type="button" class="btn-eye" @click="showPassword = !showPassword">
                  <span v-if="showPassword">&#128584;</span>
                  <span v-else>&#128065;</span>
                </button>
              </div>
            </div>

            <div class="form-extras">
              <label class="remember-me">
                <input v-model="rememberLogin" type="checkbox" /> 记住登录
              </label>
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
