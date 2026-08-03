import { todayShanghaiStr } from '../../views/orders/utils/orderFormatters.js'

/**
 * 打印设置页测试用样例数据（始终 1 张）
 * @param {'delivery_sheet'|'store_retail'} scene
 * @param {string} templateKey
 * @param {string} storeName
 */
export function buildTestLabelItems(scene, templateKey, storeName) {
  const store = String(storeName || 'OK饭').trim() || 'OK饭'
  const deliveryDate = todayShanghaiStr()

  if (scene === 'store_retail') {
    return [
      {
        region: '东区',
        address: '3号楼502室',
        name: '李女士',
        phone_tail: '6633',
        units: 1,
        remark: '测试打印',
        delivery_date: deliveryDate,
        product_title: '测试商品',
        order_no: 'TEST',
        store_pickup: templateKey === 'retail_pickup',
      },
    ]
  }

  if (templateKey === 'delivery_meal_full') {
    return [
      {
        region: '中心医院',
        store_name: store,
        name: '李女士',
        phone_masked: '132****6633',
        meal_category: '午晚餐卡',
        units: 1,
        remark: '少辣（测试）',
        delivery_date: deliveryDate,
        shop_order_id: 'OKF20260724c69a199b60ca4',
        sf_order_id: 'SF6504306526672',
        product_title: '',
        order_no: 'OKF20260724c69a19474d0329b60ca4',
        store_pickup: false,
      },
    ]
  }

  return [
    {
      region: '东区',
      address: '3号楼502室',
      name: '李女士',
      phone_tail: '6633',
      units: 1,
      remark: '测试打印',
      delivery_date: deliveryDate,
      product_title: '',
      order_no: '',
      store_pickup: false,
    },
  ]
}
