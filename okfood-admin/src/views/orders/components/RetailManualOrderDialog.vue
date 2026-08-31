<script setup>
/**
 * 商城订单：手动建单 / 协助抖音验券
 * 独立弹窗组件，通过 v-model 控制显隐，success 事件通知父级刷新列表
 */
import { computed, ref, watch } from 'vue'
import { apiJson, adminAccessToken } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { formatMemberAddressOption } from '../utils/orderFormatters.js'
import MemberDeliveryMapPicker from '../../../components/MemberDeliveryMapPicker.vue'

defineOptions({ name: 'RetailManualOrderDialog' })

const props = defineProps({
  /** 弹窗显隐 */
  modelValue: { type: Boolean, default: false },
  /** 门店 id */
  storeId: { type: Number, default: 1 },
})

const emit = defineEmits(['update:modelValue', 'success'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

/** 建单方式：抖音验券 / 手动建单 */
const mode = ref('douyin')

// —— 会员信息（两种模式共用）——
const phone = ref('')
const name = ref('')
const memberPreview = ref(null)
const memberPreviewLoading = ref(false)
let memberDebounce = 0

// —— 抖音验券 ——
const douyinCode = ref('')
const douyinSubmitting = ref(false)
/** @type {import('vue').Ref<null | Record<string, unknown>>} */
const douyinResult = ref(null)

// —— 手动建单 ——
const products = ref([])
const productsLoading = ref(false)
const manualSubmitting = ref(false)
const memberAddresses = ref([])
const addressesLoading = ref(false)
const manualForm = ref({
  store_pickup: false,
  member_address_id: null,
  pay_channel: '线下',
  pay_status: '已支付',
  amount_yuan: '',
  remark: '',
})
/** @type {import('vue').Ref<Array<{ retail_product_id: number | null, quantity: number }>>} */
const manualItems = ref([{ retail_product_id: null, quantity: 1 }])

/** 空白商城收货地址草稿（地图选点） */
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

/** 配送到家时当场登记新商城收货地址（不走会员送餐地址） */
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

function startRegisterAddress() {
  addrRegistering.value = true
  manualForm.value.member_address_id = null
  prefillAddrDraftFromMember()
}

function useExistingAddress() {
  addrRegistering.value = false
  const list = memberAddresses.value
  if (list.length) {
    const def = list.find((x) => x.is_default)
    manualForm.value.member_address_id = Number((def || list[0]).id)
  }
}

function onAddrMapWarn(msg) {
  const s = typeof msg === 'string' && msg.trim() ? msg.trim() : '地图提示'
  showToast(s, 'error')
}

function addManualItemRow() {
  if (manualItems.value.length >= 20) {
    showToast('最多 20 种商品', 'error')
    return
  }
  manualItems.value.push({ retail_product_id: null, quantity: 1 })
}

function removeManualItemRow(index) {
  if (manualItems.value.length <= 1) return
  manualItems.value.splice(index, 1)
}

const productOptionLabel = (p) => {
  const price = p.unit_price_yuan != null ? String(p.unit_price_yuan) : '—'
  const title = p.display_title || p.spu_title || p.title || '商品'
  return `${title}（¥${price}）`
}

const selectedProduct = computed(() => {
  const id = manualItems.value[0]?.retail_product_id
  if (id == null) return null
  return products.value.find((p) => Number(p.id) === Number(id)) || null
})

function resetForm() {
  mode.value = 'douyin'
  phone.value = ''
  name.value = ''
  memberPreview.value = null
  douyinCode.value = ''
  douyinResult.value = null
  manualForm.value = {
    store_pickup: false,
    member_address_id: null,
    pay_channel: '线下',
    pay_status: '已支付',
    amount_yuan: '',
    remark: '',
  }
  manualItems.value = [{ retail_product_id: null, quantity: 1 }]
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
    if (memberPreview.value && mode.value === 'manual') {
      void loadMemberAddresses(Number(memberPreview.value.id))
    }
  } catch {
    memberPreview.value = null
  } finally {
    memberPreviewLoading.value = false
  }
}

async function loadProducts() {
  if (!adminAccessToken.value) return
  productsLoading.value = true
  try {
    const data = await apiJson(
      `/api/admin/catalog/retail-products?store_id=${props.storeId}&shelf_only=true`,
      {},
      { auth: true },
    )
    products.value = Array.isArray(data) ? data : []
    if (products.value.length > 0 && manualItems.value[0] && manualItems.value[0].retail_product_id == null) {
      manualItems.value[0].retail_product_id = Number(products.value[0].id)
    }
  } catch (e) {
    products.value = []
    showToast(e instanceof Error ? e.message : '加载商品失败', 'error')
  } finally {
    productsLoading.value = false
  }
}

async function loadMemberAddresses(memberId) {
  if (!memberId || !adminAccessToken.value) {
    memberAddresses.value = []
    return
  }
  addressesLoading.value = true
  try {
    let list = await apiJson(
      `/api/admin/users/${memberId}/addresses?usage=retail`,
      {},
      { auth: true },
    )
    list = Array.isArray(list) ? list : []
    if (!list.length) {
      const mealList = await apiJson(
        `/api/admin/users/${memberId}/addresses?usage=meal`,
        {},
        { auth: true },
      )
      list = Array.isArray(mealList) ? mealList : []
    }
    memberAddresses.value = list
    if (memberAddresses.value.length > 0) {
      addrRegistering.value = false
      const cur = manualForm.value.member_address_id
      const hit =
        cur != null && memberAddresses.value.some((a) => Number(a.id) === Number(cur))
      if (!hit) {
        const def = memberAddresses.value.find((a) => a.is_default)
        manualForm.value.member_address_id = Number((def || memberAddresses.value[0]).id)
      }
    } else {
      manualForm.value.member_address_id = null
      addrRegistering.value = true
      prefillAddrDraftFromMember()
    }
  } catch {
    memberAddresses.value = []
    manualForm.value.member_address_id = null
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
      void loadProducts()
    }
  },
)

