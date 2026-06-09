<template>
  <view class="menu-store-header">
    <image
      v-if="logoUrl"
      class="menu-store-header__logo"
      :src="logoUrl"
      mode="aspectFill"
    />
    <view v-else class="menu-store-header__logo menu-store-header__logo--placeholder">
      <text class="menu-store-header__logo-txt">OK</text>
    </view>
    <view class="menu-store-header__main">
      <text class="menu-store-header__name">{{ displayName }}</text>
      <text v-if="phone" class="menu-store-header__sub">联系电话 {{ phone }}</text>
      <text v-else class="menu-store-header__sub">健康自律餐 · 每周新鲜菜单</text>
    </view>
    <view class="menu-store-header__mode">
      <view
        class="mode-pill"
        :class="{ 'mode-pill--active': currentMode === 'pickup' }"
        @tap.stop="setMode('pickup')"
        @click.stop="setMode('pickup')"
      >
        <text class="mode-pill__txt">自提</text>
      </view>
      <view
        class="mode-pill"
        :class="{ 'mode-pill--active': currentMode === 'delivery' }"
        @tap.stop="setMode('delivery')"
        @click.stop="setMode('delivery')"
      >
        <text class="mode-pill__txt">配送</text>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  storeName: { type: String, default: '' },
  storeLogoUrl: { type: String, default: '' },
  storeContactPhone: { type: String, default: '' },
  /** pickup | delivery */
  fulfillMode: { type: String, default: 'delivery' },
})

const emit = defineEmits(['change'])

const currentMode = ref(normalizeMode(props.fulfillMode))

watch(
  () => props.fulfillMode,
  (v) => {
    currentMode.value = normalizeMode(v)
  },
)

const displayName = computed(() => {
  const n = String(props.storeName || '').trim()
  return n || 'OK 饭'
})

const logoUrl = computed(() => {
  const u = String(props.storeLogoUrl || '').trim()
  return u || ''
})

const phone = computed(() => {
  const p = String(props.storeContactPhone || '').trim()
  return p || ''
})

function normalizeMode(v) {
  return v === 'pickup' ? 'pickup' : 'delivery'
}

function setMode(mode) {
  const next = normalizeMode(mode)
  if (next === currentMode.value) return
  currentMode.value = next
  emit('change', next)
}
</script>

<style lang="scss" scoped>
.menu-store-header {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 20rpx 24rpx 24rpx;
  background: #fff;
  border-bottom: 1rpx solid $ok-slate-100;
  box-sizing: border-box;
}

.menu-store-header__logo {
  width: 88rpx;
  height: 88rpx;
  border-radius: 20rpx;
  flex-shrink: 0;
  background: $ok-slate-50;
}

.menu-store-header__logo--placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: $ok-forest-green;
}

.menu-store-header__logo-txt {
  font-size: 28rpx;
  font-weight: 900;
  color: #fff;
}

.menu-store-header__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.menu-store-header__name {
  font-size: 32rpx;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-store-header__sub {
  font-size: 22rpx;
  color: $ok-slate-400;
  font-weight: 600;
  line-height: 1.3;
}

.menu-store-header__mode {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  padding: 4rpx;
  border-radius: 999rpx;
  background: $ok-slate-100;
  gap: 4rpx;
  position: relative;
  z-index: 2;
}

.mode-pill {
  min-width: 72rpx;
  padding: 10rpx 18rpx;
  border-radius: 999rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mode-pill--active {
  background: #1e293b;
}

.mode-pill__txt {
  font-size: 22rpx;
  font-weight: 800;
  color: $ok-slate-500;
  line-height: 1.2;
  pointer-events: none;
}

.mode-pill--active .mode-pill__txt {
  color: #fff;
}
</style>
