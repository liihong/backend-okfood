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
const OrdersManageView = () => import('../views/orders/OrdersManageView.vue')
const StoreConfigView = () => import('../views/StoreConfigView.vue')
const SfOrdersMonitorView = () => import('../views/SfOrdersMonitorView.vue')
const DeliveryGeoMapView = () => import('../views/DeliveryGeoMapView.vue')
const TenantsView = () => import('../views/TenantsView.vue')
const MembershipTemplatesView = () => import('../views/MembershipTemplatesView.vue')
const RetailCatalogView = () => import('../views/RetailCatalogView.vue')
const DishCategoriesView = () => import('../views/DishCategoriesView.vue')
const DeliveryRangeCheckView = () => import('../views/DeliveryRangeCheckView.vue')
const CouponTemplatesView = () => import('../views/marketing/CouponTemplatesView.vue')
const HomeBannersView = () => import('../views/marketing/HomeBannersView.vue')
const EntryPosterView = () => import('../views/marketing/EntryPosterView.vue')
const MemberCouponGrantsView = () => import('../views/marketing/MemberCouponGrantsView.vue')
const DouyinProductMappingsView = () => import('../views/marketing/douyin/DouyinProductMappingsView.vue')
const DouyinRedemptionsView = () => import('../views/marketing/douyin/DouyinRedemptionsView.vue')

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
            pageSubtitle: '总览今日与明日备餐、请假与当日已过期份数，以及片区会员覆盖分布',
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
            pageSubtitle: '单次点餐按供餐日；商城订单与卡包订单按下单日查看',
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
          path: 'menu/retail-catalog',
          name: 'menu-retail-catalog',
          component: RetailCatalogView,
          meta: { title: '普通商品管理', fullAdminOnly: true, hidePageTitle: true },
        },
        {
          path: 'marketing/home-banners',
          name: 'marketing-home-banners',
          component: HomeBannersView,
          meta: {
            title: '首页 Banner',
            pageSubtitle: '配置小程序首页轮播广告与跳转',
            supportMarketing: true,
          },
        },
        {
          path: 'marketing/entry-poster',
          name: 'marketing-entry-poster',
          component: EntryPosterView,
          meta: {
            title: '进入弹窗海报',
            pageSubtitle: '配置用户进入小程序时的提示海报',
            supportMarketing: true,
          },
        },
        {
          path: 'marketing/coupon-templates',
          name: 'marketing-coupon-templates',
          component: CouponTemplatesView,
          meta: {
            title: '优惠券管理',
            pageSubtitle: '配置小程序代金券券种与适用范围',
            supportMarketing: true,
          },
        },
        {
          path: 'marketing/member-coupons',
          name: 'marketing-member-coupons',
          component: MemberCouponGrantsView,
          meta: {
            title: '优惠券发放',
            pageSubtitle: '向会员发放优惠券并管理记录',
            supportMarketing: true,
          },
        },
        {
          path: 'marketing/douyin-products',
          name: 'marketing-douyin-products',
          component: DouyinProductMappingsView,
          meta: {
            title: '抖音商品设置',
            pageSubtitle: '配置抖音团购商品与本地权益映射',
            supportMarketing: true,
          },
        },
        {
          path: 'marketing/douyin-redemptions',
          name: 'marketing-douyin-redemptions',
          component: DouyinRedemptionsView,
          meta: {
            title: '核销记录查询',
            pageSubtitle: '抖音券验券兑换流水',
            supportMarketing: true,
          },
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
          path: 'system/dish-categories',
          name: 'system-dish-categories',
          component: DishCategoriesView,
          meta: { title: '菜品分类', ownerAdminOnly: true, hidePageTitle: true },
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
  const isOwnerAdminRoute = to.matched.some((record) => record.meta.ownerAdminOnly)
  if (hasToken && isOwnerAdminRoute) {
    if (adminKind.value === 'delivery') {
      return { name: 'regions', replace: true }
    }
    if (adminKind.value === 'support') {
      return { name: 'dashboard', replace: true }
    }
  }
  /** 营业工作台（含小程序营销）：店主与客服可进，仅配送专员拦截 */
  const isStaffWorkbenchRoute = to.matched.some(
    (record) => record.meta.fullAdminOnly || record.meta.supportMarketing,
  )
  if (hasToken && isStaffWorkbenchRoute && adminKind.value === 'delivery') {
    return { name: 'regions', replace: true }
  }
  return true
})

export default router
