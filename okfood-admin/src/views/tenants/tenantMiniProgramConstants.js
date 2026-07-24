/**
 * 租户小程序 SaaS 表单常量（品牌配置 / 首页 layout）
 * 与后端 HOME_LAYOUT_PRESETS、DEFAULT_FEATURES 对齐。
 */

export const HOME_LAYOUT_PRESETS = [
  { value: 'standard-default', label: '标准（Banner+登录+会员卡+推荐）' },
  { value: 'standard-minimal', label: '极简（Banner+登录+点单按钮）' },
  { value: 'standard-catalog', label: '目录（Banner+宫格+主推）' },
]

export const FEATURE_KEYS = [
  { key: 'douyinRedeem', label: '抖音核销' },
  { key: 'courierMode', label: '骑手模式' },
  { key: 'membershipCard', label: '会员卡' },
  { key: 'retailMenu', label: '零售菜单' },
  { key: 'leaveManagement', label: '请假管理' },
  { key: 'coupon', label: '优惠券' },
]

/** 抽屉 Tab 名：与 TenantMiniProgramDrawer 保持一致 */
export const MINI_PROGRAM_TABS = {
  brand: 'brand',
  authorizer: 'authorizer',
  publish: 'publish',
}

/** 当前模板库默认 template_id（用户已上传） */
export const DEFAULT_TEMPLATE_ID = 1

export function createEmptyBrandForm() {
  return {
    tenant_code: '',
    app_name: '',
    default_store_id: 1,
    home_template: 'default',
    home_layout_preset: 'standard-default',
    theme_primary_color: '#73B054',
    theme_page_bg: '#f7f5f0',
    features: {},
    share_home_title: '',
    share_order_title: '',
    share_mine_slogan: '',
    legal_agreement_title: '',
    legal_agreement_url: '',
    subscribe_delivery_tmpl_id: '',
  }
}

export function brandFormFromPayload(data) {
  const theme = data?.theme && typeof data.theme === 'object' ? data.theme : {}
  const features = data?.features && typeof data.features === 'object' ? data.features : {}
  const share = data?.share && typeof data.share === 'object' ? data.share : {}
  const legal = data?.legal && typeof data.legal === 'object' ? data.legal : {}
  const form = {
    tenant_code: data?.tenant_code != null ? String(data.tenant_code) : '',
    app_name: data?.app_name != null ? String(data.app_name) : '',
    default_store_id: Number(data?.default_store_id) >= 1 ? Number(data.default_store_id) : 1,
    home_template: data?.home_template || 'default',
    home_layout_preset: data?.home_layout_preset || 'standard-default',
    theme_primary_color: theme.primaryColor || '#73B054',
    theme_page_bg: theme.pageBg || '#f7f5f0',
    features: { ...features },
    share_home_title: share.homeTitle || '',
    share_order_title: share.orderTitle || '',
    share_mine_slogan: share.mineSlogan || '',
    legal_agreement_title: legal.membershipAgreementTitle || '',
    legal_agreement_url: legal.membershipAgreementUrl || '',
    subscribe_delivery_tmpl_id: data?.subscribe_delivery_tmpl_id || '',
  }
  for (const f of FEATURE_KEYS) {
    if (form.features[f.key] === undefined) {
      form.features[f.key] = f.key !== 'douyinRedeem'
    }
  }
  return form
}

export function brandPayloadFromForm(form) {
  const code = String(form.tenant_code || '').trim()
  return {
    tenant_code: code || null,
    app_name: String(form.app_name || '').trim() || null,
    default_store_id: Math.max(1, Math.floor(Number(form.default_store_id) || 1)),
    home_template: String(form.home_template || 'default').trim() || 'default',
    home_layout_preset: form.home_layout_preset || 'standard-default',
    theme: {
      primaryColor: String(form.theme_primary_color || '').trim() || '#73B054',
      pageBg: String(form.theme_page_bg || '').trim() || '#f7f5f0',
    },
    features: { ...form.features },
    share: {
      homeTitle: String(form.share_home_title || '').trim(),
      orderTitle: String(form.share_order_title || '').trim(),
      mineSlogan: String(form.share_mine_slogan || '').trim(),
    },
    legal: {
      membershipAgreementTitle: String(form.legal_agreement_title || '').trim(),
      membershipAgreementUrl: String(form.legal_agreement_url || '').trim(),
    },
    subscribe_delivery_tmpl_id: String(form.subscribe_delivery_tmpl_id || '').trim() || null,
  }
}

/** 默认体验版版本号：年月日时分 */
export function defaultUserVersion() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}`
}
