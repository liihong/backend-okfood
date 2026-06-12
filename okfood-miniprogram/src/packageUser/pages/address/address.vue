<template>
  <view class="page">
    <OkNavbar show-back :title="navbarTitle" />
    <scroll-view scroll-y class="scroll" :style="scrollStyle" :show-scrollbar="false">
      <view class="page-address">
        <view v-if="profileLoaded" class="notice notice--info">
          <text class="notice-txt">{{ sfEffectiveNotice }}</text>
        </view>
        <view class="form-box">
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">联系人姓名</text>
              <text class="field-required">*</text>
            </view>
            <input v-model="form.name" class="form-input-p" placeholder="请输入收货人姓名" />
          </view>
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">手机号码</text>
              <text class="field-required">*</text>
            </view>
            <view class="form-input-p form-phone-slot">
              <button
                v-if="!displayPhone"
                class="form-phone-wx-btn"
                open-type="getPhoneNumber"
                @getphonenumber="onWxPhoneNumber"
              >
                点我快速授权手机号码
              </button>
              <view v-else class="form-phone-filled">
                <text class="form-phone-digits">{{ displayPhone }}</text>
                <button
                  class="form-phone-wx-btn form-phone-wx-btn--inline"
                  open-type="getPhoneNumber"
                  @getphonenumber="onWxPhoneNumber"
                >
                  更换
                </button>
              </view>
            </view>
          </view>
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">收餐地址</text>
              <text class="field-required">*</text>
            </view>
            <view
              class="form-input-p form-textarea map-addr-readonly"
              hover-class="map-addr-readonly--hover"
              @tap="chooseMapLocation"
            >
              <text v-if="form.mapLocationText" class="map-addr-readonly__text">{{ form.mapLocationText }}</text>
              <text v-else class="map-addr-readonly__placeholder">请先在「地图选点」</text>
            </view>
            <view class="map-pick-slot">
              <view class="map-pick-actions">
                <button class="btn-map-pick" hover-class="none" @tap="chooseMapLocation">地图选点</button>
                <text v-if="coords" class="coords-bound-hint">已绑定地图坐标</text>
              </view>
            </view>
          </view>
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">门牌号/单元楼层</text>
              <text class="field-required">*</text>
            </view>
            <input
              v-model="form.doorDetail"
              maxlength="500"
              class="form-input-p"
placeholder="例：C座 2707"
            />
          </view>
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">忌口/备注</text>
            </view>
            <input
              v-model="form.remarks"
              class="form-input-p form-remarks"
placeholder="备注"
            />
          </view>
        </view>
        <!-- 底部留白；主按钮在 footer 固定，避免与最后一项重叠 -->
        <view class="scroll-tail" />
      </view>
    </scroll-view>
    <view class="footer">
      <button class="btn-save-addr" hover-class="none" @tap="save">保存配送信息</button>
    </view>
  </view>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { onLoad, onShow } from '@dcloudio/uni-app'
import {
  sfPushEffectiveEditNotice,
  sfPushEffectiveSaveAlert,
} from '@/utils/memberSfPushEffectiveHint.js'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { getPageScrollStyle, FIXED_FOOTER_RESERVE_PX } from '@/utils/navbar.js'
import { showOkAlert } from '@/utils/okAlert.js'
import { request, getMemberToken } from '@/utils/api.js'
import { markMinePageNeedsRefresh } from '@/utils/minePageRefresh.js'
import { normalizeAddressList, addressLineFromStructured } from '@/utils/addressApi.js'

const scrollStyle = ref({})

function applyScrollLayout() {
  scrollStyle.value = getPageScrollStyle(FIXED_FOOTER_RESERVE_PX)
}
import { hasWxPhoneAuthDetail, wxMiniMemberLoginAndStore } from '@/utils/wxMemberLogin.js'

/** 导航标题；购卡成功后跳转时可传 title=完善配送信息 */
const navbarTitle = ref('地址管理 👌')

const form = reactive({
  name: '',
  phone: '',
  mapLocationText: '',
  doorDetail: '',
  remarks: '',
})

/** 坐标仅提交接口；与 map_location_text / door_detail 一并保存 */
const coords = ref(null)

/** 当前编辑的地址 id；无则 POST 新增，有则 PATCH */
const addressId = ref('')

/** GET /api/user/me：顺丰推单状态，用于生效说明 */
const memberProfile = ref(null)
const profileLoaded = ref(false)

