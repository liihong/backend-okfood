<template>
  <view class="page">
    <OkNavbar show-back title="地址管理 👌" />
    <scroll-view scroll-y class="scroll" :show-scrollbar="false">
      <view class="page-address">
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
              <text class="field-title">收货位置</text>
              <text class="field-optional-hint">（地图选点）</text>
            </view>
            <view class="form-input-p map-pick-slot">
              <view v-if="recvLocTitle" class="map-pick-summary">
                <text class="map-pick-line">{{ recvLocTitle }}</text>
                <text v-if="recvLocSub" class="map-pick-sub">{{ recvLocSub }}</text>
              </view>
              <text v-else class="map-pick-placeholder">请在地图上选择小区/道路等收货位置</text>
              <view class="map-pick-actions">
                <button class="btn-map-pick" hover-class="none" @tap="chooseMapLocation">地图选点</button>
              </view>
            </view>
          </view>
          <view v-if="useMapAddress" class="form-field">
            <view class="field-label-row">
              <text class="field-title">门牌号/单元楼层</text>
              <text class="field-required">*</text>
            </view>
            <input
              v-model="form.houseNumber"
              class="form-input-p"
              placeholder="例：3栋 2 单元 501"
            />
          </view>
          <view v-else class="form-field">
            <view class="field-label-row">
              <text class="field-title">详细地址</text>
              <text class="field-required">*</text>
            </view>
            <textarea
              v-model="form.legacyDetail"
              class="form-input-p form-textarea"
              placeholder="请输入小区、楼栋与门牌等完整地址"
            />
            <text class="field-hint">未使用地图选点时，将仅按文字地址自动定位（精度可能较低）</text>
          </view>
          <view class="form-field">
            <view class="field-label-row">
              <text class="field-title">忌口/备注</text>
            </view>
            <input
              v-model="form.remarks"
              class="form-input-p form-remarks"
              placeholder="如果您有忌口：请输入/不吃葱/不吃香菜"
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
import { onLoad } from '@dcloudio/uni-app'
import OkNavbar from '@/components/OkNavbar/OkNavbar.vue'
import { request, getMemberToken } from '@/utils/api.js'
import { normalizeAddressList, getAddressRecordId } from '@/utils/addressApi.js'
import { hasWxPhoneAuthDetail, wxMiniMemberLoginAndStore } from '@/utils/wxMemberLogin.js'

const form = reactive({
  name: '',
  phone: '',
  houseNumber: '',
  legacyDetail: '',
  remarks: '',
})

/** 坐标仅提交接口；界面只展示地名（uni.chooseLocation 地图选点） */
const coords = ref(null)
/** 选点返回的结构化字段，用于拼接 detail_address；省市区由服务端按经纬度高德逆地理编码与小程序文案合并写入 map_location_text */
const poiMeta = ref(null)
/** 主标题：多为小区或 POI 名称 */
const recvLocTitle = ref('')
/** 副标题：城市、道路等补充（不展示经纬度） */
const recvLocSub = ref('')

const useMapAddress = computed(() => coords.value != null)

function buildPoiBaseAddress(p) {
  if (!p || typeof p !== 'object') return ''
  const city = String(p.city ?? '').trim()
  const name = String(p.name ?? '').trim()
  let address = String(p.address ?? '').trim()
  if (city && address.startsWith(city)) {
    address = address.slice(city.length).trim()
  }
  // 与后台/列表展示一致：先省市区与道路，再小区/POI 名（微信常把 name 作小区、address 作行政区+路）
  const region = [city, address].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim()
  const parts = []
  if (region) parts.push(region)
  if (name && (!region || !region.includes(name))) parts.push(name)
  return parts.join(' ').replace(/\s+/g, ' ').trim()
}

function setPoiDisplayLines(city, name, address) {
  const c = String(city || '').trim()
  const n = String(name || '').trim()
  let a = String(address || '').trim()
  if (c && a.startsWith(c)) {
    a = a.slice(c.length).trim()
  }
  const region = [c, a].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim()
  if (region) {
    recvLocTitle.value = region
    recvLocSub.value = n && !region.includes(n) ? n : ''
    return
  }
  recvLocTitle.value = n || c || '已选地点'
  recvLocSub.value = ''
}

/** 当前编辑的地址 id；无则 POST 新增，有则 PATCH */
const addressId = ref('')

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

