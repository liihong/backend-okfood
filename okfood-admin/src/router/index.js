import { createRouter, createWebHistory } from 'vue-router'
import {
  hydrateTokenFromStorage,
  adminAccessToken,
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
const CardOrdersView = () => import('../views/CardOrdersView.vue')

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
        { path: '', redirect: { name: 'dashboard' } },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: { title: '今日营业概览' },
        },
        { path: 'users', name: 'users', component: MembersView, meta: { title: '会员档案库' } },
        {
          path: 'card-orders',
          name: 'card-orders',
          component: CardOrdersView,
          meta: { title: '开卡工单' },
        },
        { path: 'delivery', name: 'delivery', component: DeliveryView, meta: { title: '智能配送大表' } },
        { path: 'regions', name: 'regions', component: RegionsView, meta: { title: '配送区域' } },
        { path: 'couriers', name: 'couriers', component: CouriersView, meta: { title: '配送员管理' } },
        { path: 'finance', name: 'finance', component: FinanceView, meta: { title: '财务中心' } },
        { path: 'menu', name: 'menu', component: MenuView, meta: { title: '菜品管理' } },
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
    return { name: 'dashboard' }
  }
  return true
})

export default router