const sfEffectiveNotice = computed(() => sfPushEffectiveEditNotice(memberProfile.value))

const displayPhone = computed(() => {
  const d = String(form.phone || '').replace(/\D/g, '')
  return d.length === 11 ? d : ''
})

async function onWxPhoneNumber(e) {
  const detail = e?.detail ?? {}
  const errMsg = String(detail.errMsg || '')
  if (errMsg.includes('deny') || errMsg.includes('cancel')) {
    uni.showToast({ title: '已取消授权', icon: 'none' })
    return
  }
  if (!hasWxPhoneAuthDetail(detail)) {
    uni.showToast({
      title: errMsg || '未收到授权数据，请重试',
      icon: 'none',
    })
    return
  }
  uni.showLoading({ title: '获取中', mask: true })
  try {
    await wxMiniMemberLoginAndStore(detail)
    const p = uni.getStorageSync('memberPhone')
    form.phone = p ? String(p).replace(/\D/g, '') : ''
    if (!form.phone || form.phone.length !== 11) {
      throw new Error('未解析到手机号，请重试')
    }
    uni.hideLoading()
    setTimeout(() => {
      uni.showToast({ title: '已填入手机号', icon: 'success' })
    }, 50)
  } catch (err) {
    uni.hideLoading()
    setTimeout(() => {
      uni.showToast({
        title: err instanceof Error ? err.message : '获取失败',
        icon: 'none',
        duration: 2800,
      })
    }, 50)
  }
}

function memberPhonePath() {
  const p = uni.getStorageSync('memberPhone')
  return p ? String(p).replace(/\D/g, '') : ''
}

function strAddrPart(v) {
  if (v == null) return ''
  if (typeof v === 'string') return v.trim()
  if (typeof v === 'number' && Number.isFinite(v)) return String(v)
  return String(v).trim()
}

/** 接口条目 → 表单：仅存 map_location_text、door_detail 与联系人 */
function applyAddressItem(item) {
  if (!item || typeof item !== 'object') return
  addressId.value = item.id != null ? String(item.id) : ''
  if (item.contact_name != null) form.name = String(item.contact_name)
  else if (item.contactName != null) form.name = String(item.contactName)
  if (item.contact_phone != null) form.phone = String(item.contact_phone).replace(/\D/g, '')
  else if (item.contactPhone != null) form.phone = String(item.contactPhone).replace(/\D/g, '')
  if (item.remarks != null) form.remarks = String(item.remarks)

  form.mapLocationText = strAddrPart(
    item.map_location_text ?? item.mapLocationText,
  )
  form.doorDetail = strAddrPart(item.door_detail ?? item.doorDetail)

  const loc = item.location
  const latRaw = loc && typeof loc === 'object' && loc.lat != null ? Number(loc.lat) : NaN
  const lngRaw = loc && typeof loc === 'object' && loc.lng != null ? Number(loc.lng) : NaN
  const hasLoc = Number.isFinite(latRaw) && Number.isFinite(lngRaw)
  coords.value = hasLoc ? { lat: latRaw, lng: lngRaw } : null
}

function clearForm() {
  form.name = ''
  form.phone = ''
  form.mapLocationText = ''
  form.doorDetail = ''
  form.remarks = ''
  coords.value = null
  addressId.value = ''
}

function applyCoordsAndPoiMeta(la, lo, meta) {
  if (!Number.isFinite(la) || !Number.isFinite(lo)) {
    uni.showToast({
      title: '未获取到位置坐标，请重选',
      icon: 'none',
    })
    return false
  }
  coords.value = { lat: la, lng: lo }
  const name = String(meta?.name ?? '').trim()
  form.mapLocationText = name || form.mapLocationText
  return true
}

/**
 * 选点后立即校验是否落在启用配送片区内。
 * @returns {Promise<boolean>} 在范围内返回 true；否则弹窗提示并返回 false（不回填）
 */
async function ensureCoordsInDeliveryRegion(la, lo) {
  try {
    const resp = await request('/api/user/me/delivery-region/check', {
      method: 'POST',
      data: { location: { lng: lo, lat: la } },
    })
    const inRegion =
      resp && typeof resp === 'object' ? resp.in_region === true : false
    return inRegion
  } catch (err) {
    uni.showToast({
      title: err instanceof Error ? err.message : '配送范围校验失败，请重试',
      icon: 'none',
      duration: 2800,
    })
    return false
  }
}

