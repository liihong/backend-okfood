<template>
  <view v-if="visible" class="addr-sheet-mask" @tap="onMaskTap">
    <view class="addr-sheet" @tap.stop>
      <view class="addr-sheet-head">
        <text class="addr-sheet-title">{{ title }}</text>
        <text class="addr-sheet-close" @tap="emitClose">×</text>
      </view>

      <view v-if="loading" class="addr-sheet-state">加载地址中…</view>
      <view v-else-if="loadError" class="addr-sheet-state addr-sheet-state--err">{{ loadError }}</view>
      <view v-else-if="!addressRows.length" class="addr-sheet-empty">
        <text class="addr-sheet-empty-txt">暂无配送地址，请先添加</text>
        <button class="addr-sheet-btn addr-sheet-btn--ghost" hover-class="none" @tap="goAddressList">
          去添加地址
        </button>
      </view>
      <scroll-view v-else scroll-y class="addr-sheet-scroll" :show-scrollbar="false">
        <view
          v-for="(row, i) in addressRows"
          :key="row.id || i"
          class="addr-sheet-row"
          :class="{ 'addr-sheet-row--on': selectedIndex === i }"
          @tap="selectedIndex = i"
        >
          <view class="addr-sheet-radio">
            <view v-if="selectedIndex === i" class="addr-sheet-dot" />
            <view v-else class="addr-sheet-ring" />
          </view>
          <view class="addr-sheet-body">
            <view class="addr-sheet-line1">
              <text class="addr-sheet-name">{{ row.name }}</text>
              <text class="addr-sheet-phone">{{ row.phone }}</text>
              <text v-if="row.isDefault" class="addr-sheet-badge">默认</text>
            </view>
            <text class="addr-sheet-line2">{{ row.line }}</text>
          </view>
        </view>
      </scroll-view>

      <view class="addr-sheet-foot">
        <button class="addr-sheet-btn addr-sheet-btn--ghost" hover-class="none" @tap="goAddressList">
          管理地址
        </button>
        <button
          class="addr-sheet-btn addr-sheet-btn--primary"
          hover-class="none"
          :disabled="confirming || loading || !addressRows.length"
          @tap="onConfirm"
        >
          {{ confirming ? '保存中…' : confirmText }}
        </button>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getMemberToken, request } from '@/utils/api.js'
import {
  addressListRow,
  getAddressRecordId,
  normalizeAddressList,
  sortAddressesDefaultFirst,
} from '@/utils/addressApi.js'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  /** 当前订单绑定的地址 id */
  selectedAddressId: {
    type: [String, Number],
    default: '',
  },
  title: {
    type: String,
    default: '选择配送地址',
  },
  confirmText: {
    type: String,
    default: '确认修改',
  },
})

const emit = defineEmits(['close', 'confirm'])

const loading = ref(false)
const loadError = ref('')
const addressRows = ref([])
const rawAddresses = ref([])
const selectedIndex = ref(0)
const confirming = ref(false)

function emitClose() {
  emit('close')
}

function onMaskTap() {
  if (confirming.value) return
  emitClose()
}

function syncSelectedIndex() {
  const targetId = props.selectedAddressId != null ? String(props.selectedAddressId) : ''
  if (!targetId) {
    selectedIndex.value = 0
    return
  }
  const idx = addressRows.value.findIndex((row) => String(row.id) === targetId)
  selectedIndex.value = idx >= 0 ? idx : 0
}

async function loadAddresses() {
  if (!getMemberToken()) {
    loadError.value = '请先登录'
    addressRows.value = []
    rawAddresses.value = []
    return
  }
  loading.value = true
  loadError.value = ''
  try {
    const raw = await request('/api/user/me/addresses', { method: 'GET', retry: 1 })
    const list = sortAddressesDefaultFirst(normalizeAddressList(raw))
    rawAddresses.value = list
    addressRows.value = list.map((item, i) => addressListRow(item, i))
    syncSelectedIndex()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载地址失败'
    addressRows.value = []
    rawAddresses.value = []
  } finally {
    loading.value = false
  }
}

