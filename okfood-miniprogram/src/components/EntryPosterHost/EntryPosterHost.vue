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
  entryPosterVisible,
  entryPosterImageUrl,
  hideEntryPosterModal,
} from '@/utils/entryPosterState.js'
import { tryShowMemberCouponReminder } from '@/utils/memberCouponReminder.js'

const modalVisible = computed(() => !!entryPosterVisible.value)
const modalImageUrl = computed(() => String(entryPosterImageUrl.value || ''))

function onVisibleChange(v) {
  if (!v) hideEntryPosterModal()
}

function onClose() {
  hideEntryPosterModal()
  setTimeout(() => {
    void tryShowMemberCouponReminder()
  }, 300)
}
</script>
