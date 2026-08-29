<script setup>
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { apiJson, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  storeId: { type: Number, default: 1 },
  initial: { type: Object, default: null },
})
const emit = defineEmits(['update:visible', 'saved'])

const saving = ref(false)
const previewing = ref(false)
const previewItems = ref([])
const formRef = ref(null)

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const form = ref(emptyForm())

function emptyForm() {
  return {
    name: '',
    sheet_label: '礼品券',
    plan_kinds: ['month'],
    date_range: [],
    exclude_membership_refunded: true,
  }
}

const rules = {
  name: [{ required: true, message: '请填写活动名称', trigger: 'blur' }],
  sheet_label: [{ required: true, message: '请填写厨房标签礼品名', trigger: 'blur' }],
  plan_kinds: [{ type: 'array', min: 1, message: '请至少选择月卡或季卡', trigger: 'change' }],
  date_range: [{ required: true, type: 'array', min: 2, message: '请选择开卡入账日区间', trigger: 'change' }],
}

watch(
  () => props.visible,
  (v) => {
    if (!v) return
    previewItems.value = []
    if (props.initial && props.initial.id) {
      form.value = {
        name: String(props.initial.name || ''),
        sheet_label: String(props.initial.sheet_label || '礼品券'),
        plan_kinds: Array.isArray(props.initial.plan_kinds) ? [...props.initial.plan_kinds] : ['month'],
        date_range: [props.initial.credited_from, props.initial.credited_to].filter(Boolean),
        exclude_membership_refunded: props.initial.exclude_membership_refunded !== false,
      }
    } else {
      form.value = emptyForm()
    }
  },
)

const isEdit = computed(() => Boolean(props.initial && props.initial.id))

function ruleBody() {
  const range = form.value.date_range || []
  return {
    plan_kinds: form.value.plan_kinds,
    credited_from: range[0],
    credited_to: range[1],
    exclude_membership_refunded: Boolean(form.value.exclude_membership_refunded),
  }
}

async function preview() {
  const kinds = Array.isArray(form.value.plan_kinds) ? form.value.plan_kinds : []
  const range = form.value.date_range || []
  if (!kinds.length) {
    ElMessage.warning('请至少选择月卡或季卡')
    return
  }
  if (!range[0] || !range[1]) {
    ElMessage.warning('请先选择开卡入账日区间，再预览名单')
    return
  }
  previewing.value = true
  try {
    const data = await apiJson(
      `/api/admin/gift-coupons/campaigns/preview-audience?store_id=${props.storeId}`,
      { method: 'POST', body: JSON.stringify(ruleBody()) },
      { auth: true },
    )
    previewItems.value = Array.isArray(data?.items) ? data.items : []
    const n = Number(data?.total) || previewItems.value.length
    ElMessage.success(n ? `圈到 ${n} 人，请在下方核对` : '该规则下没有符合条件的会员')
  } catch (e) {
    if (handleAdminLogout(e)) return
    ElMessage.error(e instanceof Error ? e.message : '预览失败')
  } finally {
    previewing.value = false
  }
}

async function submit() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  const range = form.value.date_range || []
  const payload = {
    name: String(form.value.name || '').trim(),
    sheet_label: String(form.value.sheet_label || '').trim(),
    plan_kinds: form.value.plan_kinds,
    credited_from: range[0],
    credited_to: range[1],
    exclude_membership_refunded: Boolean(form.value.exclude_membership_refunded),
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await apiJson(
        `/api/admin/gift-coupons/campaigns/${props.initial.id}?store_id=${props.storeId}`,
        { method: 'PATCH', body: JSON.stringify(payload) },
        { auth: true },
      )
      showToast('已保存', 'success')
    } else {
      await apiJson(
        `/api/admin/gift-coupons/campaigns?store_id=${props.storeId}`,
        { method: 'POST', body: JSON.stringify(payload) },
        { auth: true },
      )
      showToast('已创建草稿', 'success')
    }
    emit('saved')
    dialogVisible.value = false
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
    :title="isEdit ? '编辑礼品券活动' : '新建礼品券活动'"
    width="720px"
    destroy-on-close
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="活动名称" prop="name">
        <el-input v-model="form.name" maxlength="128" placeholder="如：2026年8月开卡礼品券" />
      </el-form-item>
      <el-form-item label="厨房标签礼品名" prop="sheet_label">
        <el-input v-model="form.sheet_label" maxlength="64" placeholder="打印在标签上，如：礼品券" />
      </el-form-item>
      <el-form-item label="开卡入账日" prop="date_range">
        <el-date-picker
          v-model="form.date_range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="卡型" prop="plan_kinds">
        <el-checkbox-group v-model="form.plan_kinds">
          <el-checkbox value="month" label="月卡" />
          <el-checkbox value="quarter" label="季卡" />
        </el-checkbox-group>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="form.exclude_membership_refunded">排除已退卡退款会员</el-checkbox>
      </el-form-item>
    </el-form>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="开卡日按工单入账日（不是起送日）。区间内任意买一次即入围，同一人只发一张。季卡按卡包种类识别，不会和月卡混算。"
      class="gift-form-alert"
    />
    <div class="gift-preview-bar">
      <el-button type="primary" :loading="previewing" @click="preview">名单预览</el-button>
      <span class="gift-preview-count">共 {{ previewItems.length }} 人（请核对后再保存并发放）</span>
    </div>
    <el-table :data="previewItems" max-height="280" stripe size="small" empty-text="点击「名单预览」后在此列出将发放的会员">
      <el-table-column type="index" label="#" width="50" />
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="phone" label="手机" min-width="120" />
      <el-table-column prop="card_kind_label" label="卡种类" width="100" />
      <el-table-column prop="credited_on" label="入账日" width="120" />
    </el-table>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存草稿</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.gift-form-alert {
  margin-bottom: 12px;
}
.gift-preview-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.gift-preview-count {
  color: var(--admin-muted, #64748b);
  font-size: 13px;
}
</style>
