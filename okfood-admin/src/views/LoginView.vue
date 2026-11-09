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
import loginBgm from '../assets/login/logo-bgm.jpeg'

/** 登录页售卖能力（与左侧五宫格一致） */
const LOGIN_SELLING_POINTS = [
  { key: 'member', label: '会员履约' },
  { key: 'delivery', label: '配送调度' },
  { key: 'finance', label: '财务透明' },
  { key: 'orders', label: '订单统计' },
  { key: 'renew', label: '续卡管理' },
]

const router = useRouter()

const loginUsername = ref(LOGIN_PRESET_USER)
const loginPassword = ref(LOGIN_PRESET_PASSWORD)
const loginLoading = ref(false)
const loginError = ref(false)

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
    <div class="login-canvas">
      <div class="login-canvas__mesh" aria-hidden="true">
        <div class="mesh-blob mesh-blob--a"></div>
        <div class="mesh-blob mesh-blob--b"></div>
        <div class="mesh-blob mesh-blob--c"></div>
      </div>

      <div class="deco-bubbles" aria-hidden="true">
        <span class="deco-bubble deco-bubble--1"></span>
        <span class="deco-bubble deco-bubble--2"></span>
        <span class="deco-bubble deco-bubble--3"></span>
        <span class="deco-bubble deco-bubble--4"></span>
        <span class="deco-bubble deco-bubble--5"></span>
        <span class="deco-bubble deco-bubble--6"></span>
        <span class="deco-bubble deco-bubble--7"></span>
        <span class="deco-bubble deco-bubble--8"></span>
        <span class="deco-bubble deco-bubble--9"></span>
        <span class="deco-bubble deco-bubble--10"></span>
        <span class="deco-bubble deco-bubble--11"></span>
        <span class="deco-bubble deco-bubble--12"></span>
      </div>

      <div class="login-stage-wrap">
        <article class="login-stage" aria-labelledby="login-title">
          <div class="login-stage__cover">
            <div class="login-stage__cover-inner">
              <img
                :src="loginBgm"
                alt=""
                width="1200"
                height="800"
                loading="eager"
              />
              <div class="login-stage__cover-dock">
                <header class="login-stage__dock-head">
                  <p class="login-stage__title">私域会员配送管理系统</p>
                </header>
                <ul class="login-stage__features" aria-label="系统核心能力">
                  <li
                    v-for="item in LOGIN_SELLING_POINTS"
                    :key="item.key"
                    class="login-stage__feature"
                  >
                    <span class="login-feature__icon" aria-hidden="true">
                      <svg
                        v-if="item.key === 'member'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
                        <circle cx="9" cy="7" r="4" />
                        <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
                      </svg>
                      <svg
                        v-else-if="item.key === 'delivery'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M5 17h12l2-7H7l-2 7z" />
                        <path d="M5 17l-1.5 3M19 17l1.5 3" />
                        <circle cx="7.5" cy="20" r="1.5" fill="currentColor" />
                        <circle cx="16.5" cy="20" r="1.5" fill="currentColor" />
                      </svg>
                      <svg
                        v-else-if="item.key === 'finance'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M12 3v18M8 7h8a3 3 0 0 1 0 6H8a3 3 0 0 0 0 6h8" />
                      </svg>
                      <svg
                        v-else-if="item.key === 'orders'"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <path d="M4 19V5" />
                        <path d="M4 19h16" />
                        <path d="M10 19V13" />
                        <path d="M16 19V9" />
                      </svg>
                      <svg
                        v-else
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="2"
                      >
                        <rect x="2" y="5" width="20" height="14" rx="2" />
                        <path d="M2 10h20" />
                      </svg>
                    </span>
                    <span class="login-feature__label">{{ item.label }}</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>

          <div class="login-stage__main" :class="{ 'is-shake': loginError }">
            <h2 id="login-title">登录</h2>
            <p class="login-lead">
              <strong>租户管理员</strong> · 使用账号密码进入后台
            </p>

            <form class="login-form" @submit.prevent="handleAdminLogin">
              <div class="form-group login-form-group">
                <label>管理员账号</label>
                <div class="input-box input-box--el">
                  <el-input
                    v-model="loginUsername"
                    placeholder="请输入账号"
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
                        stroke-width="2"
                      >
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                        <circle cx="12" cy="7" r="4" />
                      </svg>
                    </template>
                  </el-input>
                </div>
              </div>

              <div class="form-group login-form-group">
                <label>登录密码</label>
                <div class="input-box input-box--el">
                  <el-input
                    v-model="loginPassword"
                    type="password"
                    placeholder="请输入密码"
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
                        stroke-width="2"
                      >
                        <rect x="3" y="11" width="18" height="11" rx="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    </template>
                  </el-input>
                </div>
              </div>

              <div class="form-extras">
                <el-checkbox v-model="rememberLogin" class="login-remember-el">记住登录</el-checkbox>
              </div>

              <button type="submit" class="btn-submit" :disabled="loginLoading">
                <template v-if="!loginLoading">进入管理台</template>
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
                    aria-hidden="true"
                  >
                    <path
                      d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4"
                    />
                  </svg>
                  正在登录…
                </template>
              </button>
            </form>
          </div>
        </article>
        <p class="login-footer">© 2026 火源网络科技</p>
      </div>
    </div>
  </div>
</template>
