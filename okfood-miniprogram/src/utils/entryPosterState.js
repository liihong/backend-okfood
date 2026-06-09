import { ref } from 'vue'

export const entryPosterVisible = ref(false)

/** @type {import('vue').Ref<string>} */
export const entryPosterImageUrl = ref('')

/** @param {string} imageUrl */
export function showEntryPosterModal(imageUrl) {
  const url = String(imageUrl || '').trim()
  if (!url) return
  entryPosterImageUrl.value = url
  entryPosterVisible.value = true
}

export function hideEntryPosterModal() {
  entryPosterVisible.value = false
}
