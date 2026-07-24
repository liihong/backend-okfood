<script setup>
/**
 * 租户小程序 · 代码发布面板
 * 一键 commit（模板库 → 体验版）+ 拉取体验二维码。
 * 仅 authorizer 已启用时可操作；默认 template_id=1。
 */
import { computed } from 'vue'
import { DEFAULT_TEMPLATE_ID } from './tenantMiniProgramConstants.js'

const props = defineProps({
  publishState: { type: Object, default: null },
  templates: { type: Array, default: () => [] },
  form: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  committing: { type: Boolean, default: false },
  qrcodeLoading: { type: Boolean, default: false },
  qrcodeDataUrl: { type: String, default: '' },
})

const emit = defineEmits(['refresh', 'commit', 'fetch-qrcode', 'reload-templates'])

const canPublish = computed(() => Boolean(props.publishState?.authorizer_mode_active))

const preview = computed(() => props.publishState?.ext_preview || null)
const previewError = computed(() => props.publishState?.ext_preview_error || '')

const templateOptions = computed(() => {
  const items = Array.isArray(props.templates) ? props.templates : []
  if (items.length) return items
  // 列表拉取失败时仍允许用已知 ID=1 提交
  return [{ template_id: DEFAULT_TEMPLATE_ID, user_version: '—', user_desc: '本地默认（请先刷新模板列表）' }]
})
</script>

<template>
  <div v-loading="loading" class="publish-panel">
    <p class="panel-tip">
      将普通模板库代码上传到<strong>已代授权</strong>小程序并生成体验版。
      当前默认模板 ID=<strong>{{ DEFAULT_TEMPLATE_ID }}</strong>。
      未授权租户（含 OK饭直连）请继续用微信开发者工具上传，勿使用本功能。
    </p>

    <el-alert
      v-if="!canPublish"
      type="warning"
      :closable="false"
      show-icon
      title="尚未启用 Authorizer"
      description="请先到「授权」页完成代授权，再上传体验版。"
      class="mb-12"
    />

    <el-descriptions :column="1" border size="small" class="mb-12">
      <el-descriptions-item label="授权 AppID">
        {{ publishState?.authorizer_appid || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="最近版本">
        {{ publishState?.last_user_version || '—' }}
      </el-descriptions-item>
      <el-descriptions-item label="最近上传">
        {{ publishState?.last_committed_at || '—' }}
      </el-descriptions-item>
      <el-descriptions-item v-if="publishState?.last_error" label="最近错误">
        <span class="err-text">{{ publishState.last_error }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="previewError"
      type="info"
      :closable="false"
      show-icon
      :title="`ext 预览不可用：${previewError}`"
      class="mb-12"
    />
    <el-descriptions v-else-if="preview" :column="1" border size="small" class="mb-12" title="将注入的 ext 摘要">
      <el-descriptions-item label="extAppid">{{ preview.extAppid }}</el-descriptions-item>
      <el-descriptions-item label="tenantId">{{ preview.tenantId }}</el-descriptions-item>
      <el-descriptions-item label="appName">{{ preview.appName }}</el-descriptions-item>
      <el-descriptions-item label="apiBase">{{ preview.apiBase }}</el-descriptions-item>
      <el-descriptions-item label="storagePrefix">{{ preview.storagePrefix }}</el-descriptions-item>
      <el-descriptions-item label="homeTemplate">
        {{ preview.homeTemplate }} / {{ preview.homeLayoutPreset }}
      </el-descriptions-item>
    </el-descriptions>

    <el-form label-position="top" class="publish-form">
      <el-form-item label="模板库 template_id">
        <div class="tpl-row">
          <el-select v-model="form.template_id" filterable style="flex: 1" :disabled="!canPublish">
            <el-option
              v-for="t in templateOptions"
              :key="t.template_id"
              :label="`#${t.template_id} · ${t.user_version || '—'} · ${t.user_desc || ''}`"
              :value="t.template_id"
            />
          </el-select>
          <el-button :disabled="loading" @click="emit('reload-templates')">刷新列表</el-button>
        </div>
      </el-form-item>
      <el-form-item label="版本号 user_version">
        <el-input v-model="form.user_version" maxlength="64" :disabled="!canPublish" />
      </el-form-item>
      <el-form-item label="描述 user_desc">
        <el-input v-model="form.user_desc" maxlength="256" :disabled="!canPublish" />
      </el-form-item>
    </el-form>

    <div class="panel-actions">
      <el-button @click="emit('refresh')">刷新状态</el-button>
      <el-button
        type="primary"
        :loading="committing"
        :disabled="!canPublish || Boolean(previewError)"
        @click="emit('commit')"
      >
        一键上传体验版
      </el-button>
      <el-button
        type="success"
        plain
        :loading="qrcodeLoading"
        :disabled="!canPublish"
        @click="emit('fetch-qrcode')"
      >
        获取体验码
      </el-button>
    </div>

    <div v-if="qrcodeDataUrl" class="qrcode-box">
      <p class="panel-tip">体验版二维码（需先将微信号加为体验成员）</p>
      <img :src="qrcodeDataUrl" alt="体验版二维码" class="qrcode-img" />
      <div>
        <a :href="qrcodeDataUrl" download="trial-qrcode.jpg">下载图片</a>
      </div>
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
.tpl-row {
  display: flex;
  gap: 8px;
  width: 100%;
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
.qrcode-box {
  margin-top: 20px;
  text-align: center;
}
.qrcode-img {
  max-width: 240px;
  width: 100%;
  border-radius: 8px;
  background: #fff;
  padding: 8px;
}
</style>
