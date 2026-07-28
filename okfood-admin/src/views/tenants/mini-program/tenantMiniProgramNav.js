/** 租户小程序管理 · 三页导航（独立路由，替代抽屉 Tab） */

export const TENANT_MINI_PROGRAM_PAGES = [
  {
    name: 'tenant-mini-brand',
    pathSuffix: 'brand',
    label: '品牌与首页',
  },
  {
    name: 'tenant-mini-authorizer',
    pathSuffix: 'authorizer',
    label: '授权',
  },
  {
    name: 'tenant-mini-publish',
    pathSuffix: 'publish',
    label: '代码发布',
  },
]

/** @param {number | string} tenantId @param {string} [tenantName] */
export function tenantMiniProgramRoute(name, tenantId, tenantName) {
  const page = TENANT_MINI_PROGRAM_PAGES.find((p) => p.name === name)
  if (!page) return { name: 'system-tenants' }
  const query = tenantName ? { name: tenantName } : {}
  return {
    name: page.name,
    params: { tenantId: String(Math.floor(Number(tenantId))) },
    query,
  }
}
