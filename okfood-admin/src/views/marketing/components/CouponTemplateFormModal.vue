<script setup>
import { ref, watch, computed } from 'vue'
import { X } from 'lucide-vue-next'
import { apiJson, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  storeId: { type: Number, default: 1 },
  initial: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'saved'])

const saving = ref(false)
const membershipTemplates = ref([])
const dishes = ref([])
const retailProducts = ref([])
const retailCategories = ref([])

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const form = ref(emptyForm())

function emptyForm() {
  return {
    name: '',
    discount_yuan: '',
    min_order_yuan: '0',
    biz_type: 'member_card',
    scope_level: 'all',
    scope_target_id: null,
    validity_mode: 'days_after_grant',
    valid_from: '',
    valid_until: '',
    valid_days_after_grant: 30,
    usage_instructions: '',
    sort_order: 0,
    max_grants: null,
    is_active: true,
  }
}

const scopeOptions = computed(() => {
  const b = form.value.biz_type
  if (b === 'member_card') {
    return [
      { v: 'all', l: '全部购卡' },
      { v: 'week_month', l: '仅周卡/月卡' },
      { v: 'membership_template', l: '指定卡包' },
    ]
  }
  if (b === 'single_meal') {
    return [
      { v: 'all', l: '全部可单点菜品' },
      { v: 'menu_dish', l: '指定菜品' },
    ]
  }
  if (b === 'store_retail') {
    return [
      { v: 'all', l: '全部零售 SKU' },
      { v: 'retail_category', l: '指定类目' },
      { v: 'retail_product', l: '指定商品' },
    ]
  }
  return [{ v: 'all', l: '通用' }]
})

const showScopeTarget = computed(() => {
  const lv = form.value.scope_level
  return ['membership_template', 'menu_dish', 'retail_product', 'retail_category'].includes(lv)
})

const scopeTargetOptions = computed(() => {
  const lv = form.value.scope_level
  if (lv === 'membership_template') {
    return membershipTemplates.value.map((t) => ({ id: t.id, label: t.name }))
  }
  if (lv === 'menu_dish') {
    return dishes.value.map((d) => ({ id: d.id, label: d.name }))
  }
  if (lv === 'retail_product') {
    return retailProducts.value.map((p) => ({ id: p.id, label: p.title }))
  }
  if (lv === 'retail_category') {
    return retailCategories.value.map((c) => ({ id: c.id, label: c.name }))
  }
  return []
})

async function loadRefs() {
  const sid = props.storeId
  try {
    const [tplData, dishData, catData, prodData] = await Promise.all([
      apiJson(`/api/admin/catalog/membership-templates?store_id=${sid}`, {}, { auth: true }),
      apiJson(`/api/admin/dishes?enabled_only=true`, {}, { auth: true }),
      apiJson(`/api/admin/catalog/retail-categories?store_id=${sid}`, {}, { auth: true }).catch(() => []),
      apiJson(`/api/admin/catalog/retail-products?store_id=${sid}`, {}, { auth: true }).catch(() => []),
    ])
    membershipTemplates.value = Array.isArray(tplData) ? tplData : []
    dishes.value = Array.isArray(dishData) ? dishData : []
    retailCategories.value = Array.isArray(catData) ? catData : []
    retailProducts.value = Array.isArray(prodData) ? prodData : []
  } catch (e) {
    if (handleAdminLogout(e)) return
  }
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    if (props.initial) {
      const r = props.initial
      form.value = {
        name: r.name || '',
        discount_yuan: String(r.discount_yuan || ''),
        min_order_yuan: String(r.min_order_yuan ?? '0'),
        biz_type: r.biz_type || 'member_card',
        scope_level: r.scope_level || 'all',
        scope_target_id: r.scope_target_id != null ? Number(r.scope_target_id) : null,
        validity_mode: r.validity_mode || 'days_after_grant',
        valid_from: r.valid_from ? r.valid_from.slice(0, 19).replace('T', ' ') : '',
        valid_until: r.valid_until ? r.valid_until.slice(0, 19).replace('T', ' ') : '',
        valid_days_after_grant:
          r.valid_days_after_grant != null ? Number(r.valid_days_after_grant) : 30,
        usage_instructions: r.usage_instructions || '',
        sort_order: Number(r.sort_order ?? 0),
        max_grants: r.max_grants != null ? Number(r.max_grants) : null,
        is_active: r.is_active !== false,
      }
    } else {
      form.value = emptyForm()
    }
    void loadRefs()
  },
)

watch(
  () => form.value.biz_type,
  () => {
    form.value.scope_level = 'all'
    form.value.scope_target_id = null
  },
)

function close() {
  dialogVisible.value = false
}

function buildBody() {
  const f = form.value
  const body = {
    name: String(f.name || '').trim(),
    discount_yuan: String(f.discount_yuan || '').trim(),
    min_order_yuan: String(f.min_order_yuan ?? '0').trim() || '0',
    biz_type: f.biz_type,
    scope_level: f.biz_type === 'all' ? 'all' : f.scope_level,
    validity_mode: f.validity_mode,
    usage_instructions: String(f.usage_instructions || '').trim() || null,
    sort_order: Number(f.sort_order) || 0,
    is_active: !!f.is_active,
  }
  if (showScopeTarget.value && f.scope_target_id != null) {
    body.scope_target_id = Number(f.scope_target_id)
  }
  if (f.validity_mode === 'days_after_grant') {
    body.valid_days_after_grant = Number(f.valid_days_after_grant) || 30
  } else {
    if (f.valid_from) body.valid_from = String(f.valid_from).replace(' ', 'T')
    if (f.valid_until) body.valid_until = String(f.valid_until).replace(' ', 'T')
  }
  if (f.max_grants != null && Number(f.max_grants) > 0) {
    body.max_grants = Math.floor(Number(f.max_grants))
  }
  return body
}

