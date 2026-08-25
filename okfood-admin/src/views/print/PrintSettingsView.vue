<script setup>
defineOptions({ name: 'PrintSettingsView' })
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { apiJson, adminAccessToken, adminStoreBranding, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useStorePrint } from '../../composables/useStorePrint.js'
import { templatesForScene, defaultTemplateForScene } from '../../constants/printTemplates.js'

const router = useRouter()
const { storeQuery, testScenePrint, printing } = useStorePrint()

const loading = ref(false)
const saving = ref(false)
const activeScene = ref('delivery_sheet')
const profiles = ref([])
const settings = ref([])

const sceneProfiles = computed(() => profiles.value)
const sceneTemplates = computed(() =>
  templatesForScene(activeScene.value, adminStoreBranding.value?.tenant_id),
)

const currentSetting = computed(() => settings.value.find((s) => s.scene === activeScene.value) || {
  scene: activeScene.value,
  profile_id: null,
  template_key: defaultTemplateForScene(activeScene.value),
  copies_mode: 'per_unit',
})

async function loadAll() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const [p, s] = await Promise.all([
      apiJson(`/api/admin/store-print/profiles?${storeQuery()}`, {}, { auth: true }),
      apiJson(`/api/admin/store-print/scene-settings?${storeQuery()}`, {}, { auth: true }),
    ])
    profiles.value = Array.isArray(p) ? p : []
    settings.value = Array.isArray(s) ? s : []
  } catch (e) {
    handleAdminLogout(e)
  } finally {
    loading.value = false
  }
}

function updateSetting(patch) {
  const idx = settings.value.findIndex((x) => x.scene === activeScene.value)
  const base = currentSetting.value
  const next = { ...base, ...patch }
  if (idx >= 0) settings.value[idx] = next
  else settings.value.push(next)
}

async function save() {
  saving.value = true
  try {
    await apiJson(
      `/api/admin/store-print/scene-settings?${storeQuery()}`,
      { method: 'PUT', body: JSON.stringify({ settings: settings.value }) },
      { auth: true },
    )
    showToast('打印设置已保存', 'success')
    await loadAll()
  } catch (e) {
    showToast(e?.message || '保存失败', 'error')
    handleAdminLogout(e)
  } finally {
    saving.value = false
  }
}

async function onTestPrint() {
  const profileId = currentSetting.value.profile_id
  if (!profileId) {
    showToast('请先选择打印机', 'error')
    return
  }
  const storeName = String(adminStoreBranding.value?.store_name || '').trim() || 'OK饭'
  await testScenePrint({
    scene: activeScene.value,
    profileId,
    templateKey: currentSetting.value.template_key,
    storeName,
  })
}

onMounted(() => {
  void loadAll()
})
</script>

