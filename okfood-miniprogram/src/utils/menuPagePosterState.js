import { ref } from 'vue'

/** 菜单页海报弹窗是否可见 */
export const menuPagePosterVisible = ref(false)

/** 菜单页海报图片 URL */
export const menuPagePosterImageUrl = ref('')

/** @param {string} imageUrl */
export function showMenuPagePosterModal(imageUrl) {
  const url = String(imageUrl || '').trim()
  if (!url) return
  menuPagePosterImageUrl.value = url
  menuPagePosterVisible.value = true
}

export function hideMenuPagePosterModal() {
  menuPagePosterVisible.value = false
}
