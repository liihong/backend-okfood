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
    key: 'retail_delivery',
    scene: 'store_retail',
    name: '商城配送标签',
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

export function templatesForScene(scene) {
  return PRINT_TEMPLATES.filter((t) => t.scene === scene)
}

/** 场景默认模板：catalog 中该场景第一项（推荐） */
export function defaultTemplateForScene(scene) {
  return templatesForScene(scene)[0]?.key || 'delivery_meal_full'
}
