# -*- coding: utf-8 -*-
"""Restore garbled Vue components with guaranteed UTF-8 bytes."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "components"

STRIP = ROOT / "HomeMembershipCardStrip" / "HomeMembershipCardStrip.vue"
BAR = ROOT / "MemberLoginPromptBar" / "MemberLoginPromptBar.vue"

STRIP_CONTENT = """<template>
  <view v-if="templates.length" class="home-card-strip">
    <view class="home-card-strip__head">
      <view class="home-card-strip__title-wrap">
        <text class="home-card-strip__star">\u2726</text>
        <text class="home-card-strip__title">\u81ea\u5f8b\u81b3\u98df\u5361\u5305</text>
      </view>
      <text class="home-card-strip__more" @tap="goList">\u67e5\u770b\u5168\u90e8 \u203a</text>
    </view>

    <view
      v-if="templates.length <= 2"
      class="home-card-strip__row"
      :class="'home-card-strip__row--' + templates.length"
    >
      <view
        v-for="(t, idx) in templates"
        :key="t.id"
        class="home-card-strip__card"
        :class="['home-card-strip__card--' + paletteClass(idx)]"
        @tap="goDetail(t.id)"
      >
        <text class="home-card-strip__water">OK</text>
        <text class="home-card-strip__cap">MEMBER CARD</text>
        <text class="home-card-strip__name">{{ t.name }}</text>
        <view class="home-card-strip__foot">
          <text class="home-card-strip__meals">{{ t.meals_grant }} \u6b21\u9910</text>
          <text class="home-card-strip__price">\u00a5{{ priceOrDash(t.sale_price_yuan) }}</text>
        </view>
      </view>
    </view>
    <scroll-view
      v-else
      scroll-x
      class="home-card-strip__scroll"
      :show-scrollbar="false"
      enable-flex
    >
      <view class="home-card-strip__inner">
        <view
          v-for="(t, idx) in templates"
          :key="t.id"
          class="home-card-strip__card home-card-strip__card--scroll"
          :class="['home-card-strip__card--' + paletteClass(idx)]"
          @tap="goDetail(t.id)"
        >
          <text class="home-card-strip__water">OK</text>
          <text class="home-card-strip__cap">MEMBER CARD</text>
          <text class="home-card-strip__name">{{ t.name }}</text>
          <view class="home-card-strip__foot">
            <text class="home-card-strip__meals">{{ t.meals_grant }} \u6b21\u9910</text>
            <text class="home-card-strip__price">\u00a5{{ priceOrDash(t.sale_price_yuan) }}</text>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
defineProps({
  templates: { type: Array, default: () => [] },
})

function paletteClass(i) {
  const k = i % 3
  if (k === 0) return 'a'
  if (k === 1) return 'b'
  return 'c'
}

function priceOrDash(v) {
  if (v == null || v === '') return '\u2014'
  return String(v)
}

function goDetail(id) {
  uni.navigateTo({
    url: `/packageUser/pages/membershipCardDetail/membershipCardDetail?templateId=${encodeURIComponent(String(id))}`,
  })
}

function goList() {
  uni.navigateTo({ url: '/packageUser/pages/membershipCardList/membershipCardList' })
}
</script>

<style lang="scss" scoped>
.home-card-strip {
  width: 100%;
  margin-bottom: 32rpx;
  box-sizing: border-box;
}

.home-card-strip__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  padding: 0 32rpx;
  margin-bottom: 20rpx;
  box-sizing: border-box;
}

.home-card-strip__title-wrap {
  display: flex;
  align-items: center;
  gap: 10rpx;
  min-width: 0;
}

.home-card-strip__star {
  flex-shrink: 0;
  font-size: 28rpx;
  color: #f97316;
  line-height: 1;
}

.home-card-strip__title {
  font-size: 34rpx;
  font-weight: 1000;
  color: #1e293b;
  line-height: 1.3;
}

.home-card-strip__more {
  flex-shrink: 0;
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  line-height: 1.3;
}

.home-card-strip__row {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  padding: 0 32rpx;
  box-sizing: border-box;
}

.home-card-strip__row--1 .home-card-strip__card {
  flex: 1;
  width: 100%;
}

.home-card-strip__row--2 .home-card-strip__card {
  flex: 1;
  width: 0;
  min-width: 0;
}

.home-card-strip__scroll {
  width: 100%;
}

