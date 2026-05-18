import { ref, watch, onScopeDispose } from 'vue'

/**
 * 整数从当前显示值缓动过渡到新目标（ease-out cubic），适用于加载或刷新后的数字滚动效果。
 * @param {() => number | null | undefined} targetGetter
 * @param {{ duration?: number, idleValue?: number }} [options] duration 毫秒；无目标时内部归零到 idleValue（模板应对 null 单独展示「—」）
 * @returns {import('vue').Ref<number>}
 */
export function useAnimatedInteger(targetGetter, options = {}) {
  const duration = typeof options.duration === 'number' ? options.duration : 720
  const idleValue = typeof options.idleValue === 'number' ? options.idleValue : 0

  const displayed = ref(idleValue)
  let rafId = 0
  let animToken = 0

  function cancelRaf() {
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = 0
    }
  }

  /**
   * @param {number} from
   * @param {number} to
   * @param {number} token
   */
  function runAnimate(from, to, token) {
    if (from === to) {
      displayed.value = to
      return
    }
    const start = performance.now()
    const step = (now) => {
      if (token !== animToken) return
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - (1 - t) ** 3
      displayed.value = Math.round(from + (to - from) * eased)
      if (t < 1) {
        rafId = requestAnimationFrame(step)
      } else {
        displayed.value = to
        rafId = 0
      }
    }
    rafId = requestAnimationFrame(step)
  }

  watch(
    targetGetter,
    (raw) => {
      cancelRaf()
      animToken += 1
      const token = animToken

      if (raw == null || Number.isNaN(Number(raw))) {
        displayed.value = idleValue
        return
      }
      const to = Math.round(Number(raw))
      const from = displayed.value
      runAnimate(from, to, token)
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    cancelRaf()
    animToken += 1
  })

  return displayed
}
