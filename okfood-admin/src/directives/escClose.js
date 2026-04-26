/** @type {unique symbol} */
const ESC_CTX = Symbol('okfoodEscClose')

/**
 * 遮罩层在 DOM 中时，按 ESC 执行绑定函数（与点击遮罩关闭一致）。
 * 用法：<div class="modal-overlay" v-esc-close="() => show = false" ...>
 */
export const escClose = {
  mounted(el, binding) {
    const state = { fn: binding.value }
    const handler = (e) => {
      if (e.key !== 'Escape') return
      const fn = state.fn
      if (typeof fn === 'function') fn()
    }
    el[ESC_CTX] = { handler, state }
    window.addEventListener('keydown', handler)
  },
  updated(el, binding) {
    const ctx = el[ESC_CTX]
    if (ctx) ctx.state.fn = binding.value
  },
  unmounted(el) {
    const ctx = el[ESC_CTX]
    if (ctx) {
      window.removeEventListener('keydown', ctx.handler)
      delete el[ESC_CTX]
    }
  },
}
