<template>
  <EntryPosterModal
    :visible="modalVisible"
    :image-url="modalImageUrl"
    @update:visible="onVisibleChange"
    @close="onClose"
  />
</template>

<script setup>
import { computed } from 'vue'
import EntryPosterModal from '@/components/EntryPosterModal/EntryPosterModal.vue'
import {
  menuPagePosterVisible,
  menuPagePosterImageUrl,
  hideMenuPagePosterModal,
} from '@/utils/menuPagePosterState.js'

const modalVisible = computed(() => !!menuPagePosterVisible.value)
const modalImageUrl = computed(() => String(menuPagePosterImageUrl.value || ''))

function onVisibleChange(v) {
  if (!v) hideMenuPagePosterModal()
}

function onClose() {
  hideMenuPagePosterModal()
}
</script>
