/** 底部固定按钮栏（地址列表、购卡详情等）预留高度 */
export const FIXED_FOOTER_RESERVE_PX = 100

/** 订单 Tab：主分类 + 状态横滑条（导航栏下方）预留高度 */
export const ORDERS_TAB_HEADER_CHROME_PX = 118

/**
 * 微信小程序自定义导航栏：用状态栏高度 + 胶囊位置计算 scroll-view 可用高度（px）。
 * @param {number} [extraBottomPxArg] 固定底栏、自定义 tabBar 等占用高度（px）
 * @param {number} [extraTopPxArg] 导航栏下方额外顶栏（如 Tab 内筛选条，px）
 * @returns {{ statusBarHeight: number, navContentHeight: number, navBarTotal: number, menuButtonWidth: number, scrollHeightPx: string }}
 */
export function getNavbarLayout(extraBottomPxArg = 0, extraTopPxArg = 0) {
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const statusBarHeight = win.statusBarHeight || 20
  const windowWidth = win.windowWidth || 375

  let menuTop = statusBarHeight + 4
  let menuHeight = 32
  let menuRightGap = 7

  // #ifdef MP-WEIXIN
  try {
    const rect = uni.getMenuButtonBoundingClientRect()
    if (rect && rect.height) {
      menuTop = rect.top
      menuHeight = rect.height
      menuRightGap = windowWidth - rect.right
    }
  } catch (e) {
    /* 开发者工具偶发异常时用默认值 */
  }
  // #endif

  const navContentHeight = (menuTop - statusBarHeight) * 2 + menuHeight
  const navBarTotal = statusBarHeight + navContentHeight
  const menuButtonWidth = Math.ceil((menuRightGap || 7) + 87)
  const windowHeight = win.windowHeight || win.screenHeight || 667
  const extraBottomPx = Number(extraBottomPxArg) > 0 ? Math.floor(Number(extraBottomPxArg)) : 0
  const extraTopPx = Number(extraTopPxArg) > 0 ? Math.floor(Number(extraTopPxArg)) : 0
  const scrollHeightPx = `${Math.max(160, windowHeight - navBarTotal - extraTopPx - extraBottomPx)}px`

  return {
    statusBarHeight,
    navContentHeight,
    navBarTotal,
    menuButtonWidth,
    scrollHeightPx,
  }
}

/**
 * 子包/内页 scroll-view 的 :style 绑定值。
 * @param {number} [extraBottomPx]
 * @param {number} [extraTopPx]
 */
export function getPageScrollStyle(extraBottomPx = 0, extraTopPx = 0) {
  return { height: getNavbarLayout(extraBottomPx, extraTopPx).scrollHeightPx }
}

/**
 * scroll-view 在 v-if/v-else 下延迟挂载时，真机首帧高度常为 0；多次重算避免白屏。
 * @param {(style: Record<string, string>) => void} apply
 * @param {number} [extraBottomPx]
 * @param {number} [extraTopPx]
 */
export function schedulePageScrollLayout(apply, extraBottomPx = 0, extraTopPx = 0) {
  const run = () => apply(getPageScrollStyle(extraBottomPx, extraTopPx))
  run()
  setTimeout(run, 0)
  setTimeout(run, 80)
}