async function submit() {
  if (!String(form.value.name || '').trim() || !String(form.value.discount_yuan || '').trim()) {
    showToast('请填写名称与优惠金额', 'error')
    return
  }
  if (showScopeTarget.value && form.value.scope_target_id == null) {
    showToast('请选择适用范围目标', 'error')
    return
  }
  saving.value = true
  try {
    const body = buildBody()
    const sid = props.storeId
    if (props.initial?.id) {
      await apiJson(
        `/api/admin/marketing/coupon-templates/${props.initial.id}?store_id=${sid}`,
        { method: 'PATCH', body: JSON.stringify(body) },
        { auth: true },
      )
    } else {
      await apiJson(
        `/api/admin/marketing/coupon-templates?store_id=${sid}`,
        { method: 'POST', body: JSON.stringify(body) },
        { auth: true },
      )
    }
    showToast('已保存', 'success')
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
    class="coupon-template-dialog"
    width="680px"
    align-center
    destroy-on-close
    :show-close="false"
  >
    <template #header>
      <div class="coupon-modal-header">
        <h3 class="coupon-modal-title">{{ initial ? '编辑券种' : '新建券种' }}</h3>
        <button type="button" class="coupon-modal-close" aria-label="关闭" @click="close">
          <X :size="18" stroke-width="2.5" />
        </button>
      </div>
    </template>

    <el-form label-width="120px" class="coupon-form" @submit.prevent="submit">
      <el-form-item label="优惠券名称" required>
        <el-input v-model="form.name" maxlength="128" placeholder="如：新客购卡立减 50 元" />
      </el-form-item>

      <el-form-item label="优惠金额（元）" required>
        <el-input v-model="form.discount_yuan" placeholder="固定抵扣金额" />
      </el-form-item>

      <el-form-item label="最低消费（元）">
        <el-input v-model="form.min_order_yuan" placeholder="0 表示无门槛" />
      </el-form-item>

      <el-form-item label="业务线">
        <el-select v-model="form.biz_type" placeholder="选择业务线" style="width: 100%">
          <el-option label="全部小程序" value="all" />
          <el-option label="会员购卡" value="member_card" />
          <el-option label="菜单单次零售" value="single_meal" />
          <el-option label="商城零售" value="store_retail" />
        </el-select>
      </el-form-item>

      <template v-if="form.biz_type !== 'all'">
        <el-form-item label="适用范围">
          <el-select v-model="form.scope_level" placeholder="选择范围" style="width: 100%">
            <el-option v-for="o in scopeOptions" :key="o.v" :label="o.l" :value="o.v" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="showScopeTarget" label="指定目标" required>
          <el-select
            v-model="form.scope_target_id"
            filterable
            placeholder="请选择"
            style="width: 100%"
          >
            <el-option
              v-for="o in scopeTargetOptions"
              :key="o.id"
              :label="o.label"
              :value="o.id"
            />
          </el-select>
        </el-form-item>
      </template>

      <el-form-item label="有效期类型">
        <el-select v-model="form.validity_mode" style="width: 100%">
          <el-option label="发放后 N 天" value="days_after_grant" />
          <el-option label="固定时间段" value="fixed_range" />
        </el-select>
      </el-form-item>

      <el-form-item v-if="form.validity_mode === 'days_after_grant'" label="有效天数">
        <el-input-number
          v-model="form.valid_days_after_grant"
          :min="1"
          :max="3660"
          controls-position="right"
          style="width: 100%"
        />
      </el-form-item>

      <template v-else>
        <el-form-item label="开始时间">
          <el-date-picker
            v-model="form.valid_from"
            type="datetime"
            placeholder="选择开始时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker
            v-model="form.valid_until"
            type="datetime"
            placeholder="选择结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
      </template>

      <el-form-item label="使用说明">
        <el-input
          v-model="form.usage_instructions"
          type="textarea"
          :rows="3"
          maxlength="500"
          show-word-limit
          placeholder="展示给用户的用券说明"
        />
      </el-form-item>

      <el-form-item label="发放上限">
        <el-input-number
          v-model="form.max_grants"
          :min="1"
          :max="999999"
          controls-position="right"
          placeholder="留空表示不限"
          style="width: 100%"
        />
        <p class="field-hint">留空表示不限发放数量</p>
      </el-form-item>

      <el-form-item label="排序">
        <el-input-number
          v-model="form.sort_order"
          :min="0"
          :max="9999"
          controls-position="right"
          style="width: 100%"
        />
      </el-form-item>

      <el-form-item label="上架">
        <el-switch v-model="form.is_active" active-text="上架" inactive-text="下架" />
      </el-form-item>

      <div class="coupon-modal-foot">
        <el-button @click="close">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.coupon-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.coupon-modal-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}
.coupon-modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}
.coupon-modal-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}
.coupon-form {
  padding-top: 4px;
}
.field-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.coupon-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}
</style>
