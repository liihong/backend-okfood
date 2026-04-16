import { ref } from 'vue'

const toastOpen = ref(false)
const toastText = ref('')
const toastKind = ref('success')
let toastTimer = 0

/** @param {'success' | 'error'} kind */
export function showToast(msg, kind = 'success') {
  toastText.value = msg
  toastKind.value = kind
  toastOpen.value = true
  window.clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => {
    toastOpen.value = false
  }, kind === 'error' ? 3200 : 2600)
}

export function useToast() {
  return { toastOpen, toastText, toastKind, showToast }
}
