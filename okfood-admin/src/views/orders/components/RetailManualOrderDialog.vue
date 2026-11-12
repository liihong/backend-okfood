<script setup>
/**
 * 商城订单：手动建单 / 协助抖音验券
 * 独立弹窗组件，通过 v-model 控制显隐，success 事件通知父级刷新列表
 */
import { computed, ref, watch } from 'vue'
import { apiJson, adminAccessToken, dishImageDisplayUrl } from '../../../admin/core.js'
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
const mode = ref('manual')

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

/** 商品封面：相对路径拼 API 根地址 */
function productCoverUrl(p) {
  return dishImageDisplayUrl(p?.cover_image_url)
}

const selectedProduct = computed(() => {
  const id = manualItems.value[0]?.retail_product_id
  if (id == null) return null
  return products.value.find((p) => Number(p.id) === Number(id)) || null
})

function resetForm() {
  mode.value = 'manual'
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
    const [data, spuData] = await Promise.all([
      apiJson(
        `/api/admin/catalog/retail-products?store_id=${props.storeId}&shelf_only=true`,
        {},
        { auth: true },
      ),
      // SKU 列表没有封面，封面在商品（SPU）上
      apiJson(`/api/admin/catalog/retail-spus?store_id=${props.storeId}`, {}, { auth: true }).catch(() => []),
    ])
    const coverBySpu = new Map(
      (Array.isArray(spuData) ? spuData : []).map((spu) => [Number(spu.id), spu.cover_image_url || '']),
    )
    const rows = Array.isArray(data) ? data : []
    products.value = rows.map((row) => ({
      ...row,
      cover_image_url: row.cover_image_url || coverBySpu.get(Number(row.spu_id)) || '',
    }))
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

/** 配送且正在登记新地址时左右分栏，其余收成窄弹窗 */
const dialogWide = computed(
  () => mode.value === 'manual' && !manualForm.value.store_pickup && addrRegistering.value,
)
</script>

<template>
  <el-dialog
    v-model="visible"
    :width="dialogWide ? '820px' : '560px'"
    class="retail-manual-order-dialog"
    destroy-on-close
    align-center
    append-to-body
    :close-on-click-modal="!isBusy"
    :close-on-press-escape="!isBusy"
    @closed="onDialogClosed"
  >
    <template #header>
      <div class="retail-manual-head">
        <strong>手动建单</strong>
        <el-radio-group v-model="mode" size="small">
          <el-radio-button value="manual">线下建单</el-radio-button>
          <el-radio-button value="douyin">抖音验券</el-radio-button>
        </el-radio-group>
      </div>
    </template>

    <el-form label-position="top" size="small" class="retail-manual-order-form">
      <div class="retail-manual-body" :class="{ 'is-single': !dialogWide }">
        <section class="retail-manual-card retail-manual-card--order">
          <div class="retail-manual-grid">
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
                :placeholder="memberPreview ? '可留空' : '新会员必填'"
              />
            </el-form-item>
          </div>
          <p v-if="memberPreviewLoading" class="retail-manual-order-member-tip">正在查询会员…</p>
          <p v-else-if="memberPreview" class="retail-manual-order-member-tip retail-manual-order-member-tip--ok">
            已匹配 {{ memberPreview.name || '—' }} · {{ memberPreview.phone }}
          </p>
          <p v-else-if="phone.trim().length >= 5" class="retail-manual-order-member-tip">
            未找到会员，填写姓名后创建
          </p>

          <template v-if="mode === 'douyin'">
            <el-form-item label="抖音券码" required>
              <el-input
                v-model="douyinCode"
                maxlength="128"
                clearable
                placeholder="粘贴抖音券码"
              />
            </el-form-item>
            <div v-if="douyinResult" class="retail-manual-order-result">
              <p class="retail-manual-order-result-title">{{ douyinResult.message }}</p>
              <p v-if="douyinResult.grant_result_kind === 'store_retail_order'" class="retail-manual-order-result-sub">
                已生成商城订单 #{{ douyinResult.grant_result_id }}
              </p>
              <p v-else-if="douyinResult.grant_result_id" class="retail-manual-order-result-sub">
                {{ douyinResult.grant_label || douyinResult.grant_type }} · #{{ douyinResult.grant_result_id }}
              </p>
            </div>
          </template>

          <template v-else>
            <el-form-item label="商品" required>
              <div
                v-loading="productsLoading"
                class="retail-manual-items"
                element-loading-text="加载商品"
              >
                <div v-for="(row, idx) in manualItems" :key="idx" class="retail-manual-item-row">
                  <el-select
                    v-model="row.retail_product_id"
                    filterable
                    placeholder="选择商品"
                    class="retail-manual-order-select"
                    popper-class="retail-manual-product-popper"
                  >
                    <el-option
                      v-for="p in products"
                      :key="p.id"
                      :label="productOptionLabel(p)"
                      :value="Number(p.id)"
                    >
                      <span class="retail-manual-option">
                        <img v-if="productCoverUrl(p)" :src="productCoverUrl(p)" alt="" />
                        <span v-else class="retail-manual-option-ph" />
                        <span class="retail-manual-option-text">{{ productOptionLabel(p) }}</span>
                      </span>
                    </el-option>
                  </el-select>
                  <el-input-number v-model="row.quantity" :min="1" :max="50" />
                  <el-button v-if="manualItems.length > 1" link type="danger" @click="removeManualItemRow(idx)">
                    删除
                  </el-button>
                </div>
                <el-button class="retail-manual-add" link type="primary" @click="addManualItemRow">
                  + 添加商品
                </el-button>
                <p v-if="!productsLoading && !products.length" class="retail-manual-order-tip is-warn">暂无在架商品</p>
              </div>
            </el-form-item>

            <el-form-item label="履约">
              <el-radio-group v-model="manualForm.store_pickup">
                <el-radio :value="false">配送到家</el-radio>
                <el-radio :value="true">门店自提</el-radio>
              </el-radio-group>
            </el-form-item>

            <template v-if="!manualForm.store_pickup && !addrRegistering">
              <div class="retail-manual-addr-toolbar">
                <span class="retail-manual-k">收货地址</span>
                <el-button type="primary" link @click="startRegisterAddress">登记新地址</el-button>
              </div>
              <el-select
                v-if="memberAddresses.length"
                v-model="manualForm.member_address_id"
                filterable
                placeholder="选择已有商城地址"
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
              <p class="retail-manual-order-tip">选用已有地址，不改送餐地址。</p>
            </template>

            <div class="retail-manual-grid">
              <el-form-item label="支付渠道">
                <el-select v-model="manualForm.pay_channel">
                  <el-option label="线下" value="线下" />
                  <el-option label="微信" value="微信" />
                  <el-option label="抖音" value="抖音" />
                </el-select>
              </el-form-item>
              <el-form-item label="支付状态">
                <el-select v-model="manualForm.pay_status">
                  <el-option label="已支付" value="已支付" />
                  <el-option label="未支付" value="未支付" />
                </el-select>
              </el-form-item>
            </div>
            <el-form-item label="实收金额（元）">
              <el-input v-model="manualForm.amount_yuan" clearable placeholder="留空按售价" />
            </el-form-item>
            <p v-if="selectedProduct && !manualForm.amount_yuan" class="retail-manual-price">
              参考 ¥{{ selectedProduct.unit_price_yuan }}{{ manualForm.store_pickup ? '，自提减配送费' : '' }}
            </p>
            <el-form-item label="备注">
              <el-input v-model="manualForm.remark" maxlength="500" clearable placeholder="可留空，仅管理端可见" />
            </el-form-item>
          </template>
        </section>

        <section
          v-if="dialogWide"
          v-loading="addressesLoading"
          class="retail-manual-card retail-manual-card--addr"
          element-loading-text="加载地址"
        >
          <div class="retail-manual-addr-toolbar">
            <span class="retail-manual-k">收货地址</span>
            <el-button v-if="memberAddresses.length" link @click="useExistingAddress">选用已有地址</el-button>
          </div>
          <p class="retail-manual-order-tip retail-manual-addr-note">保存后只绑定本单，不改送餐地址。</p>
          <div class="retail-manual-grid">
            <el-form-item label="收件人" required>
              <el-input v-model="addrDraft.contact_name" maxlength="100" clearable placeholder="姓名" />
            </el-form-item>
            <el-form-item label="联系电话" required>
              <el-input v-model="addrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
            </el-form-item>
          </div>
          <p class="retail-manual-order-coord">GCJ-02 {{ addrCoordDisplay }}</p>
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
          <el-form-item label="收货位置">
            <el-input
              v-model="addrDraft.map_location_text"
              readonly
              maxlength="500"
              placeholder="地图选点后自动填入"
            />
          </el-form-item>
          <div class="retail-manual-grid">
            <el-form-item label="门牌">
              <el-input v-model="addrDraft.door_detail" maxlength="500" clearable placeholder="楼栋 / 室号" />
            </el-form-item>
            <el-form-item label="地址备注">
              <el-input v-model="addrDraft.remarks" maxlength="500" clearable placeholder="可留空" />
            </el-form-item>
          </div>
        </section>
      </div>
    </el-form>

    <template #footer>
      <el-button round :disabled="isBusy" @click="visible = false">取消</el-button>
      <el-button
        v-if="mode === 'douyin'"
        type="primary"
        round
        :loading="douyinSubmitting"
        @click="submitDouyinRedeem"
      >
        验券兑换
      </el-button>
      <el-button
        v-else
        type="primary"
        round
        :loading="manualSubmitting"
        @click="submitManualOrder"
      >
        创建订单
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.retail-manual-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
  padding-right: 28px;
}

