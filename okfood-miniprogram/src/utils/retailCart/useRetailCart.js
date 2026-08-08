import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  getCartItems,
  getCartCount,
  getCartSubtotalText,
  readCartItemsRaw,
} from './retailCartStorage.js'

/** 本地购物车 composable */
export function useRetailCart() {
  const tick = ref(0)
  const items = computed(() => {
    tick.value
    return getCartItems()
  })
  const count = computed(() => {
    tick.value
    return getCartCount()
  })
  const subtotalText = computed(() => {
    tick.value
    return getCartSubtotalText()
  })
  const visible = computed(() => count.value > 0)

  function refresh() {
    tick.value += 1
  }

  function onStorage() {
    refresh()
  }

  onMounted(() => {
    uni.$on('retail-cart-changed', onStorage)
  })
  onUnmounted(() => {
    uni.$off('retail-cart-changed', onStorage)
  })

  return { items, count, subtotalText, visible, refresh }
}

/** 通知购物车 UI 刷新 */
export function notifyRetailCartChanged() {
  uni.$emit('retail-cart-changed')
  // 兼容无 uni.$emit 场景
  try {
    readCartItemsRaw()
  } catch {
    /* ignore */
  }
}
