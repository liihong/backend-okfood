/** 路由 name → KeepAlive include 用的组件名（与各 View 的 defineOptions.name 一致） */
export const ADMIN_TAB_COMPONENT_NAMES = {
  dashboard: 'DashboardView',
  users: 'MembersView',
  'card-orders': 'CardOrdersView',
  orders: 'OrdersManageView',
  delivery: 'DeliveryView',
  regions: 'RegionsView',
  couriers: 'CouriersView',
  'delivery-sf-orders': 'SfOrdersMonitorView',
  finance: 'FinanceView',
  menu: 'MenuView',
  'weekly-menu': 'WeeklyMenuView',
  'store-config': 'StoreConfigView',
  'system-tenants': 'TenantsView',
  'system-membership-templates': 'MembershipTemplatesView',
  'system-retail-catalog': 'RetailCatalogView',
}

export const ADMIN_TABS_MAX_CACHE = 10