<template>
  <section v-loading="loading" class="print-settings animate-up">
    <div v-if="!profiles.length" class="ps-empty">
      <p>尚未配置打印机，请先在「打印机管理」中添加。</p>
      <el-button type="primary" @click="router.push({ name: 'system-printers' })">去添加打印机</el-button>
    </div>

    <template v-else>
      <el-tabs v-model="activeScene">
        <el-tab-pane label="配送标签" name="delivery_sheet" />
        <el-tab-pane label="商城零售标签" name="store_retail" />
      </el-tabs>

      <div class="ps-layout">
        <div class="ps-preview">
          <p class="ps-preview__title">预览说明</p>
          <p class="ps-preview__hint">
            <template v-if="currentSetting.template_key === 'delivery_enjoy_meal'">
              用餐愉快袋贴建议使用 60×90mm 竖版标签纸，须与「打印机管理」中纸张规格一致。姓名、餐别取配送会员资料；底部为扫码加好友二维码。
            </template>
            <template v-else>
              推荐使用 76×130mm 顺丰面单纸，须与「打印机管理」中纸张规格一致；推单成功后条码为顺丰运单号，可扫码。配送标签订单号为片区编码+序号（如 ZX001）；零售/商城与配送同款面单，右上角分别为「零售订单」「商城订单」，餐品行显示商品详情。若未单独配置「商城零售标签」，将自动使用配送标签的打印机。
            </template>
          </p>
          <div
            class="ps-preview__box"
            :class="{
              'ps-preview__box--waybill':
                (activeScene === 'delivery_sheet' || activeScene === 'store_retail')
                && currentSetting.template_key === 'delivery_meal_full',
              'ps-preview__box--enjoy': currentSetting.template_key === 'delivery_enjoy_meal',
            }"
          >
            <template
              v-if="
                (activeScene === 'delivery_sheet' || activeScene === 'store_retail')
                && currentSetting.template_key === 'delivery_meal_full'
              "
            >
              <div class="ps-preview__store-row">
                <span class="ps-preview__store-name">{{ adminStoreBranding?.store_name || 'OK饭' }}</span>
                <span class="ps-preview__fulfillment">{{
                  activeScene === 'store_retail' ? '商城订单' : '配送'
                }}</span>
              </div>
              <table class="ps-preview__sf-table">
                <tbody>
                  <tr><td class="ps-preview__sf-order-no">订单号：{{ activeScene === 'store_retail' ? 'OKF12345' : 'ZX001' }}</td></tr>
                  <tr><td class="ps-preview__sf-region">{{ activeScene === 'store_retail' ? '东区' : '中心医院' }}</td></tr>
                  <tr><td class="ps-preview__sf-member">李女士 · 132****6633</td></tr>
                  <tr><td class="ps-preview__sf-meal">{{
                    activeScene === 'store_retail' ? '餐品：冷萃果蔬汁 500ml' : '餐别：午+晚'
                  }}</td></tr>
                  <tr><td class="ps-preview__sf-meal">数量：1份</td></tr>
                  <tr><td class="ps-preview__sf-remark">备注：少辣</td></tr>
                  <tr><td>tips：1.若暂不吃，优先建议冷藏保存！</td></tr>
                </tbody>
              </table>
              <div class="ps-preview__sf-barcode">
                <div class="ps-preview__sf-barcode-bars" aria-hidden="true" />
                <div class="ps-preview__sf-no">SF6504306526672</div>
              </div>
            </template>
            <template v-else-if="currentSetting.template_key === 'delivery_enjoy_meal'">
              <div class="ps-preview__enjoy-head">
                <span class="ps-preview__enjoy-ico" aria-hidden="true">🛵</span>
                <span class="ps-preview__enjoy-hi">用餐愉快哦！</span>
                <span class="ps-preview__enjoy-ico" aria-hidden="true">:)</span>
              </div>
              <div class="ps-preview__enjoy-name">姓名：曹女士</div>
              <div class="ps-preview__enjoy-meal">餐别：午+果</div>
              <div class="ps-preview__enjoy-tip">1.酱汁根据个人口味酌量添加</div>
              <div class="ps-preview__enjoy-tip">2.若暂时不吃，优先建议冷藏保鲜！</div>
              <div class="ps-preview__enjoy-date">日期：2026/07/24</div>
              <div class="ps-preview__enjoy-foot">
                <span>扫码添加好友</span>
                <span class="ps-preview__enjoy-qr" aria-hidden="true" />
              </div>
            </template>
            <template v-else-if="activeScene === 'delivery_sheet'">
              <div class="ps-preview__region">东区</div>
              <div>3号楼502 张先生 ·5678</div>
              <div class="ps-preview__units">2 份</div>
              <div class="ps-preview__remark">备注：少辣</div>
            </template>
            <template v-else>
              <div class="ps-preview__region">【配送】</div>
              <div>商品名 x1</div>
              <div>李女士 ·6633</div>
            </template>
          </div>
        </div>

        <div class="ps-form">
          <el-form label-position="top">
            <el-form-item label="使用打印机">
              <el-select
                :model-value="currentSetting.profile_id"
                placeholder="选择打印机"
                clearable
                @update:model-value="(v) => updateSetting({ profile_id: v })"
              >
                <el-option v-for="p in sceneProfiles" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="打印模板">
              <el-radio-group
                :model-value="currentSetting.template_key"
                class="ps-template-list"
                @update:model-value="(v) => updateSetting({ template_key: v })"
              >
                <el-radio
                  v-for="t in sceneTemplates"
                  :key="t.key"
                  :value="t.key"
                  class="ps-template-item"
                >
                  <strong>{{ t.name }}</strong>
                  <span class="ps-template-desc">{{ t.description }}</span>
                </el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="副本策略">
              <el-radio-group
                :model-value="currentSetting.copies_mode"
                @update:model-value="(v) => updateSetting({ copies_mode: v })"
              >
                <el-radio value="per_unit">按份打印（一盒一张）</el-radio>
                <el-radio value="per_order">按单打印（一单一张）</el-radio>
              </el-radio-group>
            </el-form-item>
            <div class="ps-form-actions">
              <el-button type="primary" :loading="saving" @click="save">应用</el-button>
              <el-button
                :loading="printing"
                :disabled="!currentSetting.profile_id"
                @click="onTestPrint"
              >
                测试打印
              </el-button>
            </div>
            <p v-if="!currentSetting.profile_id" class="ps-test-hint">选择打印机后可试打一张测试页</p>
          </el-form>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.print-settings {
  background: #fff;
  border-radius: 12px;
  padding: 1rem 1.25rem;
  border: 1px solid #e5e7eb;
}
.ps-empty {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
}
.ps-layout {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 1.5rem;
  margin-top: 0.5rem;
}
@media (max-width: 768px) {
  .ps-layout {
    grid-template-columns: 1fr;
  }
}
.ps-preview__title {
  font-weight: 700;
  margin: 0 0 0.5rem;
}
.ps-preview__hint {
  font-size: 0.8rem;
  color: #6b7280;
  margin: 0 0 0.75rem;
}
.ps-preview__box {
  border: 2px dashed #d1d5db;
  border-radius: 8px;
  padding: 0.75rem;
  font-size: 0.85rem;
  line-height: 1.55;
  min-height: 140px;
}
.ps-preview__box--waybill {
  min-height: auto;
  font-size: 0.72rem;
  max-width: 220px;
}
.ps-preview__box--enjoy {
  max-width: 200px;
  font-size: 0.78rem;
}
.ps-preview__enjoy-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem;
  margin-bottom: 0.55rem;
}
.ps-preview__enjoy-hi {
  flex: 1;
  text-align: center;
  font-weight: 800;
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}
.ps-preview__enjoy-ico {
  font-size: 0.78rem;
  font-weight: 700;
  width: 1.2rem;
  text-align: center;
}
.ps-preview__enjoy-name,
.ps-preview__enjoy-meal {
  font-size: 1.05rem;
  font-weight: 800;
  line-height: 1.4;
}
.ps-preview__enjoy-meal {
  margin-bottom: 0.55rem;
}
.ps-preview__enjoy-tip {
  font-size: 0.72rem;
  color: #111;
  line-height: 1.5;
}
.ps-preview__enjoy-date {
  margin: 0.55rem 0 0.4rem;
  font-weight: 700;
  font-size: 0.82rem;
}
.ps-preview__enjoy-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.75rem;
  font-weight: 600;
}
.ps-preview__enjoy-qr {
  width: 2.4rem;
  height: 2.4rem;
  flex-shrink: 0;
  background:
    linear-gradient(#111 0 0) 0 0 / 33% 33%,
    linear-gradient(#111 0 0) 100% 0 / 33% 33%,
    linear-gradient(#111 0 0) 0 100% / 33% 33%,
    repeating-linear-gradient(90deg, #111 0 2px, #fff 2px 4px);
  background-repeat: no-repeat;
  border: 1px solid #111;
}
.ps-preview__store-row {
  position: relative;
  font-size: 0.82rem;
  font-weight: 800;
  margin-bottom: 0.35rem;
}
.ps-preview__store-name {
  display: block;
  width: 100%;
  text-align: center;
}
.ps-preview__fulfillment {
  position: absolute;
  right: 0;
  top: 0;
  font-weight: 800;
  white-space: nowrap;
}
.ps-preview__barcode {
  display: none;
}
.ps-preview__sf-barcode {
  margin-top: 0.1rem;
  padding-top: 0.3rem;
  border-top: 1px dashed #bbb;
  text-align: center;
}
.ps-preview__sf-barcode-bars {
  height: 1.6rem;
  margin: 0 auto 0.2rem;
  max-width: 92%;
  background: repeating-linear-gradient(90deg, #111 0 2px, #fff 2px 4px);
}
.ps-preview__sf-no {
  font-size: 0.65rem;
  color: #333;
  letter-spacing: 0.05em;
  font-family: monospace;
}
.ps-preview__sf-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.72rem;
}
.ps-preview__sf-table td {
  border: 1px solid #111;
  padding: 0.25rem 0.35rem;
}
.ps-preview__sf-order-no {
  font-weight: 800;
  font-size: 0.88rem;
  padding: 0.45rem 0.35rem !important;
  line-height: 1.45;
}
.ps-preview__sf-region {
  text-align: center;
  font-size: 1rem;
  font-weight: 900;
  padding: 0.4rem 0.25rem !important;
}
.ps-preview__sf-member {
  font-weight: 700;
  font-size: 0.88rem;
  padding: 0.4rem 0.35rem !important;
  line-height: 1.35;
}
.ps-preview__sf-meal {
  font-weight: 700;
  font-size: 0.98rem;
  padding: 0.5rem 0.35rem !important;
}
.ps-preview__sf-remark {
  font-weight: 700;
  font-size: 0.98rem;
  padding: 0.55rem 0.35rem !important;
  line-height: 1.45;
}
.ps-preview__date {
  font-weight: 700;
  font-size: 0.82rem;
  margin-bottom: 0.35rem;
}
.ps-preview__row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.5rem;
  font-weight: 700;
  font-size: 0.82rem;
  margin-bottom: 0.35rem;
}
.ps-preview__member {
  font-weight: 700;
  margin: 0.15rem 0;
}
.ps-preview__sep {
  margin: 0.5rem 0 0.35rem;
  color: #9ca3af;
  font-size: 0.75rem;
}
.ps-preview__tips-title {
  font-weight: 500;
  margin-bottom: 0.15rem;
}
.ps-preview__tips-block {
  text-align: center;
  margin-top: 0.35rem;
}
.ps-preview__tips {
  color: #4b5563;
}
.ps-preview__region {
  font-size: 1.25rem;
  font-weight: 900;
  margin-bottom: 0.35rem;
}
.ps-preview__units {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0.25rem 0;
}
.ps-preview__remark-big {
  margin-top: 0.3rem;
  padding: 0.3rem 0.35rem;
  font-size: 0.88rem;
  font-weight: 900;
  background: #fef3c7;
  border: 1px solid #f59e0b;
  border-radius: 4px;
  color: #92400e;
}
.ps-preview__remark {
  color: #4b5563;
  font-size: 0.8rem;
}
.ps-template-list {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
}
.ps-template-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  height: auto;
  white-space: normal;
}
.ps-template-desc {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: normal;
}
.ps-form-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  align-items: center;
}
.ps-test-hint {
  margin: 0.5rem 0 0;
  font-size: 0.78rem;
  color: #9ca3af;
}
</style>
