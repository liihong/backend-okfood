/** 与 `custom-tab-bar/index.wxss` 中 `.tab-bar` 高度一致 */
const CUSTOM_TAB_BAR_HEIGHT_PX = 48

/**
 * 须与 `custom-tab-bar/index.js` 内 MEMBER_LIST / RIDER_LIST 保持字段一致（改路由或文案时同步改两处）。
 * 合并进单次 setData，避免 observers 二次 setData 与 switchTab 叠在一起触发基础库 Error: timeout。
 */
const TAB_BAR_MEMBER_LIST = [
  {
    pagePath: '/pages/order/index',
    text: '菜单',
    iconPath: '/static/caidan-nor.png',
    selectedIconPath: '/static/caidan-sel.png',
  },
  {
    pagePath: '/pages/mine/index',
    text: '我的',
    iconPath: '/static/mine-nor.png',
    selectedIconPath: '/static/mine-sel.png',
  },
]

const TAB_BAR_RIDER_LIST = [
  {
    pagePath: '/pages/courier/dashboard',
    text: '配送单',
    iconPath: '/static/caidan-nor.png',
    selectedIconPath: '/static/caidan-sel.png',
  },
  {
    pagePath: '/pages/courier/profile',
    text: '我的',
    iconPath: '/static/mine-nor.png',
    selectedIconPath: '/static/mine-sel.png',
  },
]

/**
 * 自定义 tab 为 fixed 贴底时，scroll-view / 内容区需预留的底部高度（栏高 + 安全区）。
 */
export function getCustomTabBarBottomReservePx() {
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const inset = Number(win.safeAreaInsets?.bottom) || 0
  return CUSTOM_TAB_BAR_HEIGHT_PX + inset
}

function applyCustomTabBarPatch(tabBar, patch) {
  const run = () => {
    try {
      tabBar.setData(patch)
    } catch (e) {
      console.warn('[syncCustomTabBar] setData', e)
    }
  }
  if (typeof wx !== 'undefined' && typeof wx.nextTick === 'function') {
    wx.nextTick(run)
  } else {
    setTimeout(run, 0)
  }
}

/**
 * 微信小程序自定义 tabBar：在 tab 页的 onShow 里同步选中态与身份对应的两个 tab。
 * 非小程序端为 no-op。
 */
export function syncCustomTabBar() {
  // #ifdef MP-WEIXIN
  const stack = getCurrentPages()
  if (!stack.length) return
  const cur = stack[stack.length - 1]
  if (typeof cur.getTabBar !== 'function' || !cur.getTabBar()) return
  const route = String(cur.route || '')
  let role = 'member'
  let selected = 0
  if (route.startsWith('pages/courier/') || route.startsWith('pages/rider/')) {
    role = 'rider'
    selected = route.includes('profile') ? 1 : 0
  } else {
    role = 'member'
    selected = route.includes('mine') ? 1 : 0
  }
  const list = role === 'rider' ? TAB_BAR_RIDER_LIST : TAB_BAR_MEMBER_LIST
  applyCustomTabBarPatch(cur.getTabBar(), { selected, role, list })
  // #endif
}