function goAddressList() {
  uni.navigateTo({ url: '/packageUser/pages/address/list' })
}

function onConfirm() {
  if (confirming.value || loading.value || !addressRows.value.length) return
  const item = rawAddresses.value[selectedIndex.value]
  const addressId = getAddressRecordId(item)
  if (!addressId) {
    uni.showToast({ title: '地址无效，请重新选择', icon: 'none' })
    return
  }
  confirming.value = true
  emit('confirm', {
    memberAddressId: Number(addressId),
    addressRow: addressRows.value[selectedIndex.value] || null,
    finish: () => {
      confirming.value = false
    },
  })
}

watch(
  () => props.visible,
  (open) => {
    if (open) {
      confirming.value = false
      void loadAddresses()
    }
  },
)

watch(
  () => props.selectedAddressId,
  () => {
    if (props.visible) syncSelectedIndex()
  },
)
</script>

<style lang="scss" scoped>
.addr-sheet-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}

.addr-sheet {
  width: 100%;
  max-height: 78vh;
  background: #fff;
  border-radius: 28rpx 28rpx 0 0;
  padding: 28rpx 28rpx calc(28rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.addr-sheet-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20rpx;
}

.addr-sheet-title {
  font-size: 32rpx;
  font-weight: 800;
  color: #0f172a;
}

.addr-sheet-close {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  text-align: center;
  font-size: 40rpx;
  color: #94a3b8;
}

.addr-sheet-scroll {
  max-height: 46vh;
}

.addr-sheet-state {
  padding: 48rpx 0;
  text-align: center;
  font-size: 28rpx;
  color: #64748b;
}

.addr-sheet-state--err {
  color: #dc2626;
}

.addr-sheet-empty {
  padding: 32rpx 0 12rpx;
  text-align: center;
}

.addr-sheet-empty-txt {
  display: block;
  margin-bottom: 20rpx;
  font-size: 28rpx;
  color: #64748b;
}

.addr-sheet-row {
  display: flex;
  gap: 20rpx;
  padding: 24rpx 0;
  border-bottom: 1rpx solid #f1f5f9;
}

.addr-sheet-row--on {
  background: rgba(115, 176, 84, 0.06);
  margin: 0 -12rpx;
  padding-left: 12rpx;
  padding-right: 12rpx;
  border-radius: 16rpx;
}

.addr-sheet-radio {
  width: 36rpx;
  padding-top: 8rpx;
  flex-shrink: 0;
}

.addr-sheet-dot,
.addr-sheet-ring {
  width: 28rpx;
  height: 28rpx;
  border-radius: 50%;
}

.addr-sheet-dot {
  background: #73b054;
}

.addr-sheet-ring {
  border: 2rpx solid #cbd5e1;
}

.addr-sheet-body {
  flex: 1;
  min-width: 0;
}

.addr-sheet-line1 {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.addr-sheet-name,
.addr-sheet-phone {
  font-size: 28rpx;
  font-weight: 800;
  color: #0f172a;
}

.addr-sheet-badge {
  padding: 2rpx 10rpx;
  border-radius: 999rpx;
  background: rgba(115, 176, 84, 0.12);
  color: #73b054;
  font-size: 20rpx;
}

.addr-sheet-line2 {
  display: block;
  font-size: 26rpx;
  color: #64748b;
  line-height: 1.45;
}

.addr-sheet-foot {
  display: flex;
  gap: 16rpx;
  margin-top: 24rpx;
}

.addr-sheet-btn {
  flex: 1;
  margin: 0;
  border-radius: 16rpx;
  font-size: 28rpx;
  line-height: 1.35;
  padding: 24rpx 16rpx;
}

.addr-sheet-btn::after {
  border: none;
}

.addr-sheet-btn--ghost {
  background: #fff;
  color: #64748b;
  border: 1rpx solid #e2e8f0;
}

.addr-sheet-btn--primary {
  background: #73b054;
  color: #fff;
  border: none;
}

.addr-sheet-btn[disabled] {
  opacity: 0.55;
}
</style>
