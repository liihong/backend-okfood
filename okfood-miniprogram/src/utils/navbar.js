/**
 * 微信小程序自定义导航栏：用状态栏高度 + 胶囊位置计算内容区，避免固定写死 px。
 * @returns {{ statusBarHeight: number, navContentHeight: number, navBarTotal: number, menuButtonWidth: number }}
 */
export function getNavbarLayout() {
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

  return {
    statusBarHeight,
    navContentHeight,
    navBarTotal,
    menuButtonWidth,
  }
}
