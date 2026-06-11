const MEMBER_LIST = [
  {
    pagePath: '/pages/home/index',
    text: '首页',
    iconPath: '/static/home-nor.png',
    selectedIconPath: '/static/home-sel.png',
  },
  {
    pagePath: '/pages/order/index',
    text: '点单',
    iconPath: '/static/caidan-nor.png',
    selectedIconPath: '/static/caidan-sel.png',
  },
  {
    pagePath: '/pages/orders/index',
    text: '订单',
    iconPath: '/static/order-nor.png',
    selectedIconPath: '/static/order-sel.png',
  },
  {
    pagePath: '/pages/mine/index',
    text: '我的',
    iconPath: '/static/mine-nor.png',
    selectedIconPath: '/static/mine-sel.png',
  },
]

/** 骑手侧 tab 文案与 list 由各 tab 页 onShow 调用的 syncCustomTabBar 注入（见 utils/customTabBar.js） */

Component({
  data: {
    selected: 0,
    role: 'member',
    list: MEMBER_LIST,
  },
  methods: {
    onTap(e) {
      const { url, index } = e.currentTarget.dataset
      const i = Number(index)
      if (Number.isNaN(i)) return
      if (this.data.selected === i) return
      // 不在此 setData：由目标页 onShow → syncCustomTabBar 统一更新，减少与 switchTab 竞态导致的基础库 timeout
      wx.switchTab({ url })
    },
  },
})
