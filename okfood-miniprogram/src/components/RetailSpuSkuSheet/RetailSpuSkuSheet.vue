<template>
  <!-- z-index 高于自定义 tabBar，与购物车抽屉同级 -->
  <view v-if="show" class="sku-mask" @tap="close">
    <view class="sku-sheet" @tap.stop>
      <view class="sku-sheet__handle-wrap">
        <view class="sku-sheet__handle" />
      </view>

      <view v-if="loading" class="sku-sheet__state">加载中…</view>
      <view v-else-if="!detail" class="sku-sheet__state sku-sheet__state--err">商品不存在或已下架</view>
      <view v-else class="sku-sheet__body">
        <view class="sku-sheet__head">
          <image class="sku-sheet__cover" :src="coverUrl" mode="aspectFill" />
          <view class="sku-sheet__meta">
            <text class="sku-sheet__title">{{ detail.title }}</text>
            <text v-if="detail.subtitle" class="sku-sheet__sub">{{ detail.subtitle }}</text>
            <view class="sku-sheet__price-row">
              <text class="sku-sheet__price">¥{{ priceText }}</text>
              <text v-if="listPriceText" class="sku-sheet__list-price">¥{{ listPriceText }}</text>
            </view>
          </view>
          <view class="sku-sheet__close" @tap="close">
            <text class="sku-sheet__close-txt">×</text>
          </view>
        </view>

        <view v-if="skus.length > 1" class="sku-sheet__section">
          <text class="sku-sheet__label">选择规格</text>
          <view class="sku-sheet__chips">
            <view
              v-for="s in skus"
              :key="s.id"
              class="sku-chip"
              :class="{
                'sku-chip--on': selectedSkuId === s.id,
                'sku-chip--disabled': !isRetailSkuSelectable(s),
              }"
              @tap="() => onSelectSku(s)"
            >
              <text>{{ s.spec_label || '默认' }}</text>
            </view>
          </view>
        </view>

        <view class="sku-sheet__section sku-sheet__section--qty">
          <text class="sku-sheet__label">数量</text>
          <view class="sku-qty">
            <view class="sku-qty__btn" @tap="onChangeQty(-1)">−</view>
            <text class="sku-qty__num">{{ quantity }}</text>
            <view class="sku-qty__btn" @tap="onChangeQty(1)">+</view>
          </view>
        </view>

        <view class="sku-sheet__foot">
          <button class="sku-sheet__btn" type="default" hover-class="none" @tap="onConfirm">
            加入购物车
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { fetchRetailSpuDetail } from '@/utils/catalogApi.js'
import { optimizeImageUrl } from '@/utils/imageUrl.js'
import { addCartItem } from '@/utils/retailCart/retailCartStorage.js'
import { notifyRetailCartChanged } from '@/utils/retailCart/useRetailCart.js'
import {
  buildRetailCartProductFromSpu,
  formatRetailSkuListPriceText,
  formatRetailSkuPriceText,
  isRetailSkuSelectable,
  nextRetailSkuQuantity,
  pickDefaultRetailSku,
} from '@/utils/retailSku/retailSkuModel.js'

const props = defineProps({
  /** 是否展示抽屉 */
  show: { type: Boolean, default: false },
  /** 当前要选规格的 SPU id */
  spuId: { type: Number, default: 0 },
})

const emit = defineEmits(['update:show', 'added'])

const loading = ref(false)
const detail = ref(null)
const selectedSkuId = ref(null)
const quantity = ref(1)

const skus = computed(() => (Array.isArray(detail.value?.skus) ? detail.value.skus : []))

const selectedSku = computed(
  () => skus.value.find((s) => Number(s.id) === Number(selectedSkuId.value)) || null,
)

const coverUrl = computed(() => {
  const d = detail.value
  const urls = d?.gallery_urls
  if (Array.isArray(urls)) {
    const first = urls.find((u) => String(u || '').trim())
    if (first) return optimizeImageUrl(String(first), null, 'list')
  }
  const raw = d?.cover_image_url != null ? String(d.cover_image_url) : ''
  return raw ? optimizeImageUrl(raw, null, 'list') : ''
})

const priceText = computed(() => formatRetailSkuPriceText(selectedSku.value, detail.value))

const listPriceText = computed(() => formatRetailSkuListPriceText(selectedSku.value))

function close() {
  emit('update:show', false)
}

function resetPickerState() {
  detail.value = null
  selectedSkuId.value = null
  quantity.value = 1
}

async function loadDetail(spuId) {
  const id = Number(spuId)
  if (!Number.isFinite(id) || id < 1) {
    detail.value = null
    return
  }
  loading.value = true
  try {
    const data = await fetchRetailSpuDetail(id)
    detail.value = data
    const first = pickDefaultRetailSku(Array.isArray(data?.skus) ? data.skus : [])
    selectedSkuId.value = first?.id ?? null
    quantity.value = 1
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.show, props.spuId],
  ([visible, spuId]) => {
    if (!visible) {
      resetPickerState()
      return
    }
    void loadDetail(spuId)
  },
)

