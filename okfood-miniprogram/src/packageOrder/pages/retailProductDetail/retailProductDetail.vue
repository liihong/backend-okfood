<template>
  <view class="page">
    <OkNavbar show-back :title="detail?.title || '商品详情'" />
    <view v-if="loading" class="state">加载中…</view>
    <view v-else-if="!detail" class="state state--err">商品不存在或已下架</view>
    <scroll-view v-else scroll-y class="scroll" :show-scrollbar="false" :style="scrollStyle">
      <swiper v-if="gallery.length" class="gallery" circular indicator-dots>
        <swiper-item v-for="(url, i) in gallery" :key="i">
          <image class="gallery__img" :src="url" mode="aspectFill" />
        </swiper-item>
      </swiper>
      <view v-else class="gallery gallery--empty">
        <text class="gallery__placeholder">暂无图片</text>
      </view>

      <view class="head-card">
        <text class="head-card__title">{{ detail.title }}</text>
        <text v-if="detail.subtitle" class="head-card__sub">{{ detail.subtitle }}</text>
        <view class="head-card__price-row">
          <text class="head-card__price">¥{{ priceText }}</text>
          <text v-if="listPriceText" class="head-card__list-price">¥{{ listPriceText }}</text>
        </view>
      </view>

      <view v-if="skus.length > 1" class="spec-card">
        <text class="spec-card__label">选择规格</text>
        <view class="spec-list">
          <view
            v-for="s in skus"
            :key="s.id"
            class="spec-chip"
            :class="{ 'spec-chip--on': selectedSkuId === s.id, 'spec-chip--disabled': !skuSelectable(s) }"
            @tap="() => selectSku(s)"
          >
            <text>{{ s.spec_label || '默认' }}</text>
          </view>
        </view>
      </view>

      <view class="qty-card">
        <text class="qty-card__label">数量</text>
        <view class="qty-stepper">
          <view class="qty-btn" @tap="changeQty(-1)">−</view>
          <text class="qty-num">{{ quantity }}</text>
          <view class="qty-btn" @tap="changeQty(1)">+</view>
        </view>
      </view>

      <view v-if="detailHtml" class="detail-card">
        <text class="detail-card__title">商品详情</text>
        <rich-text class="detail-card__html" :nodes="detailHtml" />
      </view>

      <view v-if="detail.purchase_notice" class="detail-card">
        <text class="detail-card__title">购买须知</text>
        <text class="detail-card__notice">{{ detail.purchase_notice }}</text>
      </view>

      <view class="bottom-spacer" />
    </scroll-view>

    <view v-if="detail" class="bottom-bar" :style="bottomBarStyle">
      <view class="btn-share" @tap="openShareSheet">
        <text class="btn-share__txt">分享</text>
      </view>
      <button class="btn-cart" type="default" hover-class="none" @tap="addToCart">加入购物车</button>
      <button class="btn-buy" type="default" hover-class="none" @tap="buyNow">立即购买</button>
    </view>

    <view v-if="shareSheetVisible" class="share-mask" @tap="closeShareSheet">
      <view class="share-sheet" @tap.stop>
        <text class="share-sheet-title">推荐给好友</text>
        <view class="share-sheet-btn" @tap="onGeneratePoster">生成分享海报</view>
        <button class="share-sheet-btn share-sheet-btn--native" open-type="share" @tap="closeShareSheet">
          分享给微信好友
        </button>
        <view class="share-sheet-cancel" @tap="closeShareSheet">取消</view>
      </view>
    </view>

    <RetailSharePosterModal
      :visible="posterVisible"
      :spu-id="posterSpuId"
      :price-yuan="priceText"
      :cover-url="posterCoverUrl"
      @close="posterVisible = false"
    />
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { onLoad, onShow, onShareAppMessage, onShareTimeline } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import RetailSharePosterModal from '@/components/RetailSharePosterModal/RetailSharePosterModal.vue'
import { fetchRetailSpuDetail } from '@/utils/catalogApi.js'
import { addCartItem } from '@/utils/retailCart/retailCartStorage.js'
import { notifyRetailCartChanged, useRetailCart } from '@/utils/retailCart/useRetailCart.js'
import { getNavbarLayout } from '@/utils/navbar.js'
import { optimizeImageUrl } from '@/utils/imageUrl.js'
import { fitRichTextHtml } from '@/utils/richTextHtml.js'
import { parseRetailSpuIdFromQuery } from '@/utils/retailSharePoster.js'

const loading = ref(true)
const detail = ref(null)
const selectedSkuId = ref(null)
const quantity = ref(1)
const scrollStyle = ref({})
const bottomBarStyle = ref({})
const shareSheetVisible = ref(false)
const posterVisible = ref(false)
const posterSpuId = ref(0)
const { refresh: refreshCart } = useRetailCart()

const skus = computed(() => (Array.isArray(detail.value?.skus) ? detail.value.skus : []))

const selectedSku = computed(() => skus.value.find((s) => Number(s.id) === Number(selectedSkuId.value)) || null)