function openChooseLocationCentered(lat, lng) {
  const opts = {}
  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    opts.latitude = lat
    opts.longitude = lng
  }
  uni.chooseLocation({
    ...opts,
    async success(res) {
      const name = String(res.name ?? '').trim()
      const la = res.latitude != null ? Number(res.latitude) : NaN
      const lo = res.longitude != null ? Number(res.longitude) : NaN
      if (!Number.isFinite(la) || !Number.isFinite(lo)) {
        uni.showToast({ title: '未获取到位置坐标，请重选', icon: 'none' })
        return
      }
      uni.showLoading({ title: '校验配送范围…', mask: true })
      const ok = await ensureCoordsInDeliveryRegion(la, lo)
      uni.hideLoading()
      if (!ok) {
        showOkAlert({
          title: '超出配送范围',
          content: '当前位置不在配送范围内，请重新选择位置。',
          showCancel: false,
          confirmText: '我知道了',
        })
        return
      }
      applyCoordsAndPoiMeta(la, lo, { name })
    },
    fail(err) {
      const msg = err?.errMsg != null ? String(err.errMsg) : ''
      if (msg.includes('cancel') || msg.includes('deny')) {
        return
      }
      uni.showToast({
        title: msg || '打开地图失败',
        icon: 'none',
        duration: 3200,
      })
    },
  })
}

/** 微信地图选点：先读当前位置作为地图中心，便于在附近选点；定位失败则仍打开地图（与腾讯地图选点页内可搜周边 POI） */
function chooseMapLocation() {
  // #ifdef MP-WEIXIN
  uni.showLoading({ title: '定位中…', mask: true })
  uni.getLocation({
    type: 'gcj02',
    isHighAccuracy: true,
    success(loc) {
      uni.hideLoading()
      const la = loc.latitude != null ? Number(loc.latitude) : NaN
      const lo = loc.longitude != null ? Number(loc.longitude) : NaN
      openChooseLocationCentered(la, lo)
    },
    fail(err) {
      uni.hideLoading()
      const msg = err?.errMsg != null ? String(err.errMsg) : ''
      if (msg.includes('auth deny') || msg.includes('permission')) {
        showOkAlert({
          title: '需要位置权限',
          content: '开启位置后，地图会定位到您附近，方便选择收货地点。',
          confirmText: '去设置',
          cancelText: '暂不',
          success(r) {
            if (r.confirm) {
              uni.openSetting({})
            } else {
              openChooseLocationCentered(NaN, NaN)
            }
          },
        })
        return
      }
      openChooseLocationCentered(NaN, NaN)
    },
  })
  // #endif
  // #ifndef MP-WEIXIN
  uni.showToast({ title: '请在微信小程序中使用', icon: 'none' })
  // #endif
}

/** 按 id 从列表接口取一条填入表单 */
async function loadAddressById(id) {
  const token = getMemberToken()
  if (!token) return
  try {
    const data = await request('/api/user/me/addresses', {
      method: 'GET',
    })
    const list = normalizeAddressList(data)
    const item = list.find((row) => row && String(row.id) === id)
    if (item) {
      applyAddressItem(item)
      return
    }
  } catch (_) {}
  // 与页面切换紧邻时直接 showToast 易触发基础库 Error: timeout，稍后再提示
  setTimeout(() => {
    uni.showToast({ title: '未找到该地址', icon: 'none' })
    setTimeout(() => uni.navigateBack(), 1200)
  }, 100)
}

/** POST/PATCH 与后台约定字段（仅 map_location_text + door_detail；完整展示由二者拼接） */
function buildAddressBody() {
  const mapT = form.mapLocationText.trim()
  const doorT = form.doorDetail.trim()
  const base = {
    contact_name: form.name.trim(),
    contact_phone: String(form.phone).replace(/\D/g, ''),
    remarks: (form.remarks || '').trim(),
  }
  if (coords.value != null) {
    return {
      ...base,
      map_location_text: mapT || null,
      door_detail: doorT || null,
      location: { lng: coords.value.lng, lat: coords.value.lat },
    }
  }
  return {
    ...base,
    map_location_text: mapT,
    door_detail: doorT || null,
  }
}

async function loadMemberProfile() {
  if (!getMemberToken()) {
    memberProfile.value = null
    profileLoaded.value = false
    return
  }
  try {
    memberProfile.value = await request('/api/user/me', { method: 'GET' })
    profileLoaded.value = true
  } catch {
    memberProfile.value = null
    profileLoaded.value = false
  }
}

