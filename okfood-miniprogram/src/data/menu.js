/** 周菜单静态数据（后续可改为接口） */
export const WEEKLY_MENU = [
  {
    id: 1,
    day: '周一',
    price: 32,
    name: '黑椒牛排原力碗',
    ingredients:
      '原切牛脊肉、低GI红薯、新鲜西蓝花、水煮蛋、混合生菜、黑椒酱。',
    img: 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400',
  },
  {
    id: 2,
    day: '周二',
    price: 32,
    name: '柠香炙烤深海鱼',
    ingredients: '深海黑鱼片、抗氧蓝莓、鲜橙片、三色糙米、时令时蔬、油醋汁。',
    img: 'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400',
  },
  {
    id: 3,
    day: '周三',
    price: 32,
    name: '大虾肉酱能量面',
    ingredients: 'Q弹大虾、秘制低脂肉酱、全麦意面、圣女果、芝士粉、羽衣甘蓝。',
    img: 'https://via.placeholder.com/300x300?text=OKFood',
  },
  {
    id: 4,
    day: '周四',
    price: 32,
    name: '泰式鸡肉打抛饭',
    ingredients: '罗勒叶、嫩煎鸡胸肉碎、泰式酸辣汁、五谷饭、脆黄瓜、彩椒。',
    img: 'https://via.placeholder.com/300x300?text=OKRice',
  },
  {
    id: 5,
    day: '周五',
    price: 32,
    name: '盐葱鸡腿排能量碗',
    ingredients: '原切鸡腿肉、秘制盐葱酱、杂粮基底、玉米粒、紫甘蓝、迷迭香。',
    img: 'https://via.placeholder.com/300x300?text=OKFine',
  },
  {
    id: 6,
    day: '周六',
    price: 35,
    name: '韩式牛肉杂粮饭',
    ingredients: '鲜嫩肥牛卷、自制韩式辣酱、滑蛋、荞麦粒、白萝卜、新鲜海苔。',
    img: 'https://via.placeholder.com/300x300?text=OKRice',
  },
]

export function getDishById(id) {
  const n = Number(id)
  return WEEKLY_MENU.find((m) => m.id === n) || null
}