.home-card-strip__inner {
  display: flex;
  flex-direction: row;
  gap: 20rpx;
  padding: 0 32rpx 4rpx;
  box-sizing: border-box;
}

.home-card-strip__card {
  position: relative;
  min-height: 176rpx;
  border-radius: 24rpx;
  padding: 24rpx 22rpx 20rpx;
  box-sizing: border-box;
  overflow: hidden;
  box-shadow: 0 10rpx 28rpx rgba(15, 23, 42, 0.12);
}

.home-card-strip__card--scroll {
  width: 520rpx;
  flex-shrink: 0;
}

.home-card-strip__card--a {
  background: linear-gradient(135deg, #73b054 0%, #456d32 55%, #365628 100%);
}

.home-card-strip__card--b {
  background: linear-gradient(135deg, #b8860b 0%, #d97706 45%, #92400e 100%);
}

.home-card-strip__card--c {
  background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 50%, #312e81 100%);
}

.home-card-strip__water {
  position: absolute;
  right: -8rpx;
  bottom: -24rpx;
  font-size: 120rpx;
  font-weight: 900;
  color: rgba(255, 255, 255, 0.08);
  line-height: 1;
  pointer-events: none;
}

.home-card-strip__cap {
  position: relative;
  z-index: 1;
  display: block;
  font-size: 16rpx;
  letter-spacing: 0.14em;
  color: rgba(255, 255, 255, 0.72);
  margin-bottom: 8rpx;
}

.home-card-strip__name {
  position: relative;
  z-index: 1;
  display: block;
  font-size: 28rpx;
  font-weight: 800;
  color: #fff;
  line-height: 1.35;
  margin-bottom: 20rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-card-strip__foot {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12rpx;
  padding-top: 16rpx;
  border-top: 1rpx solid rgba(255, 255, 255, 0.2);
}

.home-card-strip__meals {
  font-size: 22rpx;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.88);
  flex-shrink: 0;
}

.home-card-strip__price {
  font-size: 34rpx;
  font-weight: 900;
  color: #fef08a;
  line-height: 1;
  flex-shrink: 0;
}
</style>
"""

BAR_CONTENT = """<template>
  <view v-if="guestVisible" class="member-login-bar">
    <text class="member-login-bar__text">\u767b\u5f55\u540e\u4eab\u53d7\u5b8c\u6574\u4f1a\u5458\u670d\u52a1</text>
    <button
      class="member-login-bar__btn"
      hover-class="member-login-bar__btn--hover"
      open-type="getPhoneNumber"
      @getphonenumber="onWxGetPhoneNumber"
    >
      \u7acb\u5373\u767b\u5f55
    </button>
  </view>
  <view v-else-if="loggedInVisible" class="member-user-bar">
    <view class="member-user-bar__profile">
      <view class="member-user-bar__avatar-wrap">
        <image
          v-if="avatarUrl"
          class="member-user-bar__avatar"
          :src="avatarUrl"
          mode="aspectFill"
        />
        <text v-else class="member-user-bar__avatar-fallback">{{ avatarChar }}</text>
      </view>
      <text class="member-user-bar__name">{{ displayName }}</text>
    </view>
    <button
      class="member-user-bar__btn"
      hover-class="member-user-bar__btn--hover"
      @tap="goMemberCenter"
    >
      \u4f1a\u5458\u4e2d\u5fc3
    </button>
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getMemberToken, request } from '@/utils/api.js'
import {
  hasWxPhoneAuthDetail,
  wxMiniMemberLoginAndStore,
} from '@/utils/wxMemberLogin.js'
import {
  loadWxProfile,
  memberAvatarFallbackChar,
  resolveMemberAvatarUrl,
  resolveMemberDisplayName,
} from '@/utils/memberWxProfile.js'

const emit = defineEmits(['logged-in'])

const guestVisible = ref(false)
const loggedInVisible = ref(false)
const wxProfile = ref(null)
const serverProfile = ref(null)
const memberPhone = ref('')
let syncSeq = 0

const displayName = computed(() =>
  resolveMemberDisplayName({
    wxProfile: wxProfile.value,
    serverProfile: serverProfile.value,
    phone: memberPhone.value,
  }),
)

const avatarUrl = computed(() =>
  resolveMemberAvatarUrl({
    wxProfile: wxProfile.value,
    serverProfile: serverProfile.value,
  }),
)

const avatarChar = computed(() => memberAvatarFallbackChar(displayName.value))

async function syncState() {
  const seq = ++syncSeq
  const token = getMemberToken()
  const phone = uni.getStorageSync('memberPhone') || ''
  memberPhone.value = phone

  if (!token) {
    guestVisible.value = true
    loggedInVisible.value = false
    wxProfile.value = null
    serverProfile.value = null
    return
  }

  guestVisible.value = false
  loggedInVisible.value = true
  wxProfile.value = loadWxProfile(phone)

  try {
    const data = await request('/api/user/me', { method: 'GET' })
    if (seq !== syncSeq) return
    serverProfile.value = data && typeof data === 'object' ? data : null
    const sp = data?.phone != null ? String(data.phone).trim() : ''
    if (sp) {
      memberPhone.value = sp
      wxProfile.value = loadWxProfile(sp)
    }
  } catch {
    if (seq !== syncSeq) return
    serverProfile.value = null
  }
}

async function onWxGetPhoneNumber(e) {
  const detail = e?.detail
  if (!hasWxPhoneAuthDetail(detail)) {
    if (detail?.errMsg && !String(detail.errMsg).includes('cancel')) {
      uni.showToast({ title: '\u9700\u8981\u6388\u6743\u624b\u673a\u53f7', icon: 'none' })
    }
    return
  }
  uni.showLoading({ title: '\u767b\u5f55\u4e2d', mask: true })
  try {
    const { profile } = await wxMiniMemberLoginAndStore(detail)
    emit('logged-in')
    uni.showToast({ title: '\u767b\u5f55\u6210\u529f', icon: 'success' })
    if (profile && typeof profile === 'object') {
      serverProfile.value = profile
      const sp = profile.phone != null ? String(profile.phone).trim() : ''
      if (sp) memberPhone.value = sp
    }
    await syncState()
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '\u767b\u5f55\u5931\u8d25',
      icon: 'none',
    })
  } finally {
    uni.hideLoading()
  }
}

