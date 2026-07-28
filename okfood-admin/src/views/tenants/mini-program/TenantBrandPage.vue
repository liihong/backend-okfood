<script setup>
defineOptions({ name: 'TenantMiniBrandPage' })

import { ref, onMounted } from 'vue'
import TenantMiniProgramLayout from './TenantMiniProgramLayout.vue'
import TenantBrandConfigPanel from '../TenantBrandConfigPanel.vue'
import { useTenantMiniProgramPage } from '../../../composables/useTenantMiniProgramPage.js'
import { showToast } from '../../../composables/useToast.js'
import {
  brandFormFromPayload,
  brandPayloadFromForm,
  createEmptyBrandForm,
} from '../tenantMiniProgramConstants.js'

const { tenantId, tenantName, api, backToTenants, toastError, ensureReady } = useTenantMiniProgramPage()

const loading = ref(false)
const saving = ref(false)
const brandForm = ref(createEmptyBrandForm())

async function load() {
  if (!ensureReady() || !api.value) return
  loading.value = true
  try {
    const data = await api.value.loadSaasConfig()
    brandForm.value = brandFormFromPayload(data)
  } catch (e) {
    toastError(e, '加载失败')
  } finally {
    loading.value = false
  }
}

async function saveBrand() {
  if (!api.value) return
  const code = String(brandForm.value.tenant_code || '').trim()
  if (code && !/^[a-zA-Z0-9_-]+$/.test(code)) {
    showToast('tenantId 仅允许字母、数字、下划线、连字符', 'error')
    return
  }
  saving.value = true
  try {
    const data = await api.value.patchSaasConfig(brandPayloadFromForm(brandForm.value))
    brandForm.value = brandFormFromPayload(data)
    showToast('品牌与首页已保存', 'success')
  } catch (e) {
    toastError(e, '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void load()
})
</script>

<template>
  <TenantMiniProgramLayout
    v-if="tenantId != null"
    :tenant-id="tenantId"
    :tenant-name="tenantName"
    @back="backToTenants"
  >
    <TenantBrandConfigPanel
      v-loading="loading"
      :form="brandForm"
      :saving="saving"
      @save="saveBrand"
    />
  </TenantMiniProgramLayout>
</template>