function onSelectSku(s) {
  if (!isRetailSkuSelectable(s)) {
    uni.showToast({ title: '该规格不可选', icon: 'none' })
    return
  }
  selectedSkuId.value = s.id
  quantity.value = 1
}

function onChangeQty(delta) {
  quantity.value = nextRetailSkuQuantity(quantity.value, delta, selectedSku.value)
}

function onConfirm() {
  const d = detail.value
  const s = selectedSku.value
  if (!d || !s) {
    uni.showToast({ title: '请选择规格', icon: 'none' })
    return
  }
  if (!isRetailSkuSelectable(s)) {
    uni.showToast({ title: '该规格已售罄', icon: 'none' })
    return
  }
  const payload = buildRetailCartProductFromSpu(d, s, coverUrl.value)
  if (!payload) {
    uni.showToast({ title: '商品无效', icon: 'none' })
    return
  }
  const res = addCartItem(payload, quantity.value)
  if (!res.ok) {
    uni.showToast({ title: res.msg || '加入失败', icon: 'none' })
    return
  }
  notifyRetailCartChanged()
  emit('added', { quantity: quantity.value, product: payload })
  close()
  uni.showToast({ title: '已加入购物车', icon: 'none' })
}
</script>

<style lang="scss" scoped>
.sku-mask {
  position: fixed;
  inset: 0;
  z-index: 10050;
  background: rgba(15, 23, 42, 0.48);
  display: flex;
  align-items: flex-end;
}

.sku-sheet {
  width: 100%;
  max-height: 78vh;
  background: #fff;
  border-radius: 28rpx 28rpx 0 0;
  display: flex;
  flex-direction: column;
  padding-bottom: calc(16rpx + env(safe-area-inset-bottom));
  box-sizing: border-box;
}

.sku-sheet__handle-wrap {
  padding: 16rpx 0 8rpx;
  display: flex;
  justify-content: center;
}

.sku-sheet__handle {
  width: 72rpx;
  height: 8rpx;
  border-radius: 999rpx;
  background: #e2e8f0;
}

.sku-sheet__state {
  padding: 80rpx 32rpx;
  text-align: center;
  font-size: 28rpx;
  color: $ok-slate-500;
  font-weight: 700;
}

.sku-sheet__state--err {
  color: #ef4444;
}

.sku-sheet__body {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sku-sheet__head {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 20rpx;
  padding: 8rpx 28rpx 24rpx;
  position: relative;
}

.sku-sheet__cover {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
  background: $ok-slate-50;
}

.sku-sheet__meta {
  flex: 1;
  min-width: 0;
  padding-right: 48rpx;
}

.sku-sheet__title {
  font-size: 30rpx;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.35;
}

.sku-sheet__sub {
  display: block;
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $ok-slate-500;
  line-height: 1.4;
}

.sku-sheet__price-row {
  margin-top: 16rpx;
  display: flex;
  align-items: baseline;
  gap: 12rpx;
}

.sku-sheet__price {
  font-size: 36rpx;
  font-weight: 900;
  color: $ok-forest-green;
}

.sku-sheet__list-price {
  font-size: 24rpx;
  color: $ok-slate-400;
  text-decoration: line-through;
}

.sku-sheet__close {
  position: absolute;
  top: 0;
  right: 20rpx;
  width: 56rpx;
  height: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sku-sheet__close-txt {
  font-size: 44rpx;
  font-weight: 300;
  color: $ok-slate-400;
  line-height: 1;
}

.sku-sheet__section {
  padding: 0 28rpx 24rpx;
}

.sku-sheet__section--qty {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
}

.sku-sheet__label {
  display: block;
  font-size: 26rpx;
  font-weight: 800;
  color: #334155;
  margin-bottom: 16rpx;
}

.sku-sheet__section--qty .sku-sheet__label {
  margin-bottom: 0;
}

.sku-sheet__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
}

.sku-chip {
  padding: 12rpx 28rpx;
  border-radius: 12rpx;
  border: 1rpx solid #e2e8f0;
  font-size: 24rpx;
  color: #334155;
  font-weight: 700;
}

.sku-chip--on {
  border-color: $ok-forest-green;
  background: #ecfdf5;
  color: $ok-forest-green;
}

.sku-chip--disabled {
  opacity: 0.45;
}

.sku-qty {
  display: flex;
  align-items: center;
  gap: 24rpx;
}

.sku-qty__btn {
  width: 56rpx;
  height: 56rpx;
  border-radius: 12rpx;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32rpx;
  font-weight: 600;
  color: #334155;
}

.sku-qty__num {
  min-width: 40rpx;
  text-align: center;
  font-size: 28rpx;
  font-weight: 800;
  color: #1e293b;
}

.sku-sheet__foot {
  padding: 16rpx 28rpx 8rpx;
}

.sku-sheet__btn {
  width: 100%;
  height: 88rpx;
  line-height: 88rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 30rpx;
  font-weight: 900;
  border: none;
}

.sku-sheet__btn::after {
  border: none;
}
</style>