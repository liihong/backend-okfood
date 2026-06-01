<template>
  <OkAlertModal
    v-if="isActiveHost"
    :visible="visible"
    :title="title"
    :content="content"
    :show-cancel="showCancel"
    :cancel-text="cancelText"
    :confirm-text="confirmText"
    :confirm-danger="confirmDanger"
    :tone="tone"
    :mask-closable="maskClosable"
    @confirm="onConfirm"
    @cancel="onCancel"
  />
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkAlertModal from '@/components/OkAlertModal/OkAlertModal.vue'
import {
  okAlertVisible,
  okAlertOptions,
  okAlertActiveHostId,
  registerOkAlertHost,
  unregisterOkAlertHost,
  activateOkAlertHost,
  finishOkAlert,
} from '@/utils/okAlertState.js'

let hostSeq = 0
const hostId = ++hostSeq

function resolveHostRoute() {
  const pages = getCurrentPages()
  const page = pages[pages.length - 1]
  return page?.route ? String(page.route) : ''
}

const isActiveHost = computed(() => okAlertActiveHostId.value === hostId)
const visible = computed(() => !!okAlertVisible.value && isActiveHost.value)

const title = computed(() => okAlertOptions.value?.title ?? '')
const content = computed(() => okAlertOptions.value?.content ?? '')
const showCancel = computed(() => okAlertOptions.value?.showCancel !== false)
const cancelText = computed(() => okAlertOptions.value?.cancelText || '取消')
const confirmText = computed(() => okAlertOptions.value?.confirmText || '确定')
const confirmDanger = computed(() => !!okAlertOptions.value?.confirmDanger)
const tone = computed(() => okAlertOptions.value?.tone || 'default')
const maskClosable = computed(() => !!okAlertOptions.value?.maskClosable)

onMounted(() => {
  registerOkAlertHost(hostId, resolveHostRoute())
})

onUnmounted(() => {
  unregisterOkAlertHost(hostId)
})

onShow(() => {
  activateOkAlertHost(hostId)
})

function onConfirm() {
  finishOkAlert({ confirm: true, cancel: false })
}

function onCancel() {
  finishOkAlert({ confirm: false, cancel: true })
}
</script>