/** 接口返回的地址项 → 表单（优先 contact_name / contact_phone / detail_address） */
function applyAddressItem(item) {
  if (!item || typeof item !== 'object') return
  const id = item.id ?? item.address_id ?? item.addressId
  addressId.value = id != null ? String(id) : ''
  if (item.contact_name != null) form.name = String(item.contact_name)
  else if (item.name != null) form.name = String(item.name)
  else if (item.recipient_name != null) form.name = String(item.recipient_name)
  if (item.contact_phone != null) form.phone = String(item.contact_phone)
  else if (item.phone != null) form.phone = String(item.phone)
  if (item.remarks != null) form.remarks = String(item.remarks)

  const loc = item.location
  const latRaw = loc && typeof loc === 'object' && loc.lat != null ? Number(loc.lat) : NaN
  const lngRaw = loc && typeof loc === 'object' && loc.lng != null ? Number(loc.lng) : NaN
  const hasLoc = Number.isFinite(latRaw) && Number.isFinite(lngRaw)
  if (hasLoc) {
    coords.value = { lat: latRaw, lng: lngRaw }
    poiMeta.value = null
    const mapSaved =
      item.map_location_text != null && String(item.map_location_text).trim()
        ? String(item.map_location_text).trim()
        : ''
    const doorSaved =
      item.door_detail != null && String(item.door_detail).trim()
        ? String(item.door_detail).trim()
        : ''
    if (mapSaved || doorSaved) {
      recvLocTitle.value = mapSaved || (item.detail_address != null ? String(item.detail_address) : '')
      recvLocSub.value = ''
      form.houseNumber = doorSaved
      form.legacyDetail = ''
    } else {
      const line =
        item.detail_address != null
          ? String(item.detail_address)
          : item.address != null
            ? String(item.address)
            : ''
      recvLocTitle.value = line
      recvLocSub.value = ''
      form.houseNumber = ''
      form.legacyDetail = ''
    }
  } else {
    coords.value = null
    poiMeta.value = null
    recvLocTitle.value = ''
    recvLocSub.value = ''
    form.houseNumber = ''
    if (item.detail_address != null) form.legacyDetail = String(item.detail_address)
    else if (item.address != null) form.legacyDetail = String(item.address)
    else form.legacyDetail = ''
  }
}

function clearForm() {
  form.name = ''
  form.phone = ''
  form.houseNumber = ''
  form.legacyDetail = ''
  form.remarks = ''
  coords.value = null
  poiMeta.value = null
  recvLocTitle.value = ''
  recvLocSub.value = ''
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
  poiMeta.value = meta
  const city = String(meta.city ?? '').trim()
  const name = String(meta.name ?? '').trim()
  const address = String(meta.address ?? '').trim()
  setPoiDisplayLines(city, name, address)
  form.legacyDetail = ''
  return true
}

function openChooseLocationCentered(lat, lng) {
  const opts = {}
  if (Number.isFinite(lat) && Number.isFinite(lng)) {
    opts.latitude = lat
    opts.longitude = lng
  }
  uni.chooseLocation({
    ...opts,
    success(res) {
      const name = String(res.name ?? '').trim()
      const address = String(res.address ?? '').trim()
      const la = res.latitude != null ? Number(res.latitude) : NaN
      const lo = res.longitude != null ? Number(res.longitude) : NaN
      applyCoordsAndPoiMeta(la, lo, {
        type: 2,
        city: '',
        name,
        address,
      })
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
        uni.showModal({
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
    const item = list.find((row) => getAddressRecordId(row) === id)
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

/** POST/PATCH 与后台约定字段 */
function buildAddressBody() {
  const hasCoords = coords.value != null
  let detail_address = ''
  if (hasCoords) {
    const base = poiMeta.value
      ? buildPoiBaseAddress(poiMeta.value)
      : (recvLocTitle.value || '').trim()
    const house = (form.houseNumber || '').trim()
    detail_address = house ? `${base} ${house}`.trim() : base
    return {
      contact_name: form.name.trim(),
      contact_phone: String(form.phone).replace(/\D/g, ''),
      detail_address,
      map_location_text: base || null,
      door_detail: house || null,
      remarks: (form.remarks || '').trim(),
      location: { lng: coords.value.lng, lat: coords.value.lat },
    }
  }
  detail_address = (form.legacyDetail || '').trim()
  const body = {
    contact_name: form.name.trim(),
    contact_phone: String(form.phone).replace(/\D/g, ''),
    detail_address,
    map_location_text: null,
    door_detail: null,
    remarks: (form.remarks || '').trim(),
  }
  return body
}

onLoad((options) => {
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
  const hasCoords = coords.value != null
  if (hasCoords) {
    const baseOk = poiMeta.value
      ? buildPoiBaseAddress(poiMeta.value)
      : (recvLocTitle.value || '').trim()
    if (!baseOk) {
      uni.showToast({ title: '请选择收货地点', icon: 'none' })
      return
    }
    const isNew = !addressId.value
    if (isNew && !(form.houseNumber || '').trim()) {
      uni.showToast({ title: '请填写门牌号/单元楼层', icon: 'none' })
      return
    }
  } else if (!(form.legacyDetail || '').trim()) {
    uni.showToast({ title: '请填写详细地址', icon: 'none' })
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
      if (saveResult && typeof saveResult === 'object') {
        const nid = saveResult.id ?? saveResult.address_id ?? saveResult.addressId
        if (nid != null) addressId.value = String(nid)
      }
    }
    const bodySaved = buildAddressBody()
    uni.setStorageSync('deliveryAddress', {
      name: form.name,
      phone: form.phone,
      address: bodySaved.detail_address,
      remarks: form.remarks,
      location: hasCoords ? { lat: coords.value.lat, lng: coords.value.lng } : null,
    })
    const title = isNewAddress ? '地址添加成功' : '更新成功'
    uni.showToast({ title, icon: 'success', duration: 2000 })
    setTimeout(() => {
      uni.navigateBack()
    }, 1800)
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

.map-pick-summary {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.map-pick-line {
  font-weight: 800;
  font-size: 30rpx;
  color: $ok-slate-800;
  line-height: 1.45;
}

.map-pick-sub {
  font-size: 26rpx;
  font-weight: 700;
  color: #64748b;
  line-height: 1.45;
}

.map-pick-placeholder {
  font-weight: 700;
  font-size: 28rpx;
  color: #94a3b8;
  line-height: 1.45;
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
</style>
