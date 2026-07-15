<template>
  <view
    v-if="layout === 'featured'"
    class="featured-dish-card"
    @click="emit('tap', item)"
  >
    <view class="featured-dish-card__img-wrap">
      <text class="featured-dish-card__hot">HOT</text>
      <image
        class="featured-dish-card__img"
        :src="displayImg"
        mode="aspectFill"
        :lazy-load="lazyLoad"
        @error="onImgErr"
      />
    </view>
    <view class="featured-dish-card__body">
      <view class="featured-dish-card__title-row">
        <text class="featured-dish-card__name">{{ item.name }}</text>
        <text v-if="item.spiceLabel" class="featured-dish-card__spice">{{ item.spiceLabel }}</text>
      </view>
      <text v-if="showIngredients && item.ingredients" class="featured-dish-card__ingredients">
        配料：{{ item.ingredients }}
      </text>
      <view v-if="kcalText" class="featured-dish-card__kcal">
        <text class="featured-dish-card__kcal-icon">🔥</text>
        <text class="featured-dish-card__kcal-txt">仅 {{ kcalText }} kcal</text>
      </view>
      <view class="featured-dish-card__footer">
        <view class="featured-dish-card__price-block">
          <text class="featured-dish-card__price-label">自律体验价</text>
          <text v-if="priceText != null" class="featured-dish-card__price">¥{{ priceText }}</text>
          <text v-else class="featured-dish-card__price featured-dish-card__price--pending">待公布</text>
        </view>
        <view v-if="showFeaturedSelectAction" class="featured-dish-card__cta">
          <text class="featured-dish-card__cta-txt">立即购买 ›</text>
        </view>
        <text v-else-if="showFeaturedSoldOut" class="featured-dish-card__soldout">售罄</text>
      </view>
    </view>
  </view>

  <view
    v-else-if="layout === 'list'"
    class="menu-dish-card menu-dish-card--list"
    @click="emit('tap', item)"
  >
    <image
      class="menu-dish-card__list-img"
      :src="displayImg"
      mode="aspectFill"
      lazy-load
      @error="onImgErr"
    />
    <view class="menu-dish-card__list-body">
     <view class="menu-dish-card__list-head">
        <text class="menu-dish-card__name menu-dish-card__name--list">{{ item.name }}</text>
       <text v-if="showDayLabel && item.day" class="menu-dish-card__list-day-tag">{{ item.day }}</text>
      </view>
      <text v-if="showIngredients && item.ingredients" class="menu-dish-card__list-desc">
        {{ item.ingredients }}
      </text>
     <text v-if="item.spiceLabel" class="menu-dish-card__spice menu-dish-card__spice--list">{{ item.spiceLabel
      }}</text>
      <view class="menu-dish-card__list-footer">
        <view class="menu-dish-card__price-group">
          <text v-if="priceText != null" class="menu-dish-card__price menu-dish-card__price--list">¥{{ priceText }}</text>
          <text v-else class="menu-dish-card__price menu-dish-card__price--pending">待公布</text>
          <text v-if="showListPrice" class="menu-dish-card__list-price">¥{{ listPriceText }}</text>
        </view>
        <view class="menu-dish-card__list-actions">
          <view v-if="showListStockRemaining" class="menu-dish-card__stock-badge">
            <text class="menu-dish-card__stock-badge-txt">剩 {{ item.singleStockRemaining ?? 0 }} 份</text>
          </view>
          <view v-if="showListSelectAction" class="menu-dish-card__add-btn">
            <text class="menu-dish-card__add-icon">+</text>
          </view>
          <text v-else-if="showListSoldOut" class="menu-dish-card__list-soldout">售罄</text>
        </view>
      </view>
    </view>
  </view>

  <view
    v-else
    class="menu-dish-card menu-dish-card--grid"
    @click="emit('tap', item)"
  >
    <view class="menu-dish-card__img-wrap">
      <text v-if="showDayLabel && item.day" class="menu-dish-card__day-tag">{{ item.day }}</text>
      <image
        class="menu-dish-card__img"
        :src="displayImg"
        mode="aspectFill"
        lazy-load
        @error="onImgErr"
      />
    </view>
    <view class="menu-dish-card__body">
      <view class="menu-dish-card__title-row">
        <text class="menu-dish-card__name">{{ item.name }}</text>
        <text v-if="item.spiceLabel" class="menu-dish-card__spice">{{ item.spiceLabel }}</text>
      </view>
      <view class="menu-dish-card__price-row">
        <text class="menu-dish-card__price-label">自律体验价</text>
        <text v-if="priceText != null" class="menu-dish-card__price">¥{{ priceText }}</text>
        <text v-else class="menu-dish-card__price menu-dish-card__price--pending">待公布</text>
      </view>
      <text v-if="showIngredients" class="menu-dish-card__ingredients">配料：{{ item.ingredients }}</text>
    </view>
  </view>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { formatMenuPrice, isSingleOrderStockAvailable } from '@/utils/menuApi.js'

