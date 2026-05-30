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
const OrdersManageView = () => import('../views/OrdersManageView.vue')
const StoreConfigView = () => import('../views/StoreConfigView.vue')
const SfOrdersMonitorView = () => import('../views/SfOrdersMonitorView.vue')
const DeliveryGeoMapView = () => import('../views/DeliveryGeoMapView.vue')
const TenantsView = () => import('../views/TenantsView.vue')
const MembershipTemplatesView = () => import('../views/MembershipTemplatesView.vue')
const RetailCatalogView = () => import('../views/RetailCatalogView.vue')
const DeliveryRangeCheckView = () => import('../views/DeliveryRangeCheckView.vue')

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
            if (adminKind.value === 'delivery') return { name: 'regions' }
            if (adminKind.value === 'system') return { name: 'system-tenants' }
            return { name: 'dashboard' }
          },
        },
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView,
          meta: {
            title: '今日营业概览',
            pageSubtitle: '总览今日与明日备餐、请假与卡到期，以及片区会员覆盖分布',
            hidePageTitle: true,
            fullAdminOnly: true,
          },
        },
        {
          path: 'users',
          name: 'users',
          component: MembersView,
          meta: {
            title: '会员档案库',
            pageSubtitle: '检索、导出与维护会员资料、套餐周期、配送地址及业务状态',
            fullAdminOnly: true,
          },
        },
        {
          path: 'card-orders',
          name: 'card-orders',
          component: CardOrdersView,
          meta: {
            title: '开卡工单',
            pageSubtitle: '新建与跟踪线下/微信开卡，管理缴费、入账同步与起送日期',
            fullAdminOnly: true,
          },
        },
        {
          path: 'orders',
          name: 'orders',
          component: OrdersManageView,
          meta: {
            title: '订单管理',
            pageSubtitle: '单次点餐按供餐日、商城卡包按下单日查看工单；零售 SKU 订单待业务接入后展示',
            fullAdminOnly: true,
          },
        },
        {
          path: 'delivery',
          name: 'delivery',
          component: DeliveryView,
          meta: {
            title: '智能配送大表',
            pageSubtitle: '精细化管理每日配餐、自提、请假及顺丰履约调度',
            fullAdminOnly: true,
          },
        },
        { path: 'regions', name: 'regions', component: RegionsView, meta: { title: '配送区域管理' } },
        {
          path: 'delivery-range-check',
          name: 'delivery-range-check',
          component: DeliveryRangeCheckView,
          meta: {
            title: '配送资质检验',
            pageSubtitle: '依据配送区域多边形判断是否在服务范围内（不含第三方承运口径）',
          },
        },
        { path: 'couriers', name: 'couriers', component: CouriersView, meta: { title: '配送员管理' } },
        {
          path: 'delivery-sf-orders',
          name: 'delivery-sf-orders',
          component: SfOrdersMonitorView,
          meta: { title: '顺丰订单监控' },
        },
        {
          path: 'delivery-geo-map',
          name: 'delivery-geo-map',
          component: DeliveryGeoMapView,
          meta: {
            title: '实时地理分布',
            pageSubtitle: '会员分布与送达状态地图（预留页面，侧栏暂不展示入口）',
            fullAdminOnly: true,
            hidePageTitle: true,
          },
        },
        {
          path: 'finance',
          name: 'finance',
          component: FinanceView,
          meta: { title: '财务中心', ownerAdminOnly: true, hidePageTitle: true },
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
          meta: { title: '本周菜单', fullAdminOnly: true, hidePageTitle: true },
        },
        {
          path: 'store-config',
          name: 'store-config',
          component: StoreConfigView,
          meta: { title: '门店配置', ownerAdminOnly: true },
        },
        {
          path: 'system/tenants',
          name: 'system-tenants',
          component: TenantsView,
          meta: { title: '租户管理', systemAdminOnly: true },
        },
        {
          path: 'system/membership-templates',
          name: 'system-membership-templates',
          component: MembershipTemplatesView,
          meta: { title: '会员卡管理', ownerAdminOnly: true, hidePageTitle: true },
        },
        {
          path: 'system/retail-catalog',
          name: 'system-retail-catalog',
          component: RetailCatalogView,
          meta: { title: '普通商品管理', ownerAdminOnly: true, hidePageTitle: true },
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
    if (adminKind.value === 'delivery') return { name: 'regions' }
    if (adminKind.value === 'system') return { name: 'system-tenants' }
    return { name: 'dashboard' }
  }
  const isSystemAdminRoute = to.matched.some((record) => record.meta.systemAdminOnly)
  if (hasToken && isSystemAdminRoute && adminKind.value !== 'system') {
    return { name: 'dashboard', replace: true }
  }
  if (hasToken && adminKind.value === 'system' && !isSystemAdminRoute) {
    return { name: 'system-tenants', replace: true }
  }
  if (hasToken && to.meta.ownerAdminOnly) {
    if (adminKind.value === 'delivery') {
      return { name: 'regions', replace: true }
    }
    if (adminKind.value === 'support') {
      return { name: 'dashboard', replace: true }
    }
  }
  if (hasToken && to.meta.fullAdminOnly && adminKind.value === 'delivery') {
    return { name: 'regions', replace: true }
  }
  return true
})

export default router
