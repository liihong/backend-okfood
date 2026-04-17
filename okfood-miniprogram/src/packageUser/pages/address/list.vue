<template>
  <view class="page">
    <OkNavbar show-back title="我的配送地址 👌" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view class="list-inner">
        <view v-if="loading" class="state-text">加载中…</view>
        <view v-else-if="!list.length" class="state-text state-text--muted">暂无收货地址，点击下方添加</view>
        <view
          v-for="(item, index) in list"
          v-else
          :key="addressListRow(item, index).id || `i-${index}`"
          :class="['address-item', { 'address-item--default': addressListRow(item, index).isDefault }]"
        >
          <view class="addr-info" @click="setAsDefault(item, index)">
            <view class="addr-title-row">
              <text class="addr-name">{{ addressListRow(item, index).name || '未填写称呼' }}</text>
              <text v-if="addressListRow(item, index).isDefault" class="default-tag">默认</text>
            </view>
            <text class="addr-phone">{{ addressListRow(item, index).phone || '—' }}</text>
            <text class="addr-line">{{ addressListRow(item, index).line || '—' }}</text>
          </view>
          <view class="addr-actions" @click.stop>
            <text class="edit-btn" @click="goEdit(item, index)">✎</text>
            <view class="delete-btn" @click="confirmDelete(item, index)">
              <view class="icon-trash">
                <view class="icon-trash__handle"></view>
                <view class="icon-trash__lid"></view>
                <view class="icon-trash__body"></view>
              </view>
            </view>
          </view>
        </view>
        <view class="scroll-tail" />
      </view>
    </scroll-view>
    <view class="footer">
      <button class="btn-add-address" hover-class="none" @tap.stop="goAdd">+ 添加新地址</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { request, getMemberToken } from '@/utils/api.js'
import {
  normalizeAddressList,
  addressListRow,
  sortAddressesDefaultFirst,
  isAddressItemDefault,
} from '@/utils/addressApi.js'

const list = ref([])
const loading = ref(true)
/** 避免 onShow 重叠或返回列表时旧请求先结束，连续改状态/提示触发基础库 timeout */
let fetchListSeq = 0

async function fetchList() {
  const token = getMemberToken()
  const seq = ++fetchListSeq
  if (!token) {
    list.value = []
    loading.value = false
    return
  }
  loading.value = true
  try {
    const data = await request('/api/user/me/addresses', {
      method: 'GET',
    })
    if (seq !== fetchListSeq) return
    list.value = sortAddressesDefaultFirst(normalizeAddressList(data))
  } catch {
    if (seq !== fetchListSeq) return
    list.value = []
  } finally {
    if (seq === fetchListSeq) loading.value = false
  }
}

onShow(() => {
  fetchList()
})

function goEdit(item, index) {
  const id = addressListRow(item, index).id
  if (!id) {
    uni.showToast({ title: '地址缺少编号', icon: 'none' })
    return
  }
  uni.navigateTo({
    url: `/packageUser/pages/address/address?id=${encodeURIComponent(id)}`,
  })
}

/** 点击条目设为默认：PATCH is_default，成功后列表重排默认在第一 */
async function setAsDefault(item, index) {
  const row = addressListRow(item, index)
  if (!row.id) {
    uni.showToast({ title: '地址缺少编号', icon: 'none' })
    return
  }
  if (isAddressItemDefault(item)) {
    uni.showToast({ title: '已是默认收货地址', icon: 'none' })
    return
  }
  const token = getMemberToken()
  if (!token) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  try {
    const result = await request(
      `/api/user/me/addresses/${encodeURIComponent(row.id)}`,
      { method: 'PATCH', data: { is_default: true } },
    )
    const tip =
      result && typeof result === 'object' ? result.message || result.msg : ''
    uni.showToast({
      title: typeof tip === 'string' && tip.trim() ? tip.trim() : '已设为默认地址',
      icon: 'success',
    })
    await fetchList()
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '设置失败',
      icon: 'none',
    })
  }
}

function goAdd() {
  uni.navigateTo({ url: '/packageUser/pages/address/address' })
}

