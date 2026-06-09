const STORAGE_KEY = 'okfood_menu_fulfill_mode'

/** @returns {'pickup' | 'delivery'} */
export function readMenuFulfillMode() {
  try {
    const v = uni.getStorageSync(STORAGE_KEY)
    return v === 'pickup' ? 'pickup' : 'delivery'
  } catch {
    return 'delivery'
  }
}

/** @param {'pickup' | 'delivery'} mode */
export function writeMenuFulfillMode(mode) {
  try {
    uni.setStorageSync(STORAGE_KEY, mode === 'pickup' ? 'pickup' : 'delivery')
  } catch {
    /* ignore */
  }
}