watch(mode, (m) => {
  douyinResult.value = null
  if (m === 'manual' && memberPreview.value?.id) {
    void loadMemberAddresses(Number(memberPreview.value.id))
  }
})

watch(
  () => [phone.value, name.value, memberPreview.value],
  () => {
    if (addrRegistering.value) prefillAddrDraftFromMember()
  },
)

async function submitDouyinRedeem() {
  const ph = phone.value.trim()
  const code = douyinCode.value.trim()
  if (!ph) {
    showToast('请填写会员手机号', 'error')
    return
  }
  if (code.length < 4) {
    showToast('请输入有效抖音券码', 'error')
    return
  }
  if (!memberPreview.value && !(name.value || '').trim()) {
    showToast('会员不存在，请填写姓名以创建新会员', 'error')
    return
  }

  douyinSubmitting.value = true
  douyinResult.value = null
  try {
    const body = { phone: ph, code, name: (name.value || '').trim() || null }
    const data = await apiJson(
      `/api/admin/marketing/douyin/certificates/redeem?store_id=${props.storeId}`,
      { method: 'POST', body: JSON.stringify(body) },
      { auth: true },
    )
    douyinResult.value = data
    showToast(data.message || '验券成功', 'success')
    emit('success', data)
  } catch (e) {
    showToast(e instanceof Error ? e.message : '验券失败', 'error')
  } finally {
    douyinSubmitting.value = false
  }
}

async function submitManualOrder() {
  const ph = phone.value.trim()
  if (!ph) {
    showToast('请填写会员手机号', 'error')
    return
  }
  if (!memberPreview.value && !(name.value || '').trim()) {
    showToast('会员不存在，请填写姓名以创建新会员', 'error')
    return
  }
  const items = manualItems.value
    .filter((row) => row.retail_product_id != null)
    .map((row) => ({
      retail_product_id: Number(row.retail_product_id),
      quantity: Math.max(1, Number(row.quantity) || 1),
    }))
  if (!items.length) {
    showToast('请至少选择一个商品', 'error')
    return
  }
  if (!manualForm.value.store_pickup) {
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
    } else if (!manualForm.value.member_address_id) {
      showToast('配送到家须选择或登记收货地址', 'error')
      return
    }
  }

  manualSubmitting.value = true
  try {
    const body = {
      phone: ph,
      name: (name.value || '').trim() || null,
      items,
      store_pickup: Boolean(manualForm.value.store_pickup),
      pay_channel: manualForm.value.pay_channel,
      pay_status: manualForm.value.pay_status,
      amount_yuan: (manualForm.value.amount_yuan || '').trim() || null,
      remark: (manualForm.value.remark || '').trim() || null,
    }
    if (!manualForm.value.store_pickup) {
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
        body.member_address_id = Number(manualForm.value.member_address_id)
      }
    }
    const data = await apiJson(
      `/api/admin/orders/retail-orders?store_id=${props.storeId}`,
      { method: 'POST', body: JSON.stringify(body) },
      { auth: true },
    )
    showToast(`商城订单 #${data.id} 已创建`, 'success')
    emit('success', data)
    visible.value = false
  } catch (e) {
    showToast(e instanceof Error ? e.message : '建单失败', 'error')
  } finally {
    manualSubmitting.value = false
  }
}