const props = defineProps({
  item: { type: Object, required: true },
  layout: { type: String, default: 'grid' },
  showDayLabel: { type: Boolean, default: true },
  showIngredients: { type: Boolean, default: true },
  /** 首页推荐首屏可关 lazy-load */
  lazyLoad: { type: Boolean, default: true },
})

const emit = defineEmits(['tap'])

const priceText = computed(() => formatMenuPrice(props.item?.price))

const listPriceText = computed(() =>
  formatMenuPrice(props.item?.listPrice ?? props.item?.list_price_yuan),
)

const showListPrice = computed(() => {
  const sale = priceText.value
  const list = listPriceText.value
  if (sale == null || list == null) return false
  return Number(list) > Number(sale)
})

/** 排餐项且已拉取库存（首页推荐 / 周菜单列表） */
const showMenuStockInfo = computed(
  () => props.item?.stockLoaded === true && !props.item?.isRetail,
)

const menuStockAvailable = computed(() => isSingleOrderStockAvailable(props.item))

/** 首页推荐：有库存时展示购买按钮 */
const showFeaturedSelectAction = computed(() => {
  if (!showMenuStockInfo.value) return true
  return menuStockAvailable.value
})

/** 首页推荐：无库存时展示售罄 */
const showFeaturedSoldOut = computed(
  () => showMenuStockInfo.value && !menuStockAvailable.value,
)

/** 周菜单列表：已拉取库存且为排餐项（非零售） */
const showListStockInfo = computed(() => showMenuStockInfo.value)

const listStockAvailable = computed(() => menuStockAvailable.value)

/** 有剩余库存时展示份数 */
const showListStockRemaining = computed(
  () => showListStockInfo.value && listStockAvailable.value,
)

/** 库存为 0 时展示售罄文案 */
const showListSoldOut = computed(
  () => showListStockInfo.value && !listStockAvailable.value,
)

/** 零售仍展示按钮；排餐项库存为 0 时隐藏选餐 */
const showListSelectAction = computed(() => {
  if (props.item?.isRetail) return true
  if (!showListStockInfo.value) return true
  return listStockAvailable.value
})

const kcalText = computed(() => {
  const raw = props.item?.kcal ?? props.item?.calories ?? props.item?.calorie_kcal
  if (raw == null || raw === '') return ''
  const n = Math.floor(Number(raw))
  return Number.isFinite(n) && n > 0 ? String(n) : ''
})

const fallbackImg =
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=400'

const displayImg = ref('')

watch(
  () => props.item?.img,
  (src) => {
    displayImg.value =
      typeof src === 'string' && src.trim() ? src.trim() : fallbackImg
  },
  { immediate: true },
)

function originalImgFallback() {
  const raw = props.item?.imgOriginal ?? props.item?.pic ?? props.item?.img
  if (typeof raw === 'string' && raw.trim()) return raw.trim()
  return fallbackImg
}

function onImgErr() {
  const fallback = originalImgFallback()
  if (displayImg.value !== fallback) displayImg.value = fallback
}
</script>

<style lang="scss" scoped>
.featured-dish-card {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 24rpx;
  padding: 24rpx;
  background: #fff;
  border-radius: 32rpx;
  box-shadow: 0 8rpx 32rpx rgba(15, 23, 42, 0.06);
}

