<script setup>
/**
 * 会员档案 · 操作列「更多」下拉（分组 + Emoji 图标格，对齐 design 预览图 1）
 * 样式见 admin-ui.css `.okfood-members-more-dropdown`
 */
defineProps({
  /** 不可退卡时禁用「退卡退款」 */
  refundDisabled: { type: Boolean, default: true },
  deleteDisabled: { type: Boolean, default: false },
  deleteLabel: { type: String, default: '删除' },
})
</script>

<template>
  <el-dropdown-menu class="members-more-menu">
    <el-dropdown-item disabled class="members-more-menu__group">履约</el-dropdown-item>
    <el-dropdown-item command="leave" class="members-more-menu__item">
      <span class="members-more-menu__inner" title="手工请假">
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">📅</span>
        <span class="members-more-menu__label">请假</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="reinstate_delivery" class="members-more-menu__item">
      <span
        class="members-more-menu__inner"
        title="推单后取消请假默认不加回；仅此操作可强制写入当日配送大表"
      >
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🚚</span>
        <span class="members-more-menu__label">强制加入当天配送大表</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="addresses" class="members-more-menu__item">
      <span
        class="members-more-menu__inner"
        title="地址管理：查看全部配送地址，编辑、地图选点，并可代为切换默认地址"
      >
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">📍</span>
        <span class="members-more-menu__label">地址</span>
      </span>
    </el-dropdown-item>

    <el-dropdown-item disabled class="members-more-menu__group">档案</el-dropdown-item>
    <el-dropdown-item command="edit" class="members-more-menu__item">
      <span class="members-more-menu__inner" title="修改会员信息">
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">✏️</span>
        <span class="members-more-menu__label">修改</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="edit_balance" class="members-more-menu__item">
      <span class="members-more-menu__inner" title="修改剩余次数与每配送日份数">
        <span class="members-more-menu__icon members-more-menu__icon--glyph" aria-hidden="true">#</span>
        <span class="members-more-menu__label">修改次数</span>
      </span>
    </el-dropdown-item>

    <el-dropdown-item disabled class="members-more-menu__group">记录</el-dropdown-item>
    <el-dropdown-item command="records" class="members-more-menu__item">
      <span class="members-more-menu__inner" title="套餐已确认送达的业务日（扣次记录）">
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🧾</span>
        <span class="members-more-menu__label">消费记录</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="operation_logs" class="members-more-menu__item">
      <span
        class="members-more-menu__inner"
        title="该会员在小程序或后台触发的配送、地址、请假等操作留痕"
      >
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🕐</span>
        <span class="members-more-menu__label">操作记录</span>
      </span>
    </el-dropdown-item>

    <el-dropdown-item disabled class="members-more-menu__group">售后</el-dropdown-item>
    <el-dropdown-item command="meal_compensation" class="members-more-menu__item">
      <span
        class="members-more-menu__inner"
        title="餐品问题赔付：将已消费次数补回余额，并写入操作审计"
      >
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🔧</span>
        <span class="members-more-menu__label">补餐赔付</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="grant_coupon" class="members-more-menu__item">
      <span class="members-more-menu__inner" title="跳转优惠券发放页，向该会员发放续卡优惠券">
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🎟</span>
        <span class="members-more-menu__label">发优惠券</span>
      </span>
    </el-dropdown-item>
    <el-dropdown-item command="refund" class="members-more-menu__item" :disabled="refundDisabled">
      <span
        class="members-more-menu__inner"
        title="按剩余次数 × 菜单单价计算应退金额，确认后写入财务扣减"
      >
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">💳</span>
        <span class="members-more-menu__label">退卡退款</span>
      </span>
    </el-dropdown-item>

    <el-dropdown-item disabled class="members-more-menu__group">危险</el-dropdown-item>
    <el-dropdown-item
      command="delete"
      class="members-more-menu__item members-more-menu__item--danger"
      :disabled="deleteDisabled"
    >
      <span class="members-more-menu__inner">
        <span class="members-more-menu__icon members-more-menu__icon--emoji" aria-hidden="true">🗑</span>
        <span class="members-more-menu__label">{{ deleteLabel }}</span>
      </span>
    </el-dropdown-item>
  </el-dropdown-menu>
</template>