onShow(() => {
  applyScrollLayout()
  void loadMemberProfile()
})

onLoad((options) => {
  applyScrollLayout()
  const tRaw = options && options.title != null ? String(options.title).trim() : ''
  if (tRaw && tRaw !== 'undefined') {
    try {
      navbarTitle.value = decodeURIComponent(tRaw)
    } catch {
      navbarTitle.value = tRaw
    }
  }
  const raw =
    options && options.id != null ? String(options.id).trim() : ''
  const decoded = raw ? decodeURIComponent(raw) : ''
  const id =
    decoded && decoded !== 'undefined' && decoded !== 'null' ? decoded : ''
  if (id) {
    void loadAddressById(id)
  } else {
    /* 新增：不回填 deliveryAddress；若已登录可带会员手机号便于直接保存 */
    clearForm()
    const p = memberPhonePath()
    if (p.length === 11) form.phone = p
  }
})

async function save() {
  if (!form.name?.trim()) {
    uni.showToast({ title: '请填写联系人姓名', icon: 'none' })
    return
  }
  if (!form.phone || String(form.phone).replace(/\D/g, '').length !== 11) {
    uni.showToast({ title: '请填写 11 位手机号', icon: 'none' })
    return
  }
  if (!form.mapLocationText.trim()) {
    uni.showToast({
      title: '请填写收货位置主文案，或使用地图选点',
      icon: 'none',
    })
    return
  }
  const hasCoords = coords.value != null
  if (hasCoords && !addressId.value && !form.doorDetail.trim()) {
    uni.showToast({ title: '请填写门牌号/单元楼层', icon: 'none' })
    return
  }
  const token = getMemberToken()
  if (!token) {
    uni.showToast({ title: '请先登录', icon: 'none' })
    return
  }
  const body = buildAddressBody()
  const isNewAddress = !addressId.value
  try {
    /** 服务端 `code === 200` 时 request 会 resolve；列表页 onShow 会重新拉取 */
    let saveResult
    if (addressId.value) {
      saveResult = await request(
        `/api/user/me/addresses/${encodeURIComponent(addressId.value)}`,
        { method: 'PATCH', data: body },
      )
    } else {
      saveResult = await request('/api/user/me/addresses', {
        method: 'POST',
        data: body,
      })
      if (saveResult && typeof saveResult === 'object' && saveResult.id != null) {
        addressId.value = String(saveResult.id)
      }
    }
    const bodySaved = buildAddressBody()
    const addrLine = addressLineFromStructured({
      map_location_text: bodySaved.map_location_text ?? '',
      door_detail: bodySaved.door_detail ?? '',
    })
    uni.setStorageSync('deliveryAddress', {
      name: form.name,
      phone: form.phone,
      address: addrLine,
      remarks: form.remarks,
      location: hasCoords ? { lat: coords.value.lat, lng: coords.value.lng } : null,
    })
    const alertPayload = sfPushEffectiveSaveAlert(memberProfile.value, {
      titleScheduled: isNewAddress ? '地址已保存' : '已保存',
      titleImmediate: isNewAddress ? '地址已保存' : '已保存',
      contentScheduled: '今日配送大表已同步顺丰，地址修改自下一配送日起生效；今日配送仍按原地址。',
      contentImmediate: '今日尚未向顺丰推单，地址修改保存后立即生效。',
    })
    markMinePageNeedsRefresh()
    await showOkAlert({
      title: alertPayload.title,
      content: alertPayload.content,
      showCancel: false,
      confirmText: '确定',
      tone: 'success',
    })
    uni.navigateBack()
  } catch (e) {
    uni.showToast({
      title: e instanceof Error ? e.message : '保存失败',
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
  background: #fff;
  box-sizing: border-box;
}

.scroll {
  flex: 1;
  min-height: 0;
  width: 100%;
  box-sizing: border-box;
  background: #fff;
}

.page-address {
  padding: 48rpx 40rpx 0;
}

.notice {
  background: #fffbeb;
  border: 1rpx solid #fde68a;
  border-radius: 20rpx;
  padding: 24rpx 28rpx;
  margin-bottom: 28rpx;
}

.notice--info {
  background: #eff6ff;
  border-color: #bfdbfe;
}

.notice--info .notice-txt {
  color: #1e40af;
}

.notice-txt {
  font-size: 26rpx;
  font-weight: 700;
  line-height: 1.45;
}

.scroll-tail {
  height: 24rpx;
}

.form-box {
  display: flex;
  flex-direction: column;
  gap: 30rpx;
}

.form-field {
  display: flex;
  flex-direction: column;
}

.field-label-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6rpx;
  margin-bottom: 12rpx;
}

.field-title {
  font-size: 28rpx;
  font-weight: 950;
  color: $ok-forest-green;
  line-height: 1.4;
}

.field-required {
  color: #ff3e3e;
  font-size: 32rpx;
  font-weight: 900;
  line-height: 1.2;
}

.field-optional-hint {
  font-size: 22rpx;
  font-weight: 700;
  color: #94a3b8;
  line-height: 1.2;
}

/* 小程序 input 默认高度偏小，易把占位符/文字裁成半截 */
.form-input-p {
  width: 100%;
  min-height: 104rpx;
  line-height: 44rpx;
  background: #f7f8fa;
  border: none;
  padding: 30rpx 40rpx;
  border-radius: 36rpx;
  font-weight: 800;
  font-size: 30rpx;
  color: $ok-slate-800;
  box-sizing: border-box;
}

.form-remarks {
  min-height: 120rpx;
}

.form-textarea {
  min-height: 200rpx;
  width: 100%;
  line-height: 44rpx;
  padding-top: 30rpx;
  padding-bottom: 30rpx;
  border-radius: 36rpx;
}

.map-addr-readonly {
  display: block;
  box-sizing: border-box;
}

.map-addr-readonly--hover {
  background: #eef0f3;
}

.map-addr-readonly__text {
  display: block;
  font-weight: 800;
  font-size: 30rpx;
  color: $ok-slate-800;
  line-height: 44rpx;
  word-break: break-all;
}

.map-addr-readonly__placeholder {
  display: block;
  font-weight: 800;
  font-size: 30rpx;
  color: #94a3b8;
  line-height: 44rpx;
}

.map-pick-slot {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 20rpx;
  padding-bottom: 28rpx;
}

.map-pick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 16rpx;
  align-items: center;
}

.coords-bound-hint {
  font-size: 24rpx;
  font-weight: 700;
  color: $ok-forest-green;
  line-height: 1.35;
}

.btn-map-pick {
  margin: 0;
  padding: 16rpx 36rpx;
  background: $ok-forest-green;
  color: #fff;
  border-radius: 999rpx;
  font-weight: 900;
  font-size: 28rpx;
  border: none;
  line-height: 1.35;
}

.btn-map-pick::after {
  border: none;
}

.field-hint {
  margin-top: 12rpx;
  font-size: 24rpx;
  font-weight: 650;
  color: #94a3b8;
  line-height: 1.4;
}

/* 与 .form-input-p 同灰底圆角（继承其 padding），内嵌微信手机号授权 button */
.form-phone-slot {
  display: flex;
  align-items: center;
}

.form-phone-wx-btn {
  width: 100%;
  margin: 0;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  font-weight: 800;
  font-size: 30rpx;
  line-height: 44rpx;
  color: #94a3b8;
  text-align: left;
  box-sizing: border-box;
}

.form-phone-wx-btn::after {
  border: none;
}

.form-phone-filled {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  width: 100%;
}

.form-phone-digits {
  flex: 1;
  min-width: 0;
  font-weight: 800;
  font-size: 30rpx;
  line-height: 44rpx;
  color: $ok-slate-800;
}

.form-phone-wx-btn--inline {
  width: auto;
  flex-shrink: 0;
  padding: 0 12rpx;
  color: $ok-forest-green;
  font-size: 28rpx;
}

.footer {
  flex-shrink: 0;
  padding: 20rpx 40rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  background: #fff;
  border-top: 0.5px solid #f1f5f9;
}

.btn-save-addr {
  width: 100%;
  background: $ok-sunshine-yellow;
  color: $ok-forest-green;
  padding: 32rpx 40rpx;
  border-radius: 60rpx;
  font-weight: 950;
  font-size: 34rpx;
  border: none;
  line-height: 1.35;
  box-shadow: 0 12rpx 32rpx rgba(250, 204, 21, 0.25);
}

.btn-save-addr::after {
  border: none;
}

.btn-save-addr[disabled] {
  opacity: 0.45;
}
</style>
