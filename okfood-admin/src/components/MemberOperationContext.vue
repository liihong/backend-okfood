<script setup>
/**
 * 会员操作弹窗 · 操作对象条（紧挨标题下方）
 * 顶栏 title/subtitle = 正在办哪类事；本组件 = 对谁；body 表单 = 具体动作（如操作类型）
 */
import MemberDialogMeta from './MemberDialogMeta.vue'

defineProps({
  name: { type: String, default: '' },
  phone: { type: String, default: '' },
  plan: { type: String, default: '' },
  /**
   * 双行语境（补餐等）：首行仅姓名·手机；次行「会员信息」展示餐段与剩余次数
   */
  dualMemberInfo: { type: Boolean, default: false },
  /** 与 dualMemberInfo 搭配：当前剩余次数 */
  balance: { type: [Number, String], default: null },
})
</script>

<template>
  <template v-if="dualMemberInfo">
    <div class="okfood-member-op-ctx__inner okfood-member-op-ctx__line--subject">
      <span class="okfood-member-op-ctx__kicker">操作对象</span>
      <p class="okfood-member-op-ctx__subject-line">
        <MemberDialogMeta :name="name" :phone="phone" />
      </p>
    </div>
    <div class="okfood-member-op-ctx__inner okfood-member-op-ctx__line--member-info">
      <span class="okfood-member-op-ctx__kicker">会员信息</span>
      <p class="okfood-member-op-ctx__subject-line">
        <span v-if="plan" class="okfood-admin-dlg__meta-tag">{{ plan }}</span>
        <template v-if="balance != null && balance !== ''">
          <span class="okfood-admin-dlg__meta-muted">当前剩余</span>
          <strong class="okfood-admin-dlg__meta-em">{{ balance }}</strong>
          <span class="okfood-admin-dlg__meta-muted">次</span>
        </template>
        <slot />
      </p>
    </div>
  </template>
  <div v-else class="okfood-member-op-ctx__inner">
    <span class="okfood-member-op-ctx__kicker">操作对象</span>
    <p class="okfood-member-op-ctx__subject-line">
      <MemberDialogMeta :name="name" :phone="phone" :plan="plan">
        <slot />
      </MemberDialogMeta>
    </p>
  </div>
</template>