.featured-dish-card__img-wrap {
  position: relative;
  width: 200rpx;
  min-width: 200rpx;
  height: 200rpx;
  border-radius: 24rpx;
  overflow: hidden;
  background: $ok-slate-50;
  flex-shrink: 0;
}

.featured-dish-card__hot {
  position: absolute;
  top: 12rpx;
  left: 12rpx;
  z-index: 2;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  background: #ef4444;
  color: #fff;
  font-size: 18rpx;
  font-weight: 900;
  letter-spacing: 0.04em;
  line-height: 1.4;
}

.featured-dish-card__img {
  width: 100%;
  height: 100%;
}

.featured-dish-card__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.featured-dish-card__title-row {
  display: flex;
  align-items: flex-start;
  gap: 12rpx;
  margin-bottom: 8rpx;
}

.featured-dish-card__name {
  flex: 1;
  min-width: 0;
  font-size: 32rpx;
  font-weight: 900;
  color: #1e293b;
  line-height: 1.35;
}

.featured-dish-card__spice {
  flex-shrink: 0;
  font-size: 20rpx;
  font-weight: 700;
  color: $ok-slate-500;
  background: $ok-slate-100;
  padding: 4rpx 14rpx;
  border-radius: 999rpx;
  line-height: 1.4;
}

.featured-dish-card__ingredients {
  font-size: 22rpx;
  color: $ok-slate-500;
  line-height: 1.45;
  margin-bottom: 12rpx;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.featured-dish-card__kcal {
  display: inline-flex;
  align-items: center;
  gap: 6rpx;
  align-self: flex-start;
  padding: 6rpx 16rpx;
  border-radius: 999rpx;
  background: #ecfdf5;
  margin-bottom: 16rpx;
}

.featured-dish-card__kcal-icon {
  font-size: 20rpx;
  line-height: 1;
}

.featured-dish-card__kcal-txt {
  font-size: 20rpx;
  font-weight: 800;
  color: #166534;
  line-height: 1.3;
}

.featured-dish-card__footer {
  margin-top: auto;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
}

.featured-dish-card__price-block {
  display: flex;
  flex-direction: column;
  gap: 2rpx;
}

.featured-dish-card__price-label {
  font-size: 20rpx;
  color: $ok-slate-400;
  font-weight: 600;
}

.featured-dish-card__price {
  font-size: 40rpx;
  font-weight: 900;
  color: $ok-forest-green;
  line-height: 1.1;
}

.featured-dish-card__price--pending {
  font-size: 28rpx;
  font-weight: 800;
  color: $ok-slate-400;
}

.featured-dish-card__cta {
  flex-shrink: 0;
  padding: 14rpx 28rpx;
  border-radius: 999rpx;
  background: $ok-forest-green;
}

.featured-dish-card__cta-txt {
  font-size: 24rpx;
  font-weight: 900;
  color: #fff;
  line-height: 1.2;
}

.featured-dish-card__soldout {
  flex-shrink: 0;
  font-size: 26rpx;
  font-weight: 900;
  color: $ok-slate-400;
  letter-spacing: 2rpx;
  line-height: 1.2;
  padding: 14rpx 8rpx;
}

.menu-dish-card {
  background: #fff;
  border-radius: 48rpx;
  overflow: hidden;
  border: 1px solid $ok-slate-100;
  box-shadow: 0 8rpx 24rpx rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
}

.menu-dish-card__img-wrap {
  width: 100%;
  height: 0;
  padding-bottom: 100%;
  background: $ok-slate-50;
  position: relative;
  overflow: hidden;
}

.menu-dish-card__img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.menu-dish-card__day-tag {
  position: absolute;
  top: 20rpx;
  left: 20rpx;
  background: $ok-forest-green;
  color: #fff;
  font-size: 24rpx;
  font-weight: 900;
  padding: 6rpx 16rpx;
  border-radius: 16rpx;
  z-index: 10;
}

.menu-dish-card__body {
  padding: 24rpx;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.menu-dish-card__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12rpx;
  margin-bottom: 4rpx;
}

.menu-dish-card__name {
  flex: 1;
  min-width: 0;
  font-size: 26rpx;
  font-weight: 950;
  color: #333;
}

.menu-dish-card__spice {
  flex-shrink: 0;
  font-size: 18rpx;
  font-weight: 900;
  color: #9a3412;
  background: #fff7ed;
  border: 1rpx solid #fed7aa;
  padding: 4rpx 12rpx;
  border-radius: 12rpx;
  line-height: 1.3;
}

.menu-dish-card__price-row {
  display: flex;
  align-items: baseline;
  gap: 8rpx;
  margin-bottom: 12rpx;
}

.menu-dish-card__price-label {
  font-size: 16rpx;
  color: $ok-slate-400;
  font-weight: 900;
}

.menu-dish-card__price {
  font-size: 32rpx;
  font-weight: 1000;
  font-style: italic;
  color: $ok-forest-green;
}

.menu-dish-card__price--pending {
  font-size: 26rpx;
  font-style: normal;
  font-weight: 800;
  color: $ok-slate-400;
}

.menu-dish-card__ingredients {
  font-size: 18rpx;
  color: $ok-slate-400;
  line-height: 1.4;
  font-weight: 700;
  max-height: 2.8em;
  overflow: hidden;
  text-overflow: ellipsis;
}

.menu-dish-card--list {
  flex-direction: row;
  align-items: flex-start;
  border-radius: 24rpx;
  padding: 20rpx;
  gap: 20rpx;
  margin-bottom: 20rpx;
  border: 1rpx solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 4rpx 20rpx rgba(15, 23, 42, 0.04);
}

.menu-dish-card__list-img {
  width: 160rpx;
  height: 160rpx;
  border-radius: 16rpx;
  flex-shrink: 0;
  background: $ok-slate-50;
}

.menu-dish-card__list-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.menu-dish-card__name--list {
  font-size: 28rpx;
}

.menu-dish-card__list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12rpx;
}

