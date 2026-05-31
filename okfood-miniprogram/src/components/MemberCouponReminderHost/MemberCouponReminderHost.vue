<template>
  <MemberCouponReminderModal
    :visible="modalVisible"
    :count="modalCount"
    :max-discount-yuan="modalMaxDiscount"
    :coupons="modalCoupons"
    @update:visible="onVisibleChange"
    @confirm="onConfirm"
    @dismiss="onDismiss"
  />
</template>

<script setup>
import { computed } from 'vue'
import MemberCouponReminderModal from '@/components/MemberCouponReminderModal/MemberCouponReminderModal.vue'
import {
  couponReminderVisible,
  couponReminderPayload,
  hideCouponReminderModal,
} from '@/utils/memberCouponReminderState.js'

const MEMBER_CARD_LIST_URL = '/packageUser/pages/membershipCardList/membershipCardList'

const modalVisible = computed(() => !!couponReminderVisible.value)
const modalCount = computed(() => {
  const n = Number(couponReminderPayload.value?.count)
  return Number.isFinite(n) ? Math.max(0, Math.floor(n)) : 0
})
const modalMaxDiscount = computed(() => {
  const s = couponReminderPayload.value?.maxDiscountYuan
  return s != null ? String(s) : ''
})
const modalCoupons = computed(() => {
  const list = couponReminderPayload.value?.coupons
  return Array.isArray(list) ? list : []
})

function onVisibleChange(v) {
  if (!v) hideCouponReminderModal()
}

function onDismiss() {
  hideCouponReminderModal()
}

function onConfirm() {
  hideCouponReminderModal()
  uni.navigateTo({ url: MEMBER_CARD_LIST_URL })
}
</script>
