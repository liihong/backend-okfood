<script setup>
/**
 * 零售订单：手动为单次体验用户建单
 * 写入当前供餐日、默认已支付占 1 份库存，配送到家单可推送顺丰
 */
import { computed, ref, watch } from 'vue'
import { apiJson, adminAccessToken, dishImageDisplayUrl } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { formatIsoDateZh, formatMemberAddressOption } from '../utils/orderFormatters.js'
import MemberDeliveryMapPicker from '../../../components/MemberDeliveryMapPicker.vue'

defineOptions({ name: 'SingleMealManualOrderDialog' })

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  /** 当前列表供餐日 YYYY-MM-DD */
  deliveryDate: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const phone = ref('')
const name = ref('')
const memberPreview = ref(null)
const memberPreviewLoading = ref(false)
let memberDebounce = 0

const mealPeriod = ref('lunch')
const dishByPeriod = ref({ lunch: null, dinner: null })
const dishesLoading = ref(false)
const memberAddresses = ref([])
const addressesLoading = ref(false)
const submitting = ref(false)
const form = ref({
  store_pickup: false,
  member_address_id: null,
  pay_channel: '线下',
  pay_status: '已支付',
  amount_yuan: '',
  quantity: 1,
})

function blankAddrDraft() {
  return {
    contact_name: '',
    contact_phone: '',
    map_location_text: '',
    door_detail: '',
    remarks: '',
    lngStr: '',
    latStr: '',
  }
}

/** 配送到家时当场登记送餐地址 */
const addrRegistering = ref(true)
const addrDraft = ref(blankAddrDraft())

function prefillAddrDraftFromMember() {
  const d = addrDraft.value
  if (!d.contact_name) {
    d.contact_name = (name.value || memberPreview.value?.name || '').trim()
  }
  if (!d.contact_phone) {
    d.contact_phone = (phone.value || memberPreview.value?.phone || '').trim()
  }
}

const addrCoordDisplay = computed(() => {
  const a = String(addrDraft.value.lngStr ?? '').trim()
  const b = String(addrDraft.value.latStr ?? '').trim()
  if (a && b) return `${a}, ${b}`
  return '未选点'
})

const selectedDish = computed(() => dishByPeriod.value[mealPeriod.value] || null)

const dishImageUrl = computed(() => dishImageDisplayUrl(selectedDish.value?.image_url))

const availablePeriods = computed(() => {
  const out = []
  if (dishByPeriod.value.lunch) out.push({ value: 'lunch', label: '午餐' })
  if (dishByPeriod.value.dinner) out.push({ value: 'dinner', label: '晚餐' })
  return out
})

const canSubmit = computed(() => {
  const dish = selectedDish.value
  if (!dish || dish.dish_id == null) return false
  const rem = dish.single_stock_remaining
  if (rem != null && Number(rem) < Number(form.value.quantity || 1)) return false
  return true
})

const deliveryDateLabel = computed(() => formatIsoDateZh(props.deliveryDate))

const amountPlaceholder = computed(() => {
  const price = selectedDish.value?.single_order_price_yuan
  if (price == null || price === '') return '留空按单点价'
  return `留空按 ¥${price}`
})

const stockShort = computed(() => {
  const dish = selectedDish.value
  if (!dish || dish.single_stock_remaining == null) return false
  return Number(dish.single_stock_remaining) < Number(form.value.quantity || 1)
})

function startRegisterAddress() {
  addrRegistering.value = true
  form.value.member_address_id = null
  prefillAddrDraftFromMember()
}

function useExistingAddress() {
  addrRegistering.value = false
  const list = memberAddresses.value
  if (list.length) {
    const def = list.find((x) => x.is_default)
    form.value.member_address_id = Number((def || list[0]).id)
  }
}

function onAddrMapWarn(msg) {
  const s = typeof msg === 'string' && msg.trim() ? msg.trim() : '地图提示'
  showToast(s, 'error')
}

function resetForm() {
  phone.value = ''
  name.value = ''
  memberPreview.value = null
  mealPeriod.value = 'lunch'
  dishByPeriod.value = { lunch: null, dinner: null }
  form.value = {
    store_pickup: false,
    member_address_id: null,
    pay_channel: '线下',
    pay_status: '已支付',
    amount_yuan: '',
    quantity: 1,
  }
  memberAddresses.value = []
  addrRegistering.value = true
  addrDraft.value = blankAddrDraft()
}

function onDialogClosed() {
  resetForm()
}