.menu-dish-card__list-day-tag {
  flex-shrink: 0;
  font-size: 22rpx;
  font-weight: 700;
  color: #5a9a4a;
  background: rgba(115, 176, 84, 0.1);
  border: 1rpx solid rgba(115, 176, 84, 0.22);
  padding: 4rpx 14rpx;
  border-radius: 12rpx;
  line-height: 1.3;
}
.menu-dish-card__list-desc {
  margin-top: 8rpx;
  font-size: 22rpx;
  color: $ok-slate-400;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}

.menu-dish-card__spice--list {
  align-self: flex-start;
  margin-top: 8rpx;
}
.menu-dish-card__list-footer {
  margin-top: 12rpx;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16rpx;
}

.menu-dish-card__list-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 4rpx;
    min-width: 44rpx;
    margin-top: -40rpx;
}

.menu-dish-card__stock-badge {
  padding: 2rpx 0;
  white-space: nowrap;
}

.menu-dish-card__stock-badge-txt {
  font-size: 20rpx;
  font-weight: 800;
  color: $ok-forest-green;
  line-height: 1.2;
}

.menu-dish-card__list-soldout {
  font-size: 24rpx;
  font-weight: 900;
  color: $ok-slate-400;
  letter-spacing: 2rpx;
  line-height: 1.2;
  white-space: nowrap;
}

.menu-dish-card__price-group {
  display: flex;
  align-items: baseline;
  gap: 10rpx;
  min-width: 0;
}

.menu-dish-card__price--list {
  font-size: 34rpx;
  font-style: normal;
}

.menu-dish-card__list-price {
  font-size: 24rpx;
  font-weight: 600;
  color: $ok-slate-400;
  text-decoration: line-through;
  line-height: 1.2;
}

/** 右下角加购：小圆形 + 号 */
.menu-dish-card__add-btn {
  flex-shrink: 0;
  width: 44rpx;
    height: 44rpx;
    border-radius: 50%;
  background: $ok-forest-green;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4rpx 12rpx rgba(115, 176, 84, 0.24);
}

.menu-dish-card__add-icon {
  font-size: 32rpx;
  font-weight: 300;
  color: #fff;
  line-height: 1;
  margin-top: -2rpx;
}
</style>