const isBusy = computed(() => douyinSubmitting.value || manualSubmitting.value)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="手动建单"
    :width="mode === 'manual' && !manualForm.store_pickup ? '920px' : '640px'"
    class="retail-manual-order-dialog"
    destroy-on-close
    align-center
    :close-on-click-modal="!isBusy"
    :close-on-press-escape="!isBusy"
    @closed="onDialogClosed"
  >
    <p class="retail-manual-order-hint">
      协助会员完成抖音验券或线下/微信手动建单；验券成功后若映射为商城商品将自动生成待接单订单。
    </p>

    <el-tabs v-model="mode" class="retail-manual-order-tabs">
      <el-tab-pane label="抖音验券" name="douyin" />
      <el-tab-pane label="手动建单" name="manual" />
    </el-tabs>

    <el-form label-position="top" size="default" class="retail-manual-order-form">
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="会员手机号" required>
            <el-input
              v-model="phone"
              maxlength="20"
              clearable
              placeholder="11 位手机号"
              @input="scheduleMemberPreview"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="会员姓名">
            <el-input
              v-model="name"
              maxlength="100"
              clearable
              :placeholder="memberPreview ? '已匹配会员，可留空' : '新会员必填'"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <p v-if="memberPreviewLoading" class="retail-manual-order-member-tip">正在查询会员…</p>
      <p v-else-if="memberPreview" class="retail-manual-order-member-tip retail-manual-order-member-tip--ok">
        已匹配：{{ memberPreview.name || '—' }} · {{ memberPreview.phone }}
      </p>
      <p v-else-if="phone.trim().length >= 5" class="retail-manual-order-member-tip">
        未找到会员，填写姓名后将自动创建
      </p>

      <!-- 抖音验券 -->
      <template v-if="mode === 'douyin'">
        <el-form-item label="抖音券码" required>
          <el-input
            v-model="douyinCode"
            type="textarea"
            :rows="2"
            maxlength="128"
            placeholder="请粘贴抖音 App 订单中的券码"
          />
        </el-form-item>
        <div v-if="douyinResult" class="retail-manual-order-result">
          <p class="retail-manual-order-result-title">{{ douyinResult.message }}</p>
          <p v-if="douyinResult.grant_result_kind === 'store_retail_order'" class="retail-manual-order-result-sub">
            已生成商城订单 #{{ douyinResult.grant_result_id }}，可在列表中修改配送方式。
          </p>
          <p v-else-if="douyinResult.grant_result_id" class="retail-manual-order-result-sub">
            权益类型：{{ douyinResult.grant_label || douyinResult.grant_type }} · 记录 #{{ douyinResult.grant_result_id }}
          </p>
        </div>
      </template>

      <!-- 手动建单 -->
      <template v-else>
        <el-form-item label="商品明细" required>
          <div v-for="(row, idx) in manualItems" :key="idx" class="retail-manual-item-row">
            <el-select
              v-model="row.retail_product_id"
              filterable
              placeholder="选择商品"
              :loading="productsLoading"
              class="retail-manual-order-select"
            >
              <el-option
                v-for="p in products"
                :key="p.id"
                :label="productOptionLabel(p)"
                :value="Number(p.id)"
              />
            </el-select>
            <el-input-number v-model="row.quantity" :min="1" :max="50" />
            <el-button v-if="manualItems.length > 1" link type="danger" @click="removeManualItemRow(idx)">删除</el-button>
          </div>
          <el-button link type="primary" @click="addManualItemRow">+ 添加商品</el-button>
        </el-form-item>

        <el-form-item label="履约方式">
          <el-radio-group v-model="manualForm.store_pickup">
            <el-radio :value="false">配送到家</el-radio>
            <el-radio :value="true">门店自提</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="!manualForm.store_pickup" label="商城收货地址" required>
          <div class="retail-manual-addr-toolbar">
            <el-select
              v-if="!addrRegistering && memberAddresses.length"
              v-model="manualForm.member_address_id"
              filterable
              placeholder="选择已有商城收货地址"
              :loading="addressesLoading"
              class="retail-manual-order-select"
            >
              <el-option
                v-for="a in memberAddresses"
                :key="a.id"
                :label="formatMemberAddressOption(a)"
                :value="Number(a.id)"
              />
            </el-select>
            <el-button
              v-if="!addrRegistering"
              type="primary"
              link
              @click="startRegisterAddress"
            >
              登记新地址
            </el-button>
            <el-button
              v-else-if="memberAddresses.length"
              link
              @click="useExistingAddress"
            >
              选用已有地址
            </el-button>
          </div>
          <p v-if="!addrRegistering && memberAddresses.length" class="retail-manual-order-tip">
            选用已有地址不会改写会员送餐地址。也可点「登记新地址」当场录入。
          </p>
          <template v-if="addrRegistering">
            <p class="retail-manual-order-tip">
              当场登记商城收货地址（果蔬汁/月饼），与会员送餐地址分开保存。
            </p>
            <el-row :gutter="12">
              <el-col :span="12">
                <el-form-item label="收件人" required>
                  <el-input v-model="addrDraft.contact_name" maxlength="100" clearable placeholder="收件人姓名" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="联系电话" required>
                  <el-input v-model="addrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
                </el-form-item>
              </el-col>
            </el-row>
            <p class="retail-manual-order-coord">经纬度 GCJ-02：{{ addrCoordDisplay }}</p>
            <div class="retail-manual-map-wrap">
              <MemberDeliveryMapPicker
                :key="'retail-manual-amap'"
                v-model:lng-str="addrDraft.lngStr"
                v-model:lat-str="addrDraft.latStr"
                v-model:map-location-text="addrDraft.map_location_text"
                search-input-id="retail-manual-amap-search"
                @warn="onAddrMapWarn"
              />
            </div>
            <el-form-item label="收货位置主文案">
              <el-input
                v-model="addrDraft.map_location_text"
                type="textarea"
                readonly
                :autosize="{ minRows: 2, maxRows: 4 }"
                maxlength="500"
                show-word-limit
                placeholder="地图选点后自动填入"
              />
            </el-form-item>
            <el-form-item label="门牌（楼栋 / 单元 / 室号）">
              <el-input
                v-model="addrDraft.door_detail"
                maxlength="500"
                clearable
                placeholder="例如：3 号楼 1202"
              />
            </el-form-item>
            <el-form-item label="地址备注">
              <el-input v-model="addrDraft.remarks" maxlength="500" clearable placeholder="可留空" />
            </el-form-item>
          </template>
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="支付渠道">
              <el-select v-model="manualForm.pay_channel">
                <el-option label="线下" value="线下" />
                <el-option label="微信" value="微信" />
                <el-option label="抖音" value="抖音" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="支付状态">
              <el-select v-model="manualForm.pay_status">
                <el-option label="已支付（待接单）" value="已支付" />
                <el-option label="未支付" value="未支付" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="实收金额（元）">
          <el-input
            v-model="manualForm.amount_yuan"
            clearable
            placeholder="留空则按商品售价自动计算"
          />
          <p v-if="selectedProduct && !manualForm.amount_yuan" class="retail-manual-order-tip">
            参考售价：¥{{ selectedProduct.unit_price_yuan }}
            {{ manualForm.store_pickup ? '（自提减配送费）' : '' }}
          </p>
        </el-form-item>

        <el-form-item label="后台备注">
          <el-input
            v-model="manualForm.remark"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="可选，仅管理端可见"
          />
        </el-form-item>
      </template>
    </el-form>

    <template #footer>
      <el-button :disabled="isBusy" @click="visible = false">关闭</el-button>
      <el-button
        v-if="mode === 'douyin'"
        type="primary"
        :loading="douyinSubmitting"
        @click="submitDouyinRedeem"
      >
        验券并兑换
      </el-button>
      <el-button
        v-else
        type="primary"
        :loading="manualSubmitting"
        @click="submitManualOrder"
      >
        创建订单
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.retail-manual-order-hint {
  margin: 0 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.retail-manual-order-tabs {
  margin-bottom: 8px;
}

.retail-manual-order-form {
  margin-top: 4px;
}

.retail-manual-item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.retail-manual-order-select {
  flex: 1;
  min-width: 0;
}

.retail-manual-addr-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  width: 100%;
}

.retail-manual-addr-toolbar .retail-manual-order-select {
  flex: 1;
}

:deep(.el-dialog__body) {
  max-height: min(78vh, 720px);
  overflow-y: auto;
}

.retail-manual-map-wrap {
  width: 100%;
  min-height: 244px;
  margin: 8px 0 12px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.retail-manual-order-coord {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.retail-manual-order-member-tip {
  margin: -4px 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.retail-manual-order-member-tip--ok {
  color: var(--el-color-success);
}

.retail-manual-order-tip {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.retail-manual-order-result {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: var(--el-color-success-light-9);
  border: 1px solid var(--el-color-success-light-5);
}

.retail-manual-order-result-title {
  margin: 0;
  font-size: 14px;
  color: var(--el-color-success-dark-2);
}

.retail-manual-order-result-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
</style>
