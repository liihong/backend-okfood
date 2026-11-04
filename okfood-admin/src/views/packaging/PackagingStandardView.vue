<script setup>
defineOptions({ name: 'PackagingStandardView' })
import { computed, onMounted, ref } from 'vue'
import { showToast } from '../../composables/useToast.js'
import { listPackagingSkus } from '../../api/packaging/sku.js'
import { listStandardPackaging, saveStandardPackaging } from '../../api/packaging/recipe.js'
import PackagingLineEditor from './components/PackagingLineEditor.vue'

const loading = ref(false)
const saving = ref(false)
const skus = ref([])
const lines = ref([])
const skuOptions = computed(() => skus.value.filter((item) => !item.is_meal_bag))

async function load() {
  loading.value = true
  try {
    const [skuRows, saved] = await Promise.all([listPackagingSkus(), listStandardPackaging()])
    skus.value = skuRows || []
    lines.value = (saved || []).map((line) => ({
      sku_id: line.sku_id,
      qty_per_portion: line.qty_per_portion,
    }))
  } catch (error) {
    showToast(error instanceof Error ? error.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

async function save() {
  const payload = lines.value
    .filter((line) => line.sku_id)
    .map((line) => ({ sku_id: line.sku_id, qty_per_portion: line.qty_per_portion || 1 }))
  saving.value = true
  try {
    await saveStandardPackaging(payload)
    showToast('每份标配已保存', 'success')
    await load()
  } catch (error) {
    showToast(error instanceof Error ? error.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <el-alert
      title="筷子、小勺这类每份都有的东西设一次即可。午餐和晚餐会各乘各的后厨出餐份数。打包袋不要放这里。"
      type="info"
      show-icon
      :closable="false"
      class="pack-gap"
    />
    <PackagingLineEditor v-model="lines" :sku-options="skuOptions" />
    <div class="pack-toolbar">
      <el-button type="primary" :loading="saving" @click="save">保存标配</el-button>
    </div>
  </div>
</template>

<style scoped>
.pack-gap { margin-bottom: 12px; }
.pack-toolbar { margin-top: 16px; }
</style>
