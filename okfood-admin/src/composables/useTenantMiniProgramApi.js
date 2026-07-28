/**
 * 租户小程序管理 API（品牌 / 授权 / 代码发布）
 * 供独立页面复用，避免各页重复拼装路径。
 */
import { apiJson } from '../admin/core.js'

/** @param {number | string} tenantId */
export function tenantMiniProgramBase(tenantId) {
  return `/api/admin/system/tenants/${Math.floor(Number(tenantId))}`
}

/** @param {number | string} tenantId */
export function createTenantMiniProgramApi(tenantId) {
  const base = tenantMiniProgramBase(tenantId)
  const authOpts = { auth: true }

  return {
    loadSaasConfig: () => apiJson(`${base}/saas-config`, {}, authOpts),
    patchSaasConfig: (body) =>
      apiJson(`${base}/saas-config`, { method: 'PATCH', body: JSON.stringify(body) }, authOpts),
    loadAuthorizer: () => apiJson(`${base}/wx-authorizer`, {}, authOpts),
    patchAuthorizer: (body) =>
      apiJson(`${base}/wx-authorizer`, { method: 'PATCH', body: JSON.stringify(body) }, authOpts),
    exchangeAuthorizerCode: (authorization_code) =>
      apiJson(
        `${base}/wx-authorizer/exchange-code`,
        { method: 'POST', body: JSON.stringify({ authorization_code }) },
        authOpts,
      ),
    refreshAuthorizerToken: () =>
      apiJson(`${base}/wx-authorizer/refresh`, { method: 'POST', body: '{}' }, authOpts),
    createPreAuthLink: () =>
      apiJson(`${base}/wx-authorizer/pre-auth-link`, { method: 'POST', body: '{}' }, authOpts),
    loadTemplates: () => apiJson('/api/admin/system/wx-open/templates', {}, authOpts),
    loadPublishState: () => apiJson(`${base}/wx-code/publish-state`, {}, authOpts),
    commitCode: (body) =>
      apiJson(`${base}/wx-code/commit`, { method: 'POST', body: JSON.stringify(body) }, authOpts),
    fetchTrialQrcode: (path) => {
      const q = path ? `?path=${encodeURIComponent(path)}` : ''
      return apiJson(`${base}/wx-code/trial-qrcode${q}`, {}, authOpts)
    },
    loadAuditCategories: () => apiJson(`${base}/wx-code/categories`, {}, authOpts),
    submitAudit: (body) =>
      apiJson(`${base}/wx-code/submit-audit`, { method: 'POST', body: JSON.stringify(body) }, authOpts),
    loadAuditStatus: () => apiJson(`${base}/wx-code/audit-status`, {}, authOpts),
    releaseCode: () => apiJson(`${base}/wx-code/release`, { method: 'POST', body: '{}' }, authOpts),
  }
}