/** 先弹窗确认，再请求 DELETE /api/user/me/addresses/{address_id} */
function confirmDelete(item, index) {
  const row = addressListRow(item, index)
  if (!row.id) {
    uni.showToast({ title: '地址缺少编号', icon: 'none' })
    return
  }
  uni.showModal({
    title: '提示',
    content: '确定删除该收货地址吗？删除后不可恢复。',
    confirmText: '删除',
    cancelText: '取消',
    confirmColor: '#ff3e3e',
    success: (res) => {
      if (res.confirm) {
        void deleteAddress(row.id)
      }
    },
  })
}

async function deleteAddress(addressId) {
  const token = getMemberToken()
  if (!token) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  try {
    const result = await request(
      `/api/user/me/addresses/${encodeURIComponent(addressId)}`,
      { method: 'DELETE' },
    )
    const tip =
      result && typeof result === 'object' ? result.message || result.msg : ''
    uni.showToast({
      title: typeof tip === 'string' && tip.trim() ? tip.trim() : '已删除',
    })
    await fetchList()
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '删除失败',
      icon: 'none',
    })
  }
}
</script>

<style lang="scss" scoped>
.page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $ok-slate-50;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
}

.list-inner {
  padding: 24rpx 48rpx 0;
}

.state-text {
  padding: 80rpx 20rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.state-text--muted {
  color: $ok-slate-400;
}

.address-item {
  background: #fff;
  border-radius: 56rpx;
  padding: 48rpx;
  margin-bottom: 30rpx;
  border: 1px solid rgba(0, 0, 0, 0.02);
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.02);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24rpx;
}

.address-item--default {
  border: 2px solid $ok-forest-green;
  background: #f0f9f6;
}

.addr-info {
  flex: 1;
  min-width: 0;
}

.addr-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16rpx;
  margin-bottom: 10rpx;
}

.addr-name {
  font-size: 32rpx;
  font-weight: 950;
  color: #333;
}

.default-tag {
  font-size: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  padding: 4rpx 16rpx;
  border-radius: 12rpx;
  font-weight: 900;
}

.addr-phone {
  display: block;
  font-size: 26rpx;
  color: $ok-slate-400;
  font-weight: 800;
  line-height: 1.4;
}

.addr-line {
  display: block;
  margin-top: 10rpx;
  font-size: 26rpx;
  color: #333;
  font-weight: 800;
  line-height: 1.45;
}

.addr-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8rpx;
}

.edit-btn {
  color: #ccc;
  font-size: 40rpx;
  padding: 20rpx;
}

.delete-btn {
  padding: 20rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 线框垃圾桶，#ccc 与编辑笔一致，尺寸接近 40rpx 字号 */
.icon-trash {
  width: 32rpx;
  height: 36rpx;
  position: relative;
  flex-shrink: 0;
}

.icon-trash__handle {
  position: absolute;
  top: 0;
  left: 50%;
  width: 16rpx;
  height: 7rpx;
  margin-left: -8rpx;
  border: 3rpx solid #ccc;
  border-bottom: none;
  border-radius: 4rpx 4rpx 0 0;
  box-sizing: border-box;
}

.icon-trash__lid {
  position: absolute;
  top: 5rpx;
  left: 0;
  right: 0;
  height: 3rpx;
  background: #ccc;
  border-radius: 2rpx;
}

.icon-trash__body {
  position: absolute;
  top: 9rpx;
  left: 3rpx;
  width: 26rpx;
  height: 25rpx;
  border: 3rpx solid #ccc;
  border-top: none;
  border-radius: 0 0 5rpx 5rpx;
  box-sizing: border-box;
}

.scroll-tail {
  height: 24rpx;
}

.footer {
  flex-shrink: 0;
  padding: 24rpx 48rpx;
  padding-bottom: calc(24rpx + env(safe-area-inset-bottom));
  background: $ok-slate-50;
}

.btn-add-address {
  width: 100%;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  padding: 40rpx;
  border-radius: 60rpx;
  font-weight: 950;
  font-size: 36rpx;
  box-shadow: 0 20rpx 50rpx rgba(250, 204, 21, 0.3);
  border: none;
  line-height: 1.35;
}

.btn-add-address::after {
  border: none;
}
</style>
