import { getNavbarLayout } from './navbar.js'

/** 原生 tabBar 大致高度（px）；当 windowHeight 未扣除 tabBar 时用于兜底 */
const WX_TABBAR_RESERVE_PX = 52

/**
 * 文档约定 Tab 页 windowHeight 不含 tabBar，但开发者工具/部分机型首帧会接近整屏，
 * 按此算出的高度会把内容画到 tabBar 下面，看起来像「底栏不在最下」或挡住 tabBar。
 */
function tabPageRootHeightPx(win) {
  let h = Number(win.windowHeight) || 0
  const sh = Number(win.screenHeight) || 0
  if (!h) return 0
  // #ifdef MP-WEIXIN
  if (sh > 0 && h >= sh - 12) {
    h = Math.max(120, h - WX_TABBAR_RESERVE_PX)
  }
  // #endif
  return h
}

/**
 * TabBar 页面布局：用可用窗口高度固定根节点与 scroll-view，避免盖住原生底部栏。
 * @returns {{ pageStyle: Record<string, string>, scrollStyle: Record<string, string> }}
 */
export function getTabPageLayoutStyles() {
  const win = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  const h = tabPageRootHeightPx(win)
  const { navBarTotal } = getNavbarLayout()
  const scrollH = Math.max(0, h - navBarTotal)
  if (!h) {
    return {
      pageStyle: { height: '100%', maxHeight: '100%', overflow: 'hidden' },
      scrollStyle: { flex: '1', minHeight: '0' },
    }
  }
  return {
    pageStyle: {
      height: `${h}px`,
      maxHeight: `${h}px`,
      overflow: 'hidden',
    },
    scrollStyle: {
      height: `${scrollH}px`,
      flex: 'none',
    },
  }
}
