<script setup>
/**
 * 租户管理页 · 微信第三方平台 Ticket 运维面板（平台级，与单租户无关）
 */
defineProps({
  componentState: { type: Object, default: null },
  componentTicket: { type: String, default: '' },
  saving: { type: Boolean, default: false },
  startPushLoading: { type: Boolean, default: false },
})

const emit = defineEmits(['update:componentTicket', 'save', 'start-push'])
</script>

<template>
  <el-collapse v-if="componentState" class="component-collapse">
    <el-collapse-item name="wx-open">
      <template #title>
        <div class="component-ticket-head">
          <strong>微信第三方平台</strong>
          <el-tag :type="componentState.component_ticket_present ? 'success' : 'warning'" size="small">
            verify_ticket：{{ componentState.component_ticket_present ? '已落库' : '未就绪' }}
          </el-tag>
        </div>
      </template>
      <p class="component-ticket-hint">
        回调 URL：<code>/api/wx/open/component/callback</code>。
        控制台若显示「关闭推送Ticket」，请点「启动 Ticket 推送」；未接通时可手动粘贴 ticket。
        本面板为<strong>平台级</strong>配置，不影响 OK饭直连小程序。
      </p>
      <div class="component-ticket-row">
        <el-input
          :model-value="componentTicket"
          type="password"
          show-password
          placeholder="component_verify_ticket"
          maxlength="512"
          @update:model-value="(v) => emit('update:componentTicket', v)"
        />
        <el-button type="primary" :loading="saving" @click="emit('save')">保存 Ticket</el-button>
        <el-button type="warning" plain :loading="startPushLoading" @click="emit('start-push')">
          启动 Ticket 推送
        </el-button>
      </div>
    </el-collapse-item>
  </el-collapse>
</template>

<style scoped>
.component-collapse {
  margin-bottom: 16px;
  border: none;
  --el-collapse-header-bg-color: transparent;
  --el-collapse-content-bg-color: transparent;
}
.component-ticket-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.component-ticket-hint {
  margin: 0 0 10px;
  font-size: 0.85rem;
  line-height: 1.5;
  color: rgba(226, 232, 240, 0.8);
}
.component-ticket-hint code {
  color: #fde047;
  font-size: 0.8rem;
}
.component-ticket-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.component-ticket-row .el-input {
  flex: 1;
  min-width: 220px;
}
</style>