const gallery = computed(() => {
  const urls = detail.value?.gallery_urls
  if (!Array.isArray(urls)) return []
  return urls.map((u) => optimizeImageUrl(String(u || ''), null, 'detail')).filter(Boolean)
})

/** rich-text 不吃页面 CSS，需在 HTML 上写死 max-width 才能横向等比缩放 */
const detailHtml = computed(() => fitRichTextHtml(detail.value?.detail_html))

const priceText = computed(() => {
  const s = selectedSku.value
  if (s?.unit_price_yuan != null) return Number(s.unit_price_yuan).toFixed(2)
  const min = detail.value?.price_min_yuan
  return min != null ? Number(min).toFixed(2) : '0.00'
})

const listPriceText = computed(() => {
  const lp = selectedSku.value?.list_price_yuan
  if (lp == null || String(lp).trim() === '') return ''
  return Number(lp).toFixed(2)
})

function skuSelectable(s) {
  if (!s?.is_on_shelf) return false
  if (s.stock_limited && s.stock_remaining != null && Number(s.stock_remaining) <= 0) return false
  return true
}

function selectSku(s) {
  if (!skuSelectable(s)) {
    uni.showToast({ title: '该规格不可选', icon: 'none' })
    return
  }
  selectedSkuId.value = s.id
  quantity.value = 1
}

function changeQty(delta) {
  const d = Number(delta) || 0
  let next = Math.max(1, (Number(quantity.value) || 1) + d)
  const s = selectedSku.value
  if (s?.stock_limited && s.stock_remaining != null) {
    next = Math.min(next, Math.max(1, Number(s.stock_remaining)))
  }
  next = Math.min(next, 50)
  quantity.value = next
}

function buildCartPayload() {
  const s = selectedSku.value
  const d = detail.value
  if (!s || !d) return null
  const title = s.spec_label ? `${d.title} · ${s.spec_label}` : d.title
  const cover = gallery.value[0] || d.cover_image_url || ''
  return {
    retailProductId: Number(s.id),
    spuId: Number(d.id),
    spuTitle: d.title,
    specLabel: s.spec_label || '',
    title,
    unitPriceYuan: s.unit_price_yuan,
    listPriceYuan: s.list_price_yuan,
    coverImageUrl: cover,
    stockRemaining: s.stock_remaining != null ? Number(s.stock_remaining) : null,
    stockLimited: !!s.stock_limited,
    soldCount: s.sold_count != null ? Number(s.sold_count) : 0,
  }
}

function addToCart() {
  const payload = buildCartPayload()
  if (!payload) {
    uni.showToast({ title: '请选择规格', icon: 'none' })
    return
  }
  const res = addCartItem(payload, quantity.value)
  if (!res.ok) {
    uni.showToast({ title: res.msg || '加入失败', icon: 'none' })
    return
  }
  notifyRetailCartChanged()
  refreshCart()
  uni.showToast({ title: '已加入购物车', icon: 'none' })
}

function buyNow() {
  const payload = buildCartPayload()
  if (!payload) {
    uni.showToast({ title: '请选择规格', icon: 'none' })
    return
  }
  const res = addCartItem(payload, quantity.value)
  if (!res.ok) {
    uni.showToast({ title: res.msg || '加入失败', icon: 'none' })
    return
  }
  notifyRetailCartChanged()
  refreshCart()
  uni.navigateTo({ url: '/packageOrder/pages/retailCheckout/retailCheckout' })
}

async function loadDetail(spuId) {
  loading.value = true
  try {
    const data = await fetchRetailSpuDetail(spuId)
    detail.value = data
    const list = Array.isArray(data?.skus) ? data.skus : []
    const first = list.find(skuSelectable) || list[0]
    selectedSkuId.value = first?.id ?? null
    quantity.value = 1
  } finally {
    loading.value = false
  }
}

const posterCoverUrl = computed(() => {
  const d = detail.value
  const urls = d?.gallery_urls
  if (Array.isArray(urls)) {
    const first = urls.find((u) => String(u || '').trim())
    if (first) return String(first).trim()
  }
  return d?.cover_image_url != null ? String(d.cover_image_url).trim() : ''
})

function enableWechatShareMenus() {
  // #ifdef MP-WEIXIN
  if (typeof wx !== 'undefined' && typeof wx.showShareMenu === 'function') {
    wx.showShareMenu({
      withShareTicket: true,
      menus: ['shareAppMessage', 'shareTimeline'],
    })
  }
  // #endif
}

function buildSharePayload() {
  const d = detail.value
  const id = posterSpuId.value || Number(d?.id || 0)
  const name = d && d.title ? String(d.title).trim() : '商品'
  const title = `给你推荐：${name} ¥${priceText.value}`
  const path = `/packageOrder/pages/retailProductDetail/retailProductDetail?spu_id=${encodeURIComponent(String(id))}`
  const imageUrl = posterCoverUrl.value
  return {
    title,
    path,
    query: `spu_id=${encodeURIComponent(String(id))}`,
    imageUrl,
  }
}

