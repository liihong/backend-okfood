<script setup>
/**
 * 商城订单：手动建单 / 协助抖音验券
 * 独立弹窗组件，通过 v-model 控制显隐，success 事件通知父级刷新列表
 */
import { computed, ref, watch } from 'vue'
import { apiJson, adminAccessToken } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'
import { formatMemberAddressOption } from '../utils/orderFormatters.js'

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
  retail_product_id: null,
  quantity: 1,
  store_pickup: false,
  member_address_id: null,
  pay_channel: '线下',
  pay_status: '已支付',
  amount_yuan: '',
  remark: '',
})

const selectedProduct = computed(() => {
  const id = manualForm.value.retail_product_id
  if (id == null) return null
  return products.value.find((p) => Number(p.id) === Number(id)) || null
})

const productOptionLabel = (p) => {
  const price = p.unit_price_yuan != null ? String(p.unit_price_yuan) : '—'
  return `${p.title}（¥${price}）`
}

function resetForm() {
  mode.value = 'douyin'
  phone.value = ''
  name.value = ''
  memberPreview.value = null
  douyinCode.value = ''
  douyinResult.value = null
  manualForm.value = {
    retail_product_id: null,
    quantity: 1,
    store_pickup: false,
    member_address_id: null,
    pay_channel: '线下',
    pay_status: '已支付',
    amount_yuan: '',
    remark: '',
  }
  memberAddresses.value = []
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
    if (products.value.length > 0 && manualForm.value.retail_product_id == null) {
      manualForm.value.retail_product_id = Number(products.value[0].id)
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
    const list = await apiJson(`/api/admin/users/${memberId}/addresses`, {}, { auth: true })
    memberAddresses.value = Array.isArray(list) ? list : []
    if (memberAddresses.value.length > 0) {
      const cur = manualForm.value.member_address_id
      const hit =
        cur != null && memberAddresses.value.some((a) => Number(a.id) === Number(cur))
      if (!hit) {
        const def = memberAddresses.value.find((a) => a.is_default)
        manualForm.value.member_address_id = Number((def || memberAddresses.value[0]).id)
      }
    } else {
      manualForm.value.member_address_id = null
    }
  } catch {
    memberAddresses.value = []
    manualForm.value.member_address_id = null
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
  () => phone.value,
  () => scheduleMemberPreview(),
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
  const productId = manualForm.value.retail_product_id
  if (productId == null) {
    showToast('请选择商品', 'error')
    return
  }
  if (!manualForm.value.store_pickup && !manualForm.value.member_address_id) {
    showToast('配送到家须选择配送地址', 'error')
    return
  }

  manualSubmitting.value = true
  try {
    const body = {
      phone: ph,
      name: (name.value || '').trim() || null,
      retail_product_id: Number(productId),
      quantity: Number(manualForm.value.quantity) || 1,
      store_pickup: Boolean(manualForm.value.store_pickup),
      member_address_id: manualForm.value.store_pickup
        ? null
        : Number(manualForm.value.member_address_id),
      pay_channel: manualForm.value.pay_channel,
      pay_status: manualForm.value.pay_status,
      amount_yuan: (manualForm.value.amount_yuan || '').trim() || null,
      remark: (manualForm.value.remark || '').trim() || null,
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
    width="640px"
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
        <el-form-item label="商品" required>
          <el-select
            v-model="manualForm.retail_product_id"
            filterable
            placeholder="选择上架商品"
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
        </el-form-item>

        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="数量">
              <el-input-number v-model="manualForm.quantity" :min="1" :max="50" />
            </el-form-item>
          </el-col>
          <el-col :span="16">
            <el-form-item label="履约方式">
              <el-radio-group v-model="manualForm.store_pickup">
                <el-radio :value="false">配送到家</el-radio>
                <el-radio :value="true">门店自提</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item v-if="!manualForm.store_pickup" label="配送地址" required>
          <el-select
            v-model="manualForm.member_address_id"
            filterable
            placeholder="选择会员配送地址"
            :loading="addressesLoading"
            :disabled="!memberPreview"
            class="retail-manual-order-select"
          >
            <el-option
              v-for="a in memberAddresses"
              :key="a.id"
              :label="formatMemberAddressOption(a)"
              :value="Number(a.id)"
            />
          </el-select>
          <p v-if="memberPreview && !addressesLoading && !memberAddresses.length" class="retail-manual-order-tip">
            该会员暂无配送地址，请先在会员档案中添加。
          </p>
          <p v-else-if="!memberPreview && phone.trim().length >= 5" class="retail-manual-order-tip">
            请先确认会员手机号匹配成功后再选地址。
          </p>
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

.retail-manual-order-select {
  width: 100%;
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