function scheduleMemberPreview() {
  window.clearTimeout(memberDebounce)
  memberDebounce = window.setTimeout(() => {
    void loadMemberPreview()
  }, 380)
}

async function loadMemberPreview() {
  const ph = phone.value.trim()
  if (ph.length < 5) {
    memberPreview.value = null
    return
  }
  if (!adminAccessToken.value) return
  memberPreviewLoading.value = true
  try {
    const params = new URLSearchParams({ page: '1', page_size: '10', q: ph })
    const data = await apiJson(`/api/admin/users?${params}`, {}, { auth: true })
    const items = Array.isArray(data.items) ? data.items : []
    memberPreview.value = items.find((x) => String(x.phone || '') === ph) || null
    if (memberPreview.value) {
      void loadMemberAddresses(Number(memberPreview.value.id))
    }
  } catch {
    memberPreview.value = null
  } finally {
    memberPreviewLoading.value = false
  }
}

/** 按供餐日取出当日午餐/晚餐排期餐品 */
function slotForDate(data, isoDate) {
  const weekStart = String(data?.week_start || '').slice(0, 10)
  const slots = Array.isArray(data?.slots) ? data.slots : []
  if (!weekStart || !isoDate) return null
  const hit = slots.find((s) => {
    const slot = Number(s.slot)
    if (!Number.isFinite(slot) || slot < 1) return false
    return addDaysIso(weekStart, slot - 1) === isoDate
  })
  if (!hit || hit.dish_id == null) return null
  return hit
}

function addDaysIso(iso, days) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || '').trim())
  if (!m) return ''
  const dt = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]) + Number(days)))
  return dt.toISOString().slice(0, 10)
}

async function loadDishesForDate() {
  const d = String(props.deliveryDate || '').trim().slice(0, 10)
  if (!d || !adminAccessToken.value) {
    dishByPeriod.value = { lunch: null, dinner: null }
    return
  }
  dishesLoading.value = true
  try {
    const [lunch, dinner] = await Promise.all([
      apiJson(`/api/admin/menu/weekly-slots?week_start=${encodeURIComponent(d)}&meal_period=lunch`, {}, { auth: true }),
      apiJson(`/api/admin/menu/weekly-slots?week_start=${encodeURIComponent(d)}&meal_period=dinner`, {}, { auth: true }),
    ])
    const next = {
      lunch: slotForDate(lunch, d),
      dinner: slotForDate(dinner, d),
    }
    dishByPeriod.value = next
    if (!next[mealPeriod.value]) {
      mealPeriod.value = next.lunch ? 'lunch' : next.dinner ? 'dinner' : mealPeriod.value
    }
  } catch (e) {
    dishByPeriod.value = { lunch: null, dinner: null }
    showToast(e instanceof Error ? e.message : '加载当日餐品失败', 'error')
  } finally {
    dishesLoading.value = false
  }
}

async function loadMemberAddresses(memberId) {
  if (!memberId || !adminAccessToken.value) {
    memberAddresses.value = []
    return
  }
  addressesLoading.value = true
  try {
    const list = await apiJson(`/api/admin/users/${memberId}/addresses?usage=meal`, {}, { auth: true })
    memberAddresses.value = Array.isArray(list) ? list : []
    if (memberAddresses.value.length > 0) {
      addrRegistering.value = false
      const cur = form.value.member_address_id
      const hit =
        cur != null && memberAddresses.value.some((a) => Number(a.id) === Number(cur))
      if (!hit) {
        const def = memberAddresses.value.find((a) => a.is_default)
        form.value.member_address_id = Number((def || memberAddresses.value[0]).id)
      }
    } else {
      form.value.member_address_id = null
      addrRegistering.value = true
      prefillAddrDraftFromMember()
    }
  } catch {
    memberAddresses.value = []
    form.value.member_address_id = null
    addrRegistering.value = true
    prefillAddrDraftFromMember()
  } finally {
    addressesLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void loadDishesForDate()
    }
  },
)

watch(
  () => [phone.value, name.value, memberPreview.value],
  () => {
    if (addrRegistering.value) prefillAddrDraftFromMember()
  },
)

