<script setup>
/**
 * 租户小程序 · 正式版发布（提审 / 查状态 / 全量发布）
 */
import { computed, ref, watch } from 'vue'

const props = defineProps({
  publishState: { type: Object, default: null },
  categories: { type: Array, default: () => [] },
  form: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  submitting: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
  releasing: { type: Boolean, default: false },
})

const emit = defineEmits(['refresh-status', 'submit-audit', 'release', 'reload-categories'])

const canOperate = computed(() => Boolean(props.publishState?.authorizer_mode_active))
const hasCommitted = computed(() => Boolean(props.publishState?.last_committed_at))

const auditStatusTag = computed(() => {
  const s = props.publishState?.audit_status
  if (s === 0) return { type: 'success', text: props.publishState?.audit_status_label || '审核成功' }
  if (s === 1) return { type: 'danger', text: props.publishState?.audit_status_label || '审核被拒绝' }
  if (s === 2) return { type: 'warning', text: props.publishState?.audit_status_label || '审核中' }
  if (s === 3) return { type: 'info', text: props.publishState?.audit_status_label || '已撤回' }
  if (s === 4) return { type: 'warning', text: props.publishState?.audit_status_label || '审核延后' }
  return { type: 'info', text: '未提交审核' }
})

const categoryOptions = computed(() => {
  const items = Array.isArray(props.categories) ? props.categories : []
  return items.map((c, idx) => ({
    value: idx,
    label: `${c.first_class} / ${c.second_class}`,
    raw: c,
  }))
})

const selectedCategory = ref(null)

watch(
  () => props.categories,
  (list) => {
    if (Array.isArray(list) && list.length && selectedCategory.value == null) {
      selectedCategory.value = 0
    }
  },
  { immediate: true },
)

function buildAuditPayload() {
  const idx = selectedCategory.value
  const opt = categoryOptions.value.find((o) => o.value === idx)
  const cat = opt?.raw
  if (!cat) return null
  return {
    item_list: [
      {
        address: String(props.form.page_path || 'pages/home/index').trim() || 'pages/home/index',
        tag: cat.tag || `${cat.first_class} ${cat.second_class}`,
        first_class: cat.first_class,
        second_class: cat.second_class,
        first_id: cat.first_id,
        second_id: cat.second_id,
        title: String(props.form.page_title || '首页').trim() || '首页',
      },
    ],
    version_desc: String(props.form.version_desc || '').trim() || undefined,
    feedback_info: String(props.form.feedback_info || '').trim() || undefined,
  }
}

function onSubmitAudit() {
  const payload = buildAuditPayload()
  if (!payload) return
  emit('submit-audit', payload)
}
</script>

<template>
  <div v-loading="loading" class="formal-panel">
    <p class="panel-tip">
      体验版验证通过后：<strong>提交审核</strong> → 微信审核（通常 1～3 个工作日）→
      <strong>发布正式版</strong>全量上线。类目须已在商户小程序后台配置。
    </p>

    <el-alert
      v-if="!canOperate"
      type="warning"
      :closable="false"
      show-icon
      title="尚未启用 Authorizer"
      description="请先在「授权」页完成代授权。"
      class="mb-12"
    />
    <el-alert
      v-else-if="!hasCommitted"
      type="info"
      :closable="false"
      show-icon
      title="请先上传体验版"
      description="正式版提审基于当前体验版代码，须先完成上方「一键上传体验版」。"
      class="mb-12"
    />

    <el-descriptions :column="1" border size="small" class="mb-12" title="审核 / 正式版状态">
      <el-descriptions-item label="审核状态">
        <el-tag :type="auditStatusTag.type" size="small">{{ auditStatusTag.text }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="审核 ID">{{ publishState?.audit_id ?? '—' }}</el-descriptions-item>
      <el-descriptions-item label="提审版本">
        {{ publishState?.audit_user_version || publishState?.last_user_version || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="提审时间">{{ publishState?.audit_submitted_at || '—' }}</el-descriptions-item>
      <el-descriptions-item label="正式版发布时间">{{ publishState?.released_at || '—' }}</el-descriptions-item>
      <el-descriptions-item v-if="publishState?.audit_reason" label="拒绝原因">
        <span class="err-text">{{ publishState.audit_reason }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-form label-position="top" class="formal-form">
      <el-form-item label="审核类目（来自微信后台已配置类目）">
        <div class="cat-row">
          <el-select
            v-model="selectedCategory"
            filterable
            style="flex: 1"
            placeholder="请选择类目"
            :disabled="!canOperate"
          >
            <el-option
              v-for="opt in categoryOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
          <el-button :disabled="!canOperate" @click="emit('reload-categories')">刷新类目</el-button>
        </div>
        <p v-if="!categoryOptions.length" class="field-hint">暂无类目，请先在商户小程序后台配置服务类目后刷新。</p>
      </el-form-item>
      <el-form-item label="提审页面 path">
        <el-input v-model="form.page_path" maxlength="128" placeholder="pages/home/index" :disabled="!canOperate" />
      </el-form-item>
      <el-form-item label="版本说明 version_desc">
        <el-input
          v-model="form.version_desc"
          type="textarea"
          :rows="2"
          maxlength="512"
          show-word-limit
          placeholder="向审核人员说明本次版本功能变更"
          :disabled="!canOperate"
        />
      </el-form-item>
      <el-form-item label="反馈说明 feedback_info（被拒后重提可选）">
        <el-input
          v-model="form.feedback_info"
          type="textarea"
          :rows="2"
          maxlength="200"
          show-word-limit
          :disabled="!canOperate"
        />
      </el-form-item>
    </el-form>

    <div class="panel-actions">
      <el-button :loading="refreshing" :disabled="!canOperate" @click="emit('refresh-status')">
        刷新审核状态
      </el-button>
      <el-button
        type="warning"
        :loading="submitting"
        :disabled="!canOperate || !hasCommitted || !categoryOptions.length"
        @click="onSubmitAudit"
      >
        提交审核
      </el-button>
      <el-button
        type="danger"
        :loading="releasing"
        :disabled="!canOperate || !publishState?.can_release"
        @click="emit('release')"
      >
        发布正式版
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.panel-tip {
  margin: 0 0 16px;
  font-size: 0.85rem;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.88);
}
.mb-12 {
  margin-bottom: 12px;
}
.cat-row {
  display: flex;
  gap: 8px;
  width: 100%;
}
.field-hint {
  margin: 6px 0 0;
  font-size: 0.8rem;
  color: rgba(148, 163, 184, 0.95);
}
.panel-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.err-text {
  color: #f87171;
}
</style>
