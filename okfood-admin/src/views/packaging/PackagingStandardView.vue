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
  <section class="mkt-page tab-content animate-up">
    <header class="mkt-page-head">
      <div class="mkt-page-head__copy">
        <p class="mkt-kicker">库存管理</p>
        <h1 class="mkt-title">每份标配</h1>
        <p class="mkt-intro">
          筷子、小勺这类每份都有的东西设一次即可。午餐和晚餐会各乘各的后厨出餐份数。打包袋不要放这里。
        </p>
      </div>
      <el-button type="primary" round :loading="saving" @click="save">保存标配</el-button>
    </header>

    <article v-loading="loading" class="mkt-card">
      <PackagingLineEditor v-model="lines" :sku-options="skuOptions" />
    </article>
  </section>
</template>