async function submitManualOrder() {
  const ph = phone.value.trim()
  if (!ph) {
    showToast('请填写手机号', 'error')
    return
  }
  if (!memberPreview.value && !(name.value || '').trim()) {
    showToast('会员不存在，请填写姓名以创建新会员', 'error')
    return
  }
  const dish = selectedDish.value
  if (!dish || dish.dish_id == null) {
    showToast('该供餐日未排餐品，无法建单', 'error')
    return
  }
  const qty = Math.max(1, Number(form.value.quantity) || 1)
  if (!form.value.store_pickup) {
    if (addrRegistering.value) {
      const ed = addrDraft.value
      const cn = String(ed.contact_name ?? '').trim()
      const cp = String(ed.contact_phone ?? '').trim()
      const mt = String(ed.map_location_text ?? '').trim()
      const lng = Number(String(ed.lngStr ?? '').trim())
      const lat = Number(String(ed.latStr ?? '').trim())
      if (!cn) {
        showToast('请填写收件人', 'error')
        return
      }
      if (cp.length < 5) {
        showToast('请填写有效收货电话', 'error')
        return
      }
      if (!mt) {
        showToast('请使用地图搜索或点击地图选点', 'error')
        return
      }
      if (!Number.isFinite(lng) || !Number.isFinite(lat) || (lng === 0 && lat === 0)) {
        showToast('请使用地图选点后再保存', 'error')
        return
      }
    } else if (!form.value.member_address_id) {
      showToast('配送到家须选择或登记收货地址', 'error')
      return
    }
  }

  submitting.value = true
  try {
    const body = {
      phone: ph,
      name: (name.value || '').trim() || null,
      delivery_date: String(props.deliveryDate || '').slice(0, 10),
      meal_period: mealPeriod.value,
      dish_id: Number(dish.dish_id),
      quantity: qty,
      store_pickup: Boolean(form.value.store_pickup),
      pay_channel: form.value.pay_channel,
      pay_status: form.value.pay_status,
      amount_yuan: (form.value.amount_yuan || '').trim() || null,
    }
    if (!form.value.store_pickup) {
      if (addrRegistering.value) {
        const ed = addrDraft.value
        body.delivery_address = {
          contact_name: String(ed.contact_name ?? '').trim(),
          contact_phone: String(ed.contact_phone ?? '').trim(),
          lng: Number(String(ed.lngStr ?? '').trim()),
          lat: Number(String(ed.latStr ?? '').trim()),
          map_location_text: String(ed.map_location_text ?? '').trim(),
          door_detail: String(ed.door_detail ?? '').trim() || null,
          remarks: String(ed.remarks ?? '').trim() || null,
        }
      } else {
        body.member_address_id = Number(form.value.member_address_id)
      }
    }
    const data = await apiJson(
      '/api/admin/orders/single-meals',
      { method: 'POST', body: JSON.stringify(body) },
      { auth: true },
    )
    showToast(`零售订单 #${data.id} 已创建`, 'success')
    emit('success', data)
    visible.value = false
  } catch (e) {
    showToast(e instanceof Error ? e.message : '建单失败', 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    width="820px"
    align-center
    append-to-body
    destroy-on-close
    class="single-manual-order-dialog"
    :close-on-click-modal="!submitting"
    :close-on-press-escape="!submitting"
    @closed="onDialogClosed"
  >
    <template #header>
      <div class="single-manual-drawer-head">
        <strong>手动建单</strong>
        <span>{{ deliveryDateLabel }}</span>
      </div>
    </template>

    <el-form label-position="top" size="small" class="single-manual-order-form">
      <div class="single-manual-drawer-body" :class="{ 'is-pickup': form.store_pickup }">
        <section class="single-manual-card single-manual-card--order">
          <div class="single-manual-grid">
            <el-form-item label="手机号" required>
              <el-input
                v-model="phone"
                maxlength="20"
                clearable
                placeholder="11 位手机号"
                @input="scheduleMemberPreview"
              />
            </el-form-item>
            <el-form-item label="姓名">
              <el-input
                v-model="name"
                maxlength="100"
                clearable
                :placeholder="memberPreview ? '可留空' : '新用户必填'"
              />
            </el-form-item>
          </div>
          <p v-if="memberPreviewLoading" class="single-manual-order-member-tip">正在查询会员…</p>
          <p v-else-if="memberPreview" class="single-manual-order-member-tip single-manual-order-member-tip--ok">
            已匹配 {{ memberPreview.name || '—' }} · {{ memberPreview.phone }}
          </p>
          <p v-else-if="phone.trim().length >= 5" class="single-manual-order-member-tip">
            未找到会员，填写姓名后创建体验用户
          </p>

          <div
            v-loading="dishesLoading"
            class="single-manual-dish-block"
            element-loading-text="加载餐品"
          >
            <el-image
              v-if="dishImageUrl && !dishesLoading"
              class="single-manual-dish-img"
              :src="dishImageUrl"
              :preview-src-list="[dishImageUrl]"
              fit="cover"
              preview-teleported
              hide-on-click-modal
            />
            <div v-else-if="!dishesLoading" class="single-manual-dish-img single-manual-dish-img--empty" />
            <div class="single-manual-dish-copy">
              <div class="single-manual-dish-head">
                <span class="single-manual-k">当日餐品</span>
                <el-radio-group v-if="availablePeriods.length > 1 && !dishesLoading" v-model="mealPeriod" size="small">
                  <el-radio-button v-for="p in availablePeriods" :key="p.value" :value="p.value">
                    {{ p.label }}
                  </el-radio-button>
                </el-radio-group>
              </div>
              <template v-if="!dishesLoading && selectedDish">
                <p class="single-manual-dish">{{ selectedDish.name || '餐品' }}</p>
                <p
                  v-if="selectedDish.single_order_price_yuan != null || selectedDish.single_stock_remaining != null"
                  class="single-manual-dish-meta"
                >
                  <span v-if="selectedDish.single_order_price_yuan != null">
                    ¥{{ selectedDish.single_order_price_yuan }}
                  </span>
                  <span v-if="selectedDish.single_stock_remaining != null">
                    剩 {{ selectedDish.single_stock_remaining }} 份
                  </span>
                </p>
              </template>
              <p v-else-if="!dishesLoading" class="single-manual-order-tip is-warn">该日未排餐</p>
              <p v-if="stockShort" class="single-manual-order-tip is-warn">库存不足，无法建单</p>
            </div>
          </div>

          <div class="single-manual-grid single-manual-grid--qty">
            <el-form-item label="份数">
              <el-input-number v-model="form.quantity" :min="1" :max="50" />
            </el-form-item>
            <el-form-item label="履约">
              <el-radio-group v-model="form.store_pickup">
                <el-radio :value="false">配送到家</el-radio>
                <el-radio :value="true">门店自提</el-radio>
              </el-radio-group>
            </el-form-item>
          </div>

          <div class="single-manual-grid">
            <el-form-item label="支付渠道">
              <el-select v-model="form.pay_channel">
                <el-option label="线下" value="线下" />
                <el-option label="微信" value="微信" />
                <el-option label="抖音" value="抖音" />
              </el-select>
            </el-form-item>
            <el-form-item label="支付状态">
              <el-select v-model="form.pay_status">
                <el-option label="已支付" value="已支付" />
                <el-option label="未支付" value="未支付" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="实收金额（元）">
            <el-input v-model="form.amount_yuan" clearable :placeholder="amountPlaceholder" />
          </el-form-item>
        </section>

        <section v-if="!form.store_pickup" class="single-manual-card single-manual-card--addr">
          <div class="single-manual-addr-toolbar">
            <span class="single-manual-k">收货地址</span>
            <el-button v-if="!addrRegistering" type="primary" link @click="startRegisterAddress">
              登记新地址
            </el-button>
            <el-button v-else-if="memberAddresses.length" link @click="useExistingAddress">
              选用已有地址
            </el-button>
          </div>
          <el-select
            v-if="!addrRegistering && memberAddresses.length"
            v-model="form.member_address_id"
            filterable
            placeholder="选择已有送餐地址"
            :loading="addressesLoading"
            class="single-manual-order-select"
          >
            <el-option
              v-for="a in memberAddresses"
              :key="a.id"
              :label="formatMemberAddressOption(a)"
              :value="Number(a.id)"
            />
          </el-select>
          <template v-if="addrRegistering">
            <div class="single-manual-grid">
              <el-form-item label="收件人" required>
                <el-input v-model="addrDraft.contact_name" maxlength="100" clearable placeholder="姓名" />
              </el-form-item>
              <el-form-item label="联系电话" required>
                <el-input v-model="addrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
              </el-form-item>
            </div>
            <p class="single-manual-order-coord">GCJ-02 {{ addrCoordDisplay }}</p>
            <div class="single-manual-map-wrap">
              <MemberDeliveryMapPicker
                :key="'single-manual-amap'"
                v-model:lng-str="addrDraft.lngStr"
                v-model:lat-str="addrDraft.latStr"
                v-model:map-location-text="addrDraft.map_location_text"
                search-input-id="single-manual-amap-search"
                @warn="onAddrMapWarn"
              />
            </div>
            <el-form-item label="收货位置">
              <el-input
                v-model="addrDraft.map_location_text"
                readonly
                maxlength="500"
                placeholder="地图选点后自动填入"
              />
            </el-form-item>
            <div class="single-manual-grid">
              <el-form-item label="门牌">
                <el-input v-model="addrDraft.door_detail" maxlength="500" clearable placeholder="楼栋 / 室号" />
              </el-form-item>
              <el-form-item label="地址备注">
                <el-input v-model="addrDraft.remarks" maxlength="500" clearable placeholder="可留空" />
              </el-form-item>
            </div>
          </template>
        </section>
      </div>
    </el-form>

    <template #footer>
      <el-button round :disabled="submitting" @click="visible = false">取消</el-button>
      <el-button type="primary" round :loading="submitting" :disabled="!canSubmit" @click="submitManualOrder">
        创建订单
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.single-manual-drawer-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.single-manual-drawer-head strong {
  font-size: 16px;
  font-weight: 800;
  color: #1d1f21;
}

.single-manual-drawer-head span {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-color-primary-dark-2, #c75f48);
  white-space: nowrap;
}

.single-manual-order-form {
  min-height: 0;
}

.single-manual-drawer-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 10px;
  align-items: stretch;
}

.single-manual-drawer-body.is-pickup {
  grid-template-columns: minmax(0, 420px);
}

.single-manual-card {
  min-width: 0;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.single-manual-card--order {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 14px;
}

.single-manual-card--order :deep(.el-form-item) {
  margin-bottom: 0;
}

.single-manual-card--addr {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.single-manual-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 10px;
}

.single-manual-grid--qty {
  align-items: end;
}

.single-manual-order-form :deep(.el-form-item) {
  margin-bottom: 8px;
}

.single-manual-order-form :deep(.el-form-item__label) {
  margin-bottom: 2px;
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  color: #64748b;
}

.single-manual-order-form :deep(.el-select),
.single-manual-order-form :deep(.el-input-number) {
  width: 100%;
}

.single-manual-k {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.single-manual-dish-block {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  min-height: 88px;
  padding: 8px 10px;
  border-radius: 10px;
  background: #f8fafc;
}

.single-manual-dish-img {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 10px;
  overflow: hidden;
}

.single-manual-dish-img--empty {
  background: #e2e8f0;
}

.single-manual-dish-copy {
  flex: 1;
  min-width: 0;
}

.single-manual-dish-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.single-manual-dish {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.35;
  color: #1d1f21;
}

.single-manual-dish-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin: 2px 0 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  color: #be123c;
}

.single-manual-order-select {
  width: 100%;
  margin-bottom: 8px;
}

.single-manual-addr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.single-manual-map-wrap {
  height: 168px;
  margin: 0 0 8px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.single-manual-map-wrap :deep(.mdmp) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.single-manual-map-wrap :deep(.mdmp-search) {
  margin-bottom: 6px;
}

.single-manual-map-wrap :deep(.mdmp-map) {
  flex: 1 1 auto;
  height: auto;
  min-height: 0;
}

.single-manual-map-wrap :deep(.mdmp-search-btn) {
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--el-color-primary);
}

.single-manual-order-coord {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.single-manual-order-member-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  color: #64748b;
}

.single-manual-order-member-tip--ok {
  color: #047857;
}

.single-manual-order-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.single-manual-order-tip.is-warn {
  margin-top: 4px;
  color: #c2410c;
}

@media (max-width: 860px) {
  .single-manual-drawer-body,
  .single-manual-drawer-body.is-pickup {
    grid-template-columns: 1fr;
    height: auto;
  }
}
</style>

<style>
/* 弹窗挂到 body，随内容增高，居中，不铺满视口 */
.single-manual-order-dialog.el-dialog,
.el-overlay .single-manual-order-dialog.el-dialog {
  border-radius: 16px;
  padding: 0;
  background: #f7fafb;
  max-width: calc(100vw - 32px);
}

.single-manual-order-dialog .el-dialog__header,
.el-overlay .single-manual-order-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 16px 16px 0 0;
}

.single-manual-order-dialog .el-dialog__body,
.el-overlay .single-manual-order-dialog .el-dialog__body {
  padding: 12px 14px;
  background: #f7fafb;
}

.single-manual-order-dialog .el-dialog__footer,
.el-overlay .single-manual-order-dialog .el-dialog__footer {
  padding: 10px 16px 14px;
  background: #fff;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 0 0 16px 16px;
}
</style>
