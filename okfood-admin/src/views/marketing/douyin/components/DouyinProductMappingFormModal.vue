<script setup>
import { ref, watch, computed } from 'vue'
import { apiJson, handleAdminLogout } from '../../../../admin/core.js'
import { showToast } from '../../../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  storeId: { type: Number, default: 1 },
  initial: { type: Object, default: null },
})

const emit = defineEmits(['update:visible', 'saved'])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const saving = ref(false)
const refsLoading = ref(false)
const formRef = ref(null)
const couponTemplates = ref([])
const membershipTemplates = ref([])

const form = ref(emptyForm())

const GRANT_OPTIONS = [
  { value: 'week_card', label: '周卡' },
  { value: 'month_card', label: '月卡' },
  { value: 'membership_template', label: '会员卡包' },
  { value: 'coupon_template', label: '优惠券' },
]

const needsTarget = computed(() =>
  ['membership_template', 'coupon_template'].includes(form.value.grant_type),
)

const targetLabel = computed(() =>
  form.value.grant_type === 'coupon_template' ? '关联优惠券' : '关联会员卡包',
)

const targetPlaceholder = computed(() => {
  if (refsLoading.value) return '加载中…'
  if (form.value.grant_type === 'coupon_template') {
    return couponTemplates.value.length ? '请选择优惠券券种' : '暂无可用券种，请先在优惠券管理创建'
  }
  if (form.value.grant_type === 'membership_template') {
    return membershipTemplates.value.length ? '请选择会员卡包' : '暂无可用卡包，请先在会员卡管理创建'
  }
  return '请选择'
})

const targetOptions = computed(() => {
  if (form.value.grant_type === 'coupon_template') {
    return couponTemplates.value.map((t) => ({
      id: Number(t.id),
      label: `${t.name}（减 ${t.discount_yuan} 元）`,
    }))
  }
  if (form.value.grant_type === 'membership_template') {
    return membershipTemplates.value
      .filter((t) => t.is_active !== false)
      .map((t) => ({
        id: Number(t.id),
        label: `${t.name}（${t.kind_label || '卡包'}）`,
      }))
  }
  return []
})

const rules = computed(() => ({
  display_name: [{ required: true, message: '请填写展示名称', trigger: 'blur' }],
  grant_type: [{ required: true, message: '请选择映射类型', trigger: 'change' }],
  target_id: needsTarget.value
    ? [{ required: true, message: '请选择关联目标', trigger: 'change' }]
    : [],
}))

function emptyForm() {
  return {
    display_name: '',
    douyin_product_id: '',
    douyin_sku_id: '',
    douyin_product_out_id: '',
    grant_type: 'coupon_template',
    target_id: null,
    is_active: true,
  }
}

function fillForm(row) {
  if (!row) {
    form.value = emptyForm()
    return
  }
  form.value = {
    display_name: row.display_name || '',
    douyin_product_id: row.douyin_product_id || '',
    douyin_sku_id: row.douyin_sku_id || '',
    douyin_product_out_id: row.douyin_product_out_id || '',
    grant_type: row.grant_type || 'coupon_template',
    target_id: row.target_id != null ? Number(row.target_id) : null,
    is_active: row.is_active !== false,
  }
}

async function loadRefs() {
  refsLoading.value = true
  const sid = props.storeId
  try {
    const [couponData, membershipData] = await Promise.all([
      apiJson(
        `/api/admin/marketing/coupon-templates?store_id=${sid}&active_only=true&page_size=100`,
        {},
        { auth: true },
      ),
      apiJson(`/api/admin/catalog/membership-templates?store_id=${sid}`, {}, { auth: true }),
    ])
    couponTemplates.value = Array.isArray(couponData?.items) ? couponData.items : []
    membershipTemplates.value = Array.isArray(membershipData) ? membershipData : []
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载关联选项失败', 'error')
  } finally {
    refsLoading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    fillForm(props.initial)
    void loadRefs()
  },
)

watch(
  () => form.value.grant_type,
  (next, prev) => {
    if (prev != null && next !== prev) {
      form.value.target_id = null
    }
  },
)

