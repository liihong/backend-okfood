<script setup>
/**
 * 租户小程序 · 品牌与首页配置面板
 * 写入 saas-config；不触发微信 commit（改配置一般无需重传代码）。
 */
import { HOME_LAYOUT_PRESETS, FEATURE_KEYS } from './tenantMiniProgramConstants.js'

defineProps({
  form: { type: Object, required: true },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['save'])
</script>

<template>
  <div class="brand-panel">
    <p class="panel-tip">
      此处配置会合并到小程序 <code>ext</code>，并通过 <code>GET /api/tenant/config</code> 下发。
      <strong>tenantId</strong> 须与 commit 时 <code>ext.tenantId</code> 一致。
      修改品牌/首页后一般<strong>不必</strong>重新上传代码。
    </p>

    <el-form label-position="top" class="brand-form">
      <el-divider content-position="left">基础</el-divider>
      <el-form-item label="外部 tenantId（tenants.code）">
        <el-input v-model="form.tenant_code" maxlength="64" placeholder="如 t_brand_a" />
      </el-form-item>
      <el-form-item label="小程序展示名称 appName">
        <el-input v-model="form.app_name" maxlength="128" placeholder="如：某某健康餐" />
      </el-form-item>
      <el-form-item label="默认门店 defaultStoreId">
        <el-input-number v-model="form.default_store_id" :min="1" :controls="true" class="w-full" />
      </el-form-item>
      <el-form-item label="首页模板 homeTemplate">
        <el-select v-model="form.home_template" style="width: 100%">
          <el-option label="default" value="default" />
          <el-option label="minimal" value="minimal" />
          <el-option label="catalog" value="catalog" />
        </el-select>
      </el-form-item>
      <el-form-item label="首页 layout 预设 homeLayoutPreset">
        <el-select v-model="form.home_layout_preset" style="width: 100%">
          <el-option
            v-for="p in HOME_LAYOUT_PRESETS"
            :key="p.value"
            :label="p.label"
            :value="p.value"
          />
        </el-select>
      </el-form-item>

      <el-divider content-position="left">主题 theme</el-divider>
      <el-form-item label="主色 primaryColor">
        <el-color-picker v-model="form.theme_primary_color" :show-alpha="false" />
        <el-input v-model="form.theme_primary_color" class="color-input" maxlength="16" />
      </el-form-item>
      <el-form-item label="页面背景 pageBg">
        <el-color-picker v-model="form.theme_page_bg" :show-alpha="false" />
        <el-input v-model="form.theme_page_bg" class="color-input" maxlength="16" />
      </el-form-item>

      <el-divider content-position="left">功能开关 features</el-divider>
      <div class="feature-grid">
        <el-form-item v-for="f in FEATURE_KEYS" :key="f.key" :label="f.label" class="feature-item">
          <el-switch v-model="form.features[f.key]" />
        </el-form-item>
      </div>

      <el-divider content-position="left">分享文案 share</el-divider>
      <el-form-item label="首页分享标题">
        <el-input v-model="form.share_home_title" maxlength="128" />
      </el-form-item>
      <el-form-item label="菜单页分享标题">
        <el-input v-model="form.share_order_title" maxlength="128" />
      </el-form-item>
      <el-form-item label="我的页 slogan">
        <el-input v-model="form.share_mine_slogan" maxlength="128" />
      </el-form-item>

      <el-divider content-position="left">法律协议 legal</el-divider>
      <el-form-item label="会员协议标题">
        <el-input v-model="form.legal_agreement_title" maxlength="256" />
      </el-form-item>
      <el-form-item label="会员协议 URL">
        <el-input v-model="form.legal_agreement_url" maxlength="512" placeholder="https://..." />
      </el-form-item>

      <el-divider content-position="left">订阅消息</el-divider>
      <el-form-item label="配送通知模板 ID">
        <el-input v-model="form.subscribe_delivery_tmpl_id" maxlength="128" />
      </el-form-item>
    </el-form>

    <div class="panel-actions">
      <el-button type="primary" :loading="saving" @click="emit('save')">保存品牌与首页</el-button>
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
.panel-tip code {
  font-size: 0.8rem;
  color: #fde047;
}
.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 16px;
}
.feature-item {
  margin-bottom: 0;
}
.color-input {
  margin-left: 12px;
  max-width: 160px;
}
.w-full {
  width: 100%;
}
.panel-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
