/** 单次零售新订单：浏览器语音播报（配合系统消息轮询） */

const RETAIL_ORDER_KINDS = new Set(['single_meal_order_paid', 'store_retail_order_paid'])
const ALERT_TEXT = '您有新的订单，请及时处理。'

let baselineReady = false
/** @type {Set<number>} */
const announcedIds = new Set()

export function resetRetailOrderVoiceAlertState() {
  baselineReady = false
  announcedIds.clear()
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
}

function pickZhVoice() {
  const voices = window.speechSynthesis?.getVoices?.() || []
  return (
    voices.find((v) => v.lang === 'zh-CN' && !v.localService === false) ||
    voices.find((v) => v.lang.startsWith('zh')) ||
    null
  )
}

function speakRetailOrderAlert() {
  if (typeof window === 'undefined' || !window.speechSynthesis) return

  const run = () => {
    try {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(ALERT_TEXT)
      utterance.lang = 'zh-CN'
      utterance.rate = 1
      const voice = pickZhVoice()
      if (voice) utterance.voice = voice
      window.speechSynthesis.speak(utterance)
    } catch {
      /* 部分环境不支持 TTS，静默跳过 */
    }
  }

  if (window.speechSynthesis.getVoices().length === 0) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null
      run()
    }
  } else {
    run()
  }
}

/**
 * 在系统消息拉取成功后调用：首次拉取只建基线不播报，之后对新到的未确认零售订单播报一次。
 * @param {Array<{ id?: number, kind?: string, acknowledged_at?: string | null }>} items
 */
export function handleRetailOrderNotifications(items) {
  if (typeof window === 'undefined' || !window.speechSynthesis) return

  const retailUnacked = (Array.isArray(items) ? items : []).filter(
    (n) => RETAIL_ORDER_KINDS.has(n?.kind) && !n?.acknowledged_at,
  )

  if (!baselineReady) {
    retailUnacked.forEach((n) => {
      const id = Number(n?.id)
      if (Number.isFinite(id) && id > 0) announcedIds.add(id)
    })
    baselineReady = true
    return
  }

  const hasNew = retailUnacked.some((n) => {
    const id = Number(n?.id)
    return Number.isFinite(id) && id > 0 && !announcedIds.has(id)
  })

  if (!hasNew) return

  retailUnacked.forEach((n) => {
    const id = Number(n?.id)
    if (Number.isFinite(id) && id > 0) announcedIds.add(id)
  })
  speakRetailOrderAlert()
}
