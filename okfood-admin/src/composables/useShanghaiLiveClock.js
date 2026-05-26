import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 后台顶栏全局电子钟（上海时区）。
 * HH:mm:ss + 本地化日期文案，每秒刷新。
 */
export function useShanghaiLiveClock() {
  const liveClockHm = ref('00:00:00')
  const liveClockDate = ref('')
  /** @type {number | null} */
  let timer = null

  function tickLiveClock() {
    const now = new Date()
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Shanghai',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    }).formatToParts(now)
    const h = parts.find((p) => p.type === 'hour')?.value ?? '00'
    const m = parts.find((p) => p.type === 'minute')?.value ?? '00'
    const s = parts.find((p) => p.type === 'second')?.value ?? '00'
    liveClockHm.value = `${h}:${m}:${s}`

    /** zh-CN 的 .format() 会带出「年月日」字面量，不可再拼接「年」「月」「日」，否则成双 */
    const dateParts = new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
    }).formatToParts(now)
    const y = dateParts.find((p) => p.type === 'year')?.value ?? ''
    const mo = dateParts.find((p) => p.type === 'month')?.value ?? ''
    const da = dateParts.find((p) => p.type === 'day')?.value ?? ''
    liveClockDate.value = `${y}年${mo}月${da}日`
  }

  onMounted(() => {
    tickLiveClock()
    timer = window.setInterval(tickLiveClock, 1000)
  })

  onUnmounted(() => {
    if (timer != null) {
      window.clearInterval(timer)
      timer = null
    }
  })

  return { liveClockHm, liveClockDate }
}
