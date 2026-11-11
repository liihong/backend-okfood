import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import './style.css'
import './assets/admin-ui.css'
import './assets/login-glass.css'
import './assets/element-plus-okfood-theme.css'
import './assets/okfood-el-glass-message.css'
import './assets/okfood-el-glass-messagebox.css'
import App from './App.vue'
import router from './router'
import { escClose } from './directives/escClose.js'

/** 与 layouts/AdminLayout 一致：首屏即挂上 data-admin-theme，避免无属性时主题变量不生效 */
const ADMIN_THEME_STORAGE_KEY = 'okfood-admin-primary-theme'
const PREVIEW_THEME_LEGACY_KEY = 'okfood-admin-ios-glass-primary-theme'
const ADMIN_THEME_VALID = new Set([
  'primary-peach',
  'primary-mojito',
  'primary-iris',
  'primary-sky',
  'primary-lagoon',
  'primary-apricot',
  'primary-berry',
  'primary-caramel',
  'primary-indigo',
  'primary-sakura',
])

function readInitialAdminTheme() {
  try {
    let t = localStorage.getItem(ADMIN_THEME_STORAGE_KEY)
    if (t && ADMIN_THEME_VALID.has(t)) return t
    const leg = localStorage.getItem(PREVIEW_THEME_LEGACY_KEY)
    if (leg && ADMIN_THEME_VALID.has(leg)) return leg
  } catch {
    /* ignore */
  }
  /* 与 design 定稿一致：首访默认蜜桃珊瑚 */
  return 'primary-peach'
}

if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-admin-theme', readInitialAdminTheme())
}

/** 登录页/公开页不使用管理壳；壳内锁定 document 滚动，由主内容区内部滚动（见 admin-ui.css html.okfood-admin-shell） */
function syncAdminShellClass(route) {
  const isShell = route.matched.length > 0 && route.matched[0].path === '/'
  document.documentElement.classList.toggle('okfood-admin-shell', isShell)
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
router.afterEach((to) => {
  syncAdminShellClass(to)
})
router.isReady().then(() => {
  syncAdminShellClass(router.currentRoute.value)
})
app.directive('esc-close', escClose)
app.mount('#app')
