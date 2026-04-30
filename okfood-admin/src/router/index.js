import { createRouter, createWebHistory } from 'vue-router'
import {
  hydrateTokenFromStorage,
  adminAccessToken,
  adminKind,
  registerAdminRouter,
} from '../admin/core.js'

const LoginView = () => import('../views/LoginView.vue')
const AdminLayout = () => import('../layouts/AdminLayout.vue')
const DashboardView = () => import('../views/DashboardView.vue')
const MembersView = () => import('../views/MembersView.vue')
const DeliveryView = () => import('../views/DeliveryView.vue')
const RegionsView = () => import('../views/RegionsView.vue')
const CouriersView = () => import('../views/CouriersView.vue')
const FinanceView = () => import('../views/FinanceView.vue')
const MenuView = () => import('../views/MenuView.vue')
const WeeklyMenuView = () => import('../views/WeeklyMenuView.vue')
const CardOrdersView = () => import('../views/CardOrdersView.vue')
const StoreConfigView = () => import('../views/StoreConfigView.vue')
const SfOrdersMonitorView = () => import('../views/SfOrdersMonitorView.vue')

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { guest: true },
    },
    {
      path: '/',
      component: AdminLayout,
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: () => {
            hydrateTokenFromStorage()
            return { name: adminKind.value === 'delivery' ? 'regions' : 'dashboard' }
          },
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: '今日营业概览', hidePageTitle: true, fullAdminOnly: true },
        },
        {
          path: 'users',
          name: 'users',
          component: MembersView,
          meta: { title: '会员档案库', fullAdminOnly: true },
        },
        {
          path: 'card-orders',
          name: 'card-orders',
          component: CardOrdersView,
          meta: { title: '开卡工单', fullAdminOnly: true },
        },
        {
          path: 'delivery',
          name: 'delivery',
          component: DeliveryView,
          meta: { title: '智能配送大表', fullAdminOnly: true },
        },
        { path: 'regions', name: 'regions', component: RegionsView, meta: { title: '配送区域管理' } },
        { path: 'couriers', name: 'couriers', component: CouriersView, meta: { title: '配送员管理' } },
        {
          path: 'delivery-sf-orders',
          name: 'delivery-sf-orders',
          component: SfOrdersMonitorView,
          meta: { title: '顺丰订单监控' },
        },
        {
          path: 'finance',
          name: 'finance',
          component: FinanceView,
          meta: { title: '财务中心', fullAdminOnly: true },
        },
        {
          path: 'menu',
          name: 'menu',
          component: MenuView,
          meta: { title: '菜品管理', fullAdminOnly: true },
        },
        {
          path: 'weekly-menu',
          name: 'weekly-menu',
          component: WeeklyMenuView,
          meta: { title: '本周菜单', fullAdminOnly: true },
        },
        {
          path: 'store-config',
          name: 'store-config',
          component: StoreConfigView,
          meta: { title: '门店配置', fullAdminOnly: true },
        },
      ],
    },
  ],
})

registerAdminRouter(router)

router.beforeEach((to) => {
  hydrateTokenFromStorage()
  const hasToken = Boolean(String(adminAccessToken.value || '').trim())
  if (to.meta.requiresAuth && !hasToken) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && hasToken) {
    return { name: adminKind.value === 'delivery' ? 'regions' : 'dashboard' }
  }
  if (hasToken && to.meta.fullAdminOnly && adminKind.value === 'delivery') {
    return { name: 'regions', replace: true }
  }
  return true
})

export default router