async function onSubmit() {
  if (saving.value) return
  const valid = await formRef.value?.validate?.().catch(() => false)
  if (valid === false) return

  const keys = [
    form.value.douyin_product_id.trim(),
    form.value.douyin_sku_id.trim(),
    form.value.douyin_product_out_id.trim(),
  ]
  if (!keys.some(Boolean)) {
    showToast('至少填写一个抖音商品标识（product_id / sku_id / product_out_id）', 'error')
    return
  }

  const body = {
    display_name: form.value.display_name.trim(),
    douyin_product_id: form.value.douyin_product_id.trim() || null,
    douyin_sku_id: form.value.douyin_sku_id.trim() || null,
    douyin_product_out_id: form.value.douyin_product_out_id.trim() || null,
    grant_type: form.value.grant_type,
    is_active: form.value.is_active,
  }

  if (needsTarget.value) {
    const tid = form.value.target_id
    if (tid == null || !Number.isFinite(Number(tid)) || Number(tid) < 1) {
      showToast(`请${targetLabel.value}`, 'error')
      return
    }
    const optionIds = new Set(targetOptions.value.map((o) => o.id))
    if (!optionIds.has(Number(tid))) {
      showToast('所选关联目标已下架或不存在，请重新选择', 'error')
      return
    }
    body.target_id = Number(tid)
  }

  saving.value = true
  try {
    if (props.initial?.id) {
      await apiJson(
        `/api/admin/marketing/douyin/product-mappings/${props.initial.id}?store_id=${props.storeId}`,
        { method: 'PATCH', body: JSON.stringify(body) },
        { auth: true },
      )
      showToast('已更新', 'success')
    } else {
      await apiJson(
        `/api/admin/marketing/douyin/product-mappings?store_id=${props.storeId}`,
        { method: 'POST', body: JSON.stringify(body) },
        { auth: true },
      )
      showToast('已创建', 'success')
    }
    emit('saved')
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="initial ? '编辑抖音商品映射' : '新建抖音商品映射'"
    width="560px"
    destroy-on-close
    @closed="fillForm(null)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" @submit.prevent="onSubmit">
      <el-form-item label="展示名称" prop="display_name">
        <el-input v-model="form.display_name" maxlength="128" placeholder="后台识别用，如：抖音50元代金券" />
      </el-form-item>
      <el-form-item label="product_id">
        <el-input
          v-model="form.douyin_product_id"
          maxlength="64"
          placeholder="抖音 product_id（与 sku_id 至少填一项）"
        />
      </el-form-item>
      <el-form-item label="sku_id">
        <el-input v-model="form.douyin_sku_id" maxlength="64" placeholder="抖音 sku_id" />
      </el-form-item>
      <el-form-item label="product_out_id">
        <el-input v-model="form.douyin_product_out_id" maxlength="64" placeholder="第三方 product_out_id" />
      </el-form-item>
      <el-form-item label="映射类型" prop="grant_type">
        <el-select v-model="form.grant_type" placeholder="选择本地权益类型" style="width: 100%">
          <el-option v-for="o in GRANT_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="needsTarget" :label="targetLabel" prop="target_id">
        <el-select
          v-model="form.target_id"
          :placeholder="targetPlaceholder"
          :loading="refsLoading"
          :disabled="refsLoading || !targetOptions.length"
          filterable
          clearable
          style="width: 100%"
        >
          <el-option v-for="o in targetOptions" :key="o.id" :label="o.label" :value="o.id" />
        </el-select>
        <p v-if="!refsLoading && !targetOptions.length" class="field-hint field-hint--warn">
          当前门店暂无可选{{ form.grant_type === 'coupon_template' ? '优惠券券种' : '会员卡包' }}，请先创建并上架。
        </p>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.is_active" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="needsTarget && !targetOptions.length" @click="onSubmit">
        保存
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--admin-muted, #64748b);
  line-height: 1.5;
}
.field-hint--warn {
  color: #b45309;
}
</style>