function openShareSheet() {
  if (!detail.value) return
  shareSheetVisible.value = true
}

function closeShareSheet() {
  shareSheetVisible.value = false
}

function onGeneratePoster() {
  closeShareSheet()
  const id = Number(detail.value?.id || posterSpuId.value || 0)
  if (!Number.isFinite(id) || id < 1) {
    uni.showToast({ title: '商品无效', icon: 'none' })
    return
  }
  posterSpuId.value = id
  posterVisible.value = true
}

onLoad((options) => {
  const id = parseRetailSpuIdFromQuery(options)
  posterSpuId.value = id
  if (id > 0) loadDetail(id)
  else {
    loading.value = false
    detail.value = null
  }
})

onShow(() => {
  enableWechatShareMenus()
})

onShareAppMessage(() => {
  const { title, path, imageUrl } = buildSharePayload()
  const payload = { title, path }
  if (imageUrl) payload.imageUrl = imageUrl
  return payload
})

onShareTimeline(() => {
  const { title, query, imageUrl } = buildSharePayload()
  const payload = { title, query }
  if (imageUrl) payload.imageUrl = imageUrl
  return payload
})

onMounted(() => {
  const { navBarTotal } = getNavbarLayout()
  scrollStyle.value = { height: `calc(100vh - ${navBarTotal}px - 56px)` }
  bottomBarStyle.value = { paddingBottom: 'env(safe-area-inset-bottom)' }
})
</script>

<style lang="scss" scoped>
.page {
  min-height: 100vh;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
}
.state {
  padding: 48px 16px;
  text-align: center;
  color: #64748b;
}
.state--err {
  color: #ef4444;
}
.scroll {
  flex: 1;
}
.gallery {
  width: 100%;
  height: 280px;
  background: #fff;
}
.gallery--empty {
  display: flex;
  align-items: center;
  justify-content: center;
}
.gallery__img {
  width: 100%;
  height: 280px;
}
.gallery__placeholder {
  color: #94a3b8;
}
.head-card {
  margin: 12px;
  padding: 16px;
  background: #fff;
  border-radius: 12px;
}
.head-card__title {
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}
.head-card__sub {
  display: block;
  margin-top: 6px;
  font-size: 13px;
  color: #64748b;
}
.head-card__price-row {
  margin-top: 12px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.head-card__price {
  font-size: 22px;
  font-weight: 700;
  color: #0d5c46;
}
.head-card__list-price {
  font-size: 13px;
  color: #94a3b8;
  text-decoration: line-through;
}
.spec-card,
.qty-card,
.detail-card {
  margin: 0 12px 12px;
  padding: 14px 16px;
  background: #fff;
  border-radius: 12px;
}
.detail-card {
  overflow: hidden;
}
.spec-card__label,
.qty-card__label,
.detail-card__title {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  display: block;
}
.spec-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.spec-chip {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  font-size: 13px;
  color: #334155;
}
.spec-chip--on {
  border-color: #0d5c46;
  background: #ecfdf5;
  color: #0d5c46;
}
.spec-chip--disabled {
  opacity: 0.45;
}
.qty-stepper {
  display: flex;
  align-items: center;
  gap: 16px;
}
.qty-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}
.qty-num {
  min-width: 24px;
  text-align: center;
  font-size: 16px;
}
.detail-card__html {
  width: 100%;
  overflow: hidden;
  font-size: 14px;
  line-height: 1.6;
  color: #475569;
  word-break: break-word;
}
.detail-card__notice {
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
  white-space: pre-wrap;
}
.bottom-spacer {
  height: 80px;
}
.bottom-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  z-index: 10;
}
.btn-share {
  flex: 0 0 52px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.btn-share__txt {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}
.btn-cart,
.btn-buy {
  flex: 1;
  height: 44px;
  line-height: 44px;
  border-radius: 22px;
  font-size: 15px;
  border: none;
}
.btn-cart {
  background: #ecfdf5;
  color: #0d5c46;
}
.btn-buy {
  background: #0d5c46;
  color: #fff;
}
.share-mask {
  position: fixed;
  inset: 0;
  z-index: 110;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-end;
}
.share-sheet {
  width: 100%;
  padding: 16px 16px calc(16px + env(safe-area-inset-bottom));
  background: #fff;
  border-radius: 16px 16px 0 0;
  box-sizing: border-box;
}
.share-sheet-title {
  display: block;
  text-align: center;
  font-size: 15px;
  font-weight: 650;
  color: #0f172a;
  margin-bottom: 12px;
}
.share-sheet-btn {
  width: 100%;
  height: 44px;
  line-height: 44px;
  border-radius: 10px;
  background: #f8fafc;
  color: #0f172a;
  font-size: 15px;
  text-align: center;
  margin-bottom: 8px;
  border: none;
}
.share-sheet-btn--native {
  padding: 0;
}
.share-sheet-btn::after {
  border: none;
}
.share-sheet-cancel {
  height: 44px;
  line-height: 44px;
  text-align: center;
  color: #64748b;
  font-size: 15px;
}
</style>