function goMemberCenter() {
  uni.switchTab({ url: '/pages/mine/index' })
}

onMounted(syncState)
onShow(syncState)
</script>

<style lang="scss" scoped>
.member-login-bar,
.member-user-bar {
  margin: 0 32rpx;
}

.member-login-bar {
  min-height: 88rpx;
  padding: 16rpx 24rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  background: #ecfdf5;
  border: 1rpx solid #bbf7d0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-login-bar__text {
  flex: 1;
  min-width: 0;
  font-size: 26rpx;
  font-weight: 700;
  color: #166534;
}

.member-login-bar__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 28rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  border: none;
}

.member-login-bar__btn::after {
  border: none;
}

.member-login-bar__btn--hover {
  opacity: 0.92;
}

.member-user-bar {
  min-height: 88rpx;
  padding: 12rpx 24rpx;
  box-sizing: border-box;
  border-radius: 999rpx;
  background: #fff;
  border: 1rpx solid $ok-slate-100;
  box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.04);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
}

.member-user-bar__profile {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16rpx;
}

.member-user-bar__avatar-wrap {
  width: 64rpx;
  height: 64rpx;
  border-radius: 50%;
  overflow: hidden;
  flex-shrink: 0;
  background: $ok-slate-100;
  display: flex;
  align-items: center;
  justify-content: center;
}

.member-user-bar__avatar {
  width: 100%;
  height: 100%;
}

.member-user-bar__avatar-fallback {
  font-size: 28rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.member-user-bar__name {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  font-weight: 800;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.member-user-bar__btn {
  flex-shrink: 0;
  margin: 0;
  padding: 0 28rpx;
  height: 56rpx;
  line-height: 56rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  border: none;
}

.member-user-bar__btn::after {
  border: none;
}

.member-user-bar__btn--hover {
  opacity: 0.92;
}
</style>
"""


def write_utf8(path: Path, content: str, marker: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")
    decoded = path.read_text(encoding="utf-8")
    assert marker in decoded, f"missing marker {marker!r} in {path.name}"


def main() -> None:
    write_utf8(STRIP, STRIP_CONTENT, "\u81ea\u5f8b\u81b3\u98df\u5361\u5305")
    write_utf8(BAR, BAR_CONTENT, "\u767b\u5f55\u540e\u4eab\u53d7\u5b8c\u6574\u4f1a\u5458\u670d\u52a1")
    print("restored:", STRIP.name, BAR.name)


if __name__ == "__main__":
    main()
