<script setup>
/**
 * 会员操作弹窗 · 操作对象条（客服核对姓名/手机/餐段）
 */
defineProps({
  name: { type: String, default: '' },
  phone: { type: String, default: '' },
  /** 套餐、餐段等第三段文案 */
  plan: { type: String, default: '' },
})
</script>

<template>
  <span class="okfood-admin-dlg__meta-name">{{ name || '—' }}</span>
  <span v-if="phone" class="okfood-admin-dlg__meta-sep" aria-hidden="true">·</span>
  <span v-if="phone" class="okfood-admin-dlg__meta-phone">{{ phone }}</span>
  <template v-if="plan">
    <span class="okfood-admin-dlg__meta-sep" aria-hidden="true">·</span>
    <span class="okfood-admin-dlg__meta-tag">{{ plan }}</span>
  </template>
  <slot />
</template>