.retail-manual-head strong {
  font-size: 16px;
  font-weight: 800;
  color: #1d1f21;
}

.retail-manual-order-form {
  min-height: 0;
}

.retail-manual-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 10px;
  align-items: stretch;
}

.retail-manual-body.is-single {
  grid-template-columns: minmax(0, 1fr);
}

.retail-manual-card {
  min-width: 0;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.retail-manual-card--order {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  height: 100%;
}

.retail-manual-card--order :deep(.el-form-item) {
  margin-bottom: 0;
}

.retail-manual-card--addr {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.retail-manual-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 10px;
}

.retail-manual-order-form :deep(.el-form-item) {
  margin-bottom: 8px;
}

.retail-manual-order-form :deep(.el-form-item__label) {
  margin-bottom: 2px;
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  color: #64748b;
}

.retail-manual-order-form :deep(.el-select),
.retail-manual-order-form :deep(.el-input-number) {
  width: 100%;
}

.retail-manual-k {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.retail-manual-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  min-height: 36px;
  max-height: 132px;
  overflow: auto;
}

.retail-manual-item-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.retail-manual-item-row :deep(.el-input-number) {
  width: 108px;
  flex-shrink: 0;
}

.retail-manual-order-select {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.retail-manual-option {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.retail-manual-option img,
.retail-manual-option-ph {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 6px;
  object-fit: cover;
  background: #e2e8f0;
}

.retail-manual-option-text {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.retail-manual-add {
  align-self: flex-start;
  padding: 0;
  height: auto;
}

.retail-manual-addr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.retail-manual-map-wrap {
  height: 168px;
  margin: 0 0 16px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.retail-manual-map-wrap :deep(.mdmp) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.retail-manual-map-wrap :deep(.mdmp-search) {
  margin-bottom: 6px;
}

.retail-manual-map-wrap :deep(.mdmp-map) {
  flex: 1 1 auto;
  height: auto;
  min-height: 0;
}

.retail-manual-map-wrap :deep(.mdmp-search-btn) {
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--el-color-primary);
}

.retail-manual-order-coord {
  margin: 0 0 6px;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.retail-manual-order-member-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.3;
  color: #64748b;
}

.retail-manual-order-member-tip--ok {
  color: #047857;
}

.retail-manual-order-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.retail-manual-order-tip.is-warn {
  color: #c2410c;
}

.retail-manual-addr-note {
  margin-bottom: 14px;
}

.retail-manual-price {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.35;
  color: #be123c;
}

.retail-manual-order-result {
  padding: 10px 12px;
  border-radius: 10px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.retail-manual-order-result-title {
  margin: 0;
  font-size: 13px;
  font-weight: 700;
  color: #047857;
}

.retail-manual-order-result-sub {
  margin: 4px 0 0;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

@media (max-width: 860px) {
  .retail-manual-body,
  .retail-manual-body.is-single {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
/* 弹窗挂到 body，居中，不跟着旧的整页高度滚 */
.retail-manual-order-dialog.el-dialog,
.el-overlay .retail-manual-order-dialog.el-dialog {
  border-radius: 16px;
  padding: 0;
  background: #f7fafb;
  max-width: calc(100vw - 32px);
}

.retail-manual-order-dialog .el-dialog__header,
.el-overlay .retail-manual-order-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 16px 16px 0 0;
}

.retail-manual-order-dialog .el-dialog__body,
.el-overlay .retail-manual-order-dialog .el-dialog__body {
  padding: 12px 14px;
  background: #f7fafb;
}

.retail-manual-order-dialog .el-dialog__footer,
.el-overlay .retail-manual-order-dialog .el-dialog__footer {
  padding: 10px 16px 14px;
  background: #fff;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 0 0 16px 16px;
}

/* 下拉挂到 body，选项加高才能放下封面 */
.retail-manual-product-popper .el-select-dropdown__item {
  height: auto;
  min-height: 40px;
  line-height: 1.3;
  padding-top: 4px;
  padding-bottom: 4px;
}
</style>
