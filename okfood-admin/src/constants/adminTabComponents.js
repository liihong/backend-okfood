/**
 * 配送工作台三联页路由名（进入任一页时自动在顶栏钉住另外两页，顺序固定）
 * 仅 AdminLayout 中 showFullAdminMenus 为 true 时启用（店主/客服；不含配送专员）
 */
export const ADMIN_DELIVERY_WORKBENCH_TRIAD = [
  'delivery',
  'regions',
  'delivery-range-check',
]

/** 路由 name → KeepAlive include 用的组件名（与各 View 的 defineOptions.name 一致） */
export const ADMIN_TAB_COMPONENT_NAMES = {
  dashboard: 'DashboardView',
  users: 'MembersView',
  'card-orders': 'CardOrdersView',
  orders: 'OrdersManageView',
  delivery: 'DeliveryView',
  regions: 'RegionsView',
  'delivery-range-check': 'DeliveryRangeCheckView',
  couriers: 'CouriersView',
  'delivery-sf-orders': 'SfOrdersMonitorView',
  'delivery-geo-map': 'DeliveryGeoMapView',
  finance: 'FinanceView',
  menu: 'MenuView',
  'weekly-menu': 'WeeklyMenuView',
  'store-config': 'StoreConfigView',
  'system-tenants': 'TenantsView',
  'system-membership-templates': 'MembershipTemplatesView',
  'system-retail-catalog': 'RetailCatalogView',
  'system-dish-categories': 'DishCategoriesView',
  'marketing-coupon-templates': 'CouponTemplatesView',
  'marketing-member-coupons': 'MemberCouponGrantsView',
  'marketing-douyin-products': 'DouyinProductMappingsView',
  'marketing-douyin-redemptions': 'DouyinRedemptionsView',
}

export const ADMIN_TABS_MAX_CACHE = 10
