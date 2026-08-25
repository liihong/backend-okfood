/** 预设打印模板 catalog（与后端 PRINT_TEMPLATES 一致） */
export const PRINT_TEMPLATES = [
  {
    key: 'delivery_meal_full',
    scene: 'delivery_sheet',
    name: '备餐面单（推荐）',
    description: '顺丰同城风格 76×130：门店名、条码、订单号/片区/会员/餐别/备注/tips',
  },
  {
    key: 'delivery_standard',
    scene: 'delivery_sheet',
    name: '标准备餐标签',
    description: '顶部片区、地址、姓名、份数、备注',
  },
  {
    key: 'delivery_compact',
    scene: 'delivery_sheet',
    name: '紧凑标签',
    description: '适合 80×60mm',
  },
  {
    key: 'delivery_large_region',
    scene: 'delivery_sheet',
    name: '大字片区',
    description: '片区突出便于分拣',
  },
  {
    key: 'delivery_enjoy_meal',
    scene: 'delivery_sheet',
    name: '用餐愉快袋贴',
    description: '竖版袋贴：姓名/餐别大字、食用提示、日期、扫码加好友（建议 60×90mm）',
    tenant_ids: [3],
  },
  {
    key: 'delivery_meal_full',
    scene: 'store_retail',
    name: '备餐面单（推荐）',
    description: '与配送标签同款 76×130：订单号/片区/会员/餐品/备注/tips',
  },
  {
    key: 'retail_delivery',
    scene: 'store_retail',
    name: '商城配送标签（旧）',
    description: '配送到家',
  },
  {
    key: 'retail_pickup',
    scene: 'store_retail',
    name: '商城自提标签',
    description: '门店自提',
  },
  {
    key: 'retail_simple',
    scene: 'store_retail',
    name: '简洁商品标签',
    description: '商品+数量+联系人',
  },
]

/**
 * @param {string} scene
 * @param {number|null|undefined} tenantId 当前租户；有 tenant_ids 的模板仅对该租户展示
 */
export function templatesForScene(scene, tenantId) {
  const tid = Number(tenantId)
  const hasTid = Number.isFinite(tid) && tid > 0
  return PRINT_TEMPLATES.filter((t) => {
    if (t.scene !== scene) return false
    const allowed = Array.isArray(t.tenant_ids) ? t.tenant_ids : null
    if (allowed && allowed.length) {
      // 租户未知时仍展示，避免租户 3 因品牌接口未带回 tenant_id 而看不到选项
      if (hasTid && !allowed.includes(tid)) return false
    }
    return true
  })
}

/** 场景默认模板：catalog 中该场景第一项（推荐） */
export function defaultTemplateForScene(scene) {
  return templatesForScene(scene)[0]?.key || 'delivery_meal_full'
}
