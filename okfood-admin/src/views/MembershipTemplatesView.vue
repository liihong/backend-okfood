<script setup>
defineOptions({ name: 'MembershipTemplatesView' })
import { ref, computed, onMounted } from 'vue'
import { Camera, Info, Plus, X } from 'lucide-vue-next'

/** 多行文本字数展示（与参考稿右下角计数一致） */
function textareaCount(text, max) {
  const n = (text == null ? '' : String(text)).length
  return `${n} / ${max}`
}
import {
  apiForm,
  apiJson,
  adminAccessToken,
  adminStoreBranding,
  DEFAULT_SIDEBAR_STORE_NAME,
  dishImageDisplayUrl,
  fetchAdminStoreBranding,
  handleAdminLogout,
} from '../admin/core.js'
import { showToast } from '../composables/useToast.js'

const list = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const saving = ref(false)
const editingId = ref(null)
const cardPhotoUploading = ref(false)
const cardPhotoUploadKey = ref(0)
/** 顶部说明横条是否展示 */
const bannerVisible = ref(true)
const form = ref({
  kind_label: '',
  name: '',
  meals_grant: 6,
  meal_periods: ['lunch'],
  deliver_dinner_with_lunch: false,
  list_price_yuan: '',
  sale_price_yuan: '',
  card_style_image_url: '',
  validity_days: null,
  intro_short: '',
  purchase_notice: '',
  remark: '',
  sort_order: 0,
  is_active: true,
})

/** 仅午+晚同时勾选时才询问是否与午餐一起配送 */
const showDeliverDinnerWithLunch = computed(() => {
  const ps = Array.isArray(form.value.meal_periods) ? form.value.meal_periods : []
  return ps.includes('lunch') && ps.includes('dinner')
})

function parseOptionalMoney(raw) {
  const t = String(raw ?? '').trim()
  if (!t) return null
  const n = Number(t)
  if (!Number.isFinite(n) || n < 0) {
    return undefined
  }
  return n.toFixed(2)
}

/** 无上传图时：按种类/餐次选用迷你卡面渐变（仅展示） */
function mealPeriodsLabel(row) {
  const ps = Array.isArray(row.meal_periods) ? row.meal_periods : ['lunch']
  const hasL = ps.includes('lunch')
  const hasD = ps.includes('dinner')
  if (hasL && hasD) return '午+晚'
  if (hasD) return '晚餐'
  return '午餐'
}

function cardPreviewClass(row) {
  const kind = String(row.kind_label || '')
  if (kind.includes('午晚餐') || kind.includes('晚餐')) {
    return 'mcard-mini-preview mcard-mini-preview--dinner'
  }
  const meals = Number(row.meals_grant) || 0
  if (meals > 12) return 'mcard-mini-preview mcard-mini-preview--month'
  return 'mcard-mini-preview mcard-mini-preview--week'
}

function validityLabel(row) {
  if (row.validity_days != null && row.validity_days !== '') return `${row.validity_days} 天`
  return '永久有效'
}

function fmtPriceYuan(v) {
  if (v == null || String(v).trim() === '') return null
  const n = Number(v)
  if (!Number.isFinite(n)) return null
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** 名称列副标题：优先商品简介 */
function cardSubtitle(row) {
  const t = String(row.intro_short || '').trim()
  if (t) return t
  const meals = row.meals_grant ?? '—'
  return `入账 ${meals} 次 · 小程序展示模板`
}

async function onCardPhotoUploadChange(uploadFile) {
  const file = uploadFile?.raw
  if (!file || !file.type.startsWith('image/')) return
  if (!adminAccessToken.value) {
    showToast('请先登录', 'error')
    return
  }
  cardPhotoUploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file)
    const data = await apiForm('/api/admin/upload', fd, { auth: true })
    const url = data && typeof data.url === 'string' ? data.url.trim() : ''
    if (url) {
      form.value.card_style_image_url = url
      showToast('卡片图已上传', 'success')
    } else {
      showToast('上传成功但未返回地址', 'error')
    }
  } catch (err) {
    const status = err && typeof err.status === 'number' ? err.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(err instanceof Error ? err.message : '上传失败', 'error')
  } finally {
    cardPhotoUploading.value = false
    cardPhotoUploadKey.value += 1
  }
}

/** 样式图预览左上角：优先门店/租户品牌名，勿写死 OK饭 */
const cardPreviewBrandName = computed(() => {
  const name = String(adminStoreBranding.value?.store_name || '').trim()
  return name || DEFAULT_SIDEBAR_STORE_NAME
})

async function fetchList() {
  if (!adminAccessToken.value) return
  loading.value = true
  try {
    const data = await apiJson('/api/admin/catalog/membership-templates', {}, { auth: true })
    list.value = Array.isArray(data) ? data : []
  } catch (e) {
    if (e?.status === 401) {
      alert('登录已过期')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.value = {
    kind_label: '',
    name: '',
    meals_grant: 6,
    meal_periods: ['lunch'],
    deliver_dinner_with_lunch: false,
    list_price_yuan: '',
    sale_price_yuan: '',
    card_style_image_url: '',
    validity_days: null,
    intro_short: '',
    purchase_notice: '',
    remark: '',
    sort_order: 0,
    is_active: true,
  }
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.value = {
    kind_label: row.kind_label ?? '',
    name: row.name || '',
    meals_grant: row.meals_grant,
    meal_periods: Array.isArray(row.meal_periods) && row.meal_periods.length ? [...row.meal_periods] : ['lunch'],
    deliver_dinner_with_lunch: row.deliver_dinner_with_lunch === true,
    list_price_yuan: row.list_price_yuan != null ? String(row.list_price_yuan).trim() : '',
    sale_price_yuan: row.sale_price_yuan != null ? String(row.sale_price_yuan).trim() : '',
    card_style_image_url: row.card_style_image_url || '',
    validity_days: row.validity_days != null ? Number(row.validity_days) : null,
    intro_short: row.intro_short || '',
    purchase_notice: row.purchase_notice || '',
    remark: row.remark || '',
    sort_order: row.sort_order,
    is_active: row.is_active,
  }
  dialogVisible.value = true
}

async function saveForm() {
  if (saving.value) return
  const kind = String(form.value.kind_label || '').trim()
  const name = String(form.value.name || '').trim()
  if (!kind) {
    showToast('请填写种类（如：周卡、季卡、午晚餐卡）', 'error')
    return
  }
  if (!name) {
    showToast('请填写名称', 'error')
    return
  }
  const periods = Array.isArray(form.value.meal_periods) ? form.value.meal_periods.filter(Boolean) : []
  if (!periods.length) {
    showToast('请至少选择一个覆盖餐段', 'error')
    return
  }
  const listPx = parseOptionalMoney(form.value.list_price_yuan)
  const salePx = parseOptionalMoney(form.value.sale_price_yuan)
  if (listPx === undefined || salePx === undefined) {
    showToast('原价、优惠价须为非负数字，留空表示不展示', 'error')
    return
  }
  let validityDays = null
  const rawVd = form.value.validity_days
  if (rawVd != null && rawVd !== '') {
    const n = Math.floor(Number(rawVd))
    if (!Number.isFinite(n) || n < 0) {
      showToast('有效天数须为非负整数或留空', 'error')
      return
    }
    validityDays = n
  }
  saving.value = true
  try {
    const common = {
      kind_label: kind,
      name,
      meals_grant: Number(form.value.meals_grant),
      meal_periods: periods,
      deliver_dinner_with_lunch: Boolean(
        periods.includes('lunch') && periods.includes('dinner') && form.value.deliver_dinner_with_lunch,
      ),
      list_price_yuan: listPx,
      sale_price_yuan: salePx,
      card_style_image_url: String(form.value.card_style_image_url || '').trim() || null,
      validity_days: validityDays,
      intro_short: String(form.value.intro_short || '').trim() || null,
      purchase_notice: String(form.value.purchase_notice || '').trim() || null,
      remark: String(form.value.remark || '').trim() || null,
      sort_order: Number(form.value.sort_order) || 0,
      is_active: Boolean(form.value.is_active),
    }
    if (editingId.value) {
      await apiJson(`/api/admin/catalog/membership-templates/${editingId.value}`, {
        method: 'PATCH',
        body: JSON.stringify(common),
      }, { auth: true })
      showToast('已保存')
    } else {
      await apiJson('/api/admin/catalog/membership-templates', {
        method: 'POST',
        body: JSON.stringify(common),
      }, { auth: true })
      showToast('已创建')
    }
    dialogVisible.value = false
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function removeRow(row) {
  const ok = window.confirm(`确定删除「${row.name}」？`)
  if (!ok) return
  try {
    await apiJson(`/api/admin/catalog/membership-templates/${row.id}`, { method: 'DELETE' }, { auth: true })
    showToast('已删除')
    await fetchList()
  } catch (e) {
    showToast(e instanceof Error ? e.message : '删除失败', 'error')
  }
}

onMounted(() => {
  void fetchAdminStoreBranding()
  void fetchList()
})
</script>

<template>
  <div class="mcard-page tab-content animate-up page-content-shell">
    <div class="page-content-title-row page-content-title-row--actions-only">
      <div class="page-content-title-actions">
        <button type="button" class="mcard-btn-add" @click="openCreate">
          <Plus :size="16" stroke-width="3" aria-hidden="true" />
          新增会员卡模板
        </button>
      </div>
    </div>

    <!-- 提示横条 -->
    <div v-show="bannerVisible" class="mcard-alert">
      <div class="mcard-alert-content">
        <Info :size="18" stroke-width="2.5" aria-hidden="true" />
        <span>
          种类可自定义；划线价/优惠价与卡片图为小程序展示用。自助微信支付开卡仍以「门店配置」周卡/月卡金额为准，与模板标价独立。
        </span>
      </div>
      <button type="button" class="mcard-alert-close" aria-label="关闭提示" @click="bannerVisible = false">
        <X :size="16" stroke-width="2.5" />
      </button>
    </div>

    <!-- 主表格 -->
    <div class="mcard-main-card" v-loading="loading">
      <div class="mcard-table-scroll">
        <table class="mcard-table">
          <thead>
            <tr>
              <th class="mcard-th mcard-th--preview">样式图</th>
              <th class="mcard-th mcard-th--kind">种类</th>
              <th class="mcard-th mcard-th--name">卡片名称</th>
              <th class="mcard-th mcard-th--center">入账餐次</th>
              <th class="mcard-th mcard-th--price">标价明细</th>
              <th class="mcard-th mcard-th--valid">有效天数</th>
              <th class="mcard-th mcard-th--center">排序</th>
              <th class="mcard-th mcard-th--center">启用</th>
              <th class="mcard-th mcard-th--remark">备注</th>
              <th class="mcard-th mcard-th--actions">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loading && !list.length">
              <td colspan="10" class="mcard-empty">暂无模版</td>
            </tr>
            <tr v-for="row in list" :key="row.id">
              <td>
                <div v-if="row.card_style_image_url" class="mcard-thumb-wrap">
                  <img
                    :src="dishImageDisplayUrl(row.card_style_image_url)"
                    alt=""
                    class="mcard-thumb-img"
                  />
                </div>
                <div v-else :class="cardPreviewClass(row)">
                  <span class="mcard-mini-brand">{{ cardPreviewBrandName }}</span>
                  <span class="mcard-mini-name">{{ row.name || '—' }}</span>
                  <span class="mcard-mini-meals">{{ row.meals_grant }}餐</span>
                </div>
              </td>
              <td>
                <span class="mcard-type-badge">{{ row.kind_label || '—' }}</span>
                <span class="mcard-period-badge">{{ mealPeriodsLabel(row) }}</span>
              </td>
              <td>
                <div class="mcard-identity">
                  <span class="mcard-card-title">{{ row.name || '—' }}</span>
                  <span class="mcard-card-desc">{{ cardSubtitle(row) }}</span>
                </div>
              </td>
              <td>
                <div class="mcard-cell-center">
                  <span class="mcard-meals-badge">{{ row.meals_grant ?? '—' }}</span>
                </div>
              </td>
              <td>
                <div class="mcard-price-stack">
                  <span v-if="fmtPriceYuan(row.list_price_yuan)" class="mcard-original-price">
                    原价 ¥{{ fmtPriceYuan(row.list_price_yuan) }}
                  </span>
                  <span v-else class="mcard-original-price mcard-original-price--empty">原价 —</span>
                  <span v-if="fmtPriceYuan(row.sale_price_yuan)" class="mcard-discount-price">
                    优惠 ¥{{ fmtPriceYuan(row.sale_price_yuan) }}
                  </span>
                  <span v-else class="mcard-discount-price mcard-discount-price--empty">优惠 —</span>
                </div>
              </td>
              <td>
                <span class="mcard-validity">{{ validityLabel(row) }}</span>
              </td>
              <td>
                <div class="mcard-cell-center">
                  <span class="mcard-sort-readonly">{{ row.sort_order ?? 0 }}</span>
                </div>
              </td>
              <td>
                <div class="mcard-cell-center">
                  <span
                    class="mcard-switch"
                    :class="{ 'mcard-switch--on': row.is_active }"
                    role="img"
                    :aria-label="row.is_active ? '已启用' : '未启用'"
                  >
                    <span class="mcard-switch-knob" />
                  </span>
                </div>
              </td>
              <td>
                <span class="mcard-remark">{{ (row.remark || '').trim() || '—' }}</span>
              </td>
              <td>
                <div class="mcard-actions">
                  <button type="button" class="mcard-btn-action mcard-btn-action--edit" @click="openEdit(row)">
                    编辑
                  </button>
                  <button type="button" class="mcard-btn-action mcard-btn-action--delete" @click="removeRow(row)">
                    删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 新建/编辑模版弹窗：UI 对齐参考稿，保存/校验逻辑不变 -->
    <el-dialog
      v-model="dialogVisible"
      class="mcard-template-dialog"
      width="680px"
      align-center
      destroy-on-close
      :show-close="false"
    >
      <template #header>
        <div class="mcard-modal-header">
          <h3 class="mcard-modal-title">{{ editingId ? '编辑模版' : '新建模版' }}</h3>
          <button type="button" class="mcard-modal-close" aria-label="关闭" @click="dialogVisible = false">
            <X :size="14" stroke-width="2.5" />
          </button>
        </div>
      </template>

      <div class="mcard-modal-body">
        <div class="mcard-form-grid">
          <div class="mcard-field">
            <label class="mcard-form-label">种类</label>
            <el-input
              v-model="form.kind_label"
              maxlength="64"
              size="small"
              class="mcard-form-control"
              placeholder="如：周卡、月卡、次卡、季卡、午晚餐餐卡"
            />
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">名称</label>
            <el-input
              v-model="form.name"
              maxlength="128"
              size="small"
              class="mcard-form-control"
              placeholder="如：标准六餐 — 可作具体套餐名"
            />
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">覆盖餐段</label>
            <el-checkbox-group v-model="form.meal_periods" size="small" class="mcard-form-control mcard-form-control--periods">
              <el-checkbox label="lunch">午餐</el-checkbox>
              <el-checkbox label="dinner">晚餐</el-checkbox>
            </el-checkbox-group>
          </div>

          <div v-if="showDeliverDinnerWithLunch" class="mcard-field mcard-field--span2">
            <label class="mcard-form-label">与午餐一起配送</label>
            <div class="mcard-form-control">
              <el-radio-group v-model="form.deliver_dinner_with_lunch" size="small">
                <el-radio :value="false">分开配送（午、晚各扣各的）</el-radio>
                <el-radio :value="true">一起配送（午餐送达时同时扣晚餐）</el-radio>
              </el-radio-group>
              <p class="mcard-form-hint">
                改此项只影响之后新开的卡；已入账会员仍按开卡时的选择扣次。
              </p>
            </div>
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">单笔入账餐次</label>
            <el-input-number
              v-model="form.meals_grant"
              :min="1"
              :max="366"
              size="small"
              controls-position="right"
              class="mcard-form-control mcard-form-control--number"
            />
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">原价(元)</label>
            <el-input
              v-model="form.list_price_yuan"
              size="small"
              class="mcard-form-control"
              placeholder="划线价，留空不在小程序展示"
            />
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">优惠价(元)</label>
            <el-input
              v-model="form.sale_price_yuan"
              size="small"
              class="mcard-form-control"
              placeholder="主推价，留空不在小程序展示"
            />
          </div>

          <div class="mcard-field">
            <label class="mcard-form-label">有效天数</label>
            <el-input-number
              v-model="form.validity_days"
              :min="0"
              :max="3660"
              :precision="0"
              size="small"
              controls-position="right"
              class="mcard-form-control mcard-form-control--number"
              placeholder="展示用"
            />
          </div>

          <div class="mcard-field mcard-field--split">
            <div class="mcard-field">
              <label class="mcard-form-label">排序</label>
              <el-input-number
                v-model="form.sort_order"
                :min="0"
                size="small"
                controls-position="right"
                class="mcard-form-control mcard-form-control--number"
              />
            </div>
            <div class="mcard-field mcard-field--switch">
              <label class="mcard-form-label">启用</label>
              <el-switch v-model="form.is_active" size="small" class="mcard-form-switch" />
            </div>
          </div>

          <div class="mcard-field mcard-field--span2">
            <label class="mcard-form-label">卡片样式图</label>
            <div class="mcard-upload-row">
              <el-upload
                :key="cardPhotoUploadKey"
                class="mcard-style-upload"
                :show-file-list="false"
                :auto-upload="false"
                accept="image/*"
                @change="onCardPhotoUploadChange"
              >
                <button type="button" class="mcard-btn-upload" :disabled="cardPhotoUploading">
                  <Camera :size="14" stroke-width="2.5" aria-hidden="true" />
                  {{ cardPhotoUploading ? '上传中…' : '上传图片' }}
                </button>
              </el-upload>
              <el-input
                v-model="form.card_style_image_url"
                size="small"
                class="mcard-form-control"
                placeholder="/static/uploads/... 或上传"
              />
              <img
                v-if="form.card_style_image_url"
                :src="dishImageDisplayUrl(form.card_style_image_url)"
                alt=""
                class="mcard-upload-preview"
              />
            </div>
          </div>

          <div class="mcard-field mcard-field--span2">
            <label class="mcard-form-label">商品简介</label>
            <div class="mcard-textarea-wrap">
              <el-input
                v-model="form.intro_short"
                type="textarea"
                :rows="2"
                maxlength="512"
                :show-word-limit="false"
                size="small"
                class="mcard-textarea-control"
                placeholder="一句话卖点，对应小程序「商品简介」"
              />
              <span class="mcard-char-counter">{{ textareaCount(form.intro_short, 512) }}</span>
            </div>
          </div>

          <div class="mcard-field mcard-field--span2">
            <label class="mcard-form-label">购买须知</label>
            <div class="mcard-textarea-wrap">
              <el-input
                v-model="form.purchase_notice"
                type="textarea"
                :rows="2"
                maxlength="6000"
                :show-word-limit="false"
                size="small"
                class="mcard-textarea-control"
                placeholder="有效期说明、使用限制、适用门店等"
              />
              <span class="mcard-char-counter">{{ textareaCount(form.purchase_notice, 6000) }}</span>
            </div>
          </div>

          <div class="mcard-field mcard-field--span2">
            <label class="mcard-form-label">备注</label>
            <el-input
              v-model="form.remark"
              type="textarea"
              :rows="1"
              size="small"
              class="mcard-textarea-control mcard-textarea-control--plain"
              placeholder="备注信息"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="mcard-modal-footer">
          <button type="button" class="mcard-btn-modal mcard-btn-modal--cancel" @click="dialogVisible = false">
            取消
          </button>
          <button
            type="button"
            class="mcard-btn-modal mcard-btn-modal--submit"
            :disabled="saving"
            @click="saveForm"
          >
            {{ saving ? '提交中…' : editingId ? '保存' : '创建' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.mcard-page {
  --mcard-primary: #0d5c46;
  --mcard-primary-hover: #0a4635;
  --mcard-border: #eaedf1;
  --mcard-muted: #64748b;
  --mcard-danger-bg: #fef2f2;
  --mcard-danger-text: #ef4444;
  --mcard-info-bg: #f0fdf4;
  --mcard-info-text: #166534;
  --mcard-info-border: #bbf7d0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.mcard-btn-add {
  background: var(--mcard-primary);
  color: #fff;
  border: none;
  padding: 12px 24px;
  border-radius: 16px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 8px 16px -4px rgba(13, 92, 70, 0.25);
  transition: all 0.3s ease;
}

.mcard-btn-add:hover {
  background: var(--mcard-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 12px 20px -4px rgba(13, 92, 70, 0.35);
}

/* 提示横条 */
.mcard-alert {
  background: var(--mcard-info-bg);
  border: 1px solid var(--mcard-info-border);
  border-radius: 20px;
  padding: 16px 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.mcard-alert-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--mcard-info-text);
  line-height: 1.5;
}

.mcard-alert-content svg {
  flex-shrink: 0;
  color: var(--mcard-primary);
  margin-top: 2px;
}

.mcard-alert-close {
  background: transparent;
  border: none;
  color: var(--mcard-muted);
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
  transition: opacity 0.2s;
  flex-shrink: 0;
}

.mcard-alert-close:hover {
  opacity: 1;
}

/* 主表格外壳 */
.mcard-main-card {
  background: #fff;
  border-radius: 32px;
  border: 1px solid var(--mcard-border);
  padding: 24px;
  box-shadow: 0 4px 20px -2px rgba(148, 163, 184, 0.05);
  overflow: hidden;
  min-height: 120px;
}

.mcard-table-scroll {
  width: 100%;
  overflow-x: auto;
}

.mcard-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
}

.mcard-th {
  background: #f8fafc;
  color: var(--mcard-muted);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 16px 20px;
  border-bottom: 2px solid var(--mcard-border);
  white-space: nowrap;
}

.mcard-th--center {
  text-align: center;
}

.mcard-th--actions {
  text-align: right;
}

.mcard-table td {
  padding: 20px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid var(--mcard-border);
  vertical-align: middle;
  color: #0f172a;
}

.mcard-table tbody tr:hover {
  background: #f8fafc;
}

.mcard-empty {
  text-align: center;
  color: #94a3b8;
  padding: 3rem 1rem !important;
}

/* 迷你卡面预览 */
.mcard-mini-preview {
  width: 84px;
  height: 52px;
  border-radius: 8px;
  padding: 6px;
  color: #fff;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 6px 12px -2px rgba(15, 23, 42, 0.15);
  position: relative;
  overflow: hidden;
}

.mcard-mini-preview::before {
  content: '';
  position: absolute;
  top: -20%;
  right: -20%;
  width: 50px;
  height: 50px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 50%;
}

.mcard-mini-preview--week {
  background: linear-gradient(135deg, #0d5c46 0%, #10b981 100%);
}

.mcard-mini-preview--month {
  background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
}

.mcard-mini-preview--dinner {
  background: linear-gradient(135deg, #d97706 0%, #fbbf24 100%);
}

.mcard-mini-brand {
  font-size: 8px;
  font-weight: 900;
  letter-spacing: 0.05em;
  opacity: 0.9;
  position: relative;
  z-index: 1;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mcard-mini-name {
  font-size: 7px;
  font-weight: 700;
  opacity: 0.8;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
  z-index: 1;
}

.mcard-mini-meals {
  font-size: 10px;
  font-weight: 900;
  text-align: right;
  font-family: var(--okfood-font-number);
  position: relative;
  z-index: 1;
}

.mcard-thumb-wrap {
  width: 84px;
  height: 52px;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 6px 12px -2px rgba(15, 23, 42, 0.12);
}

.mcard-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.mcard-type-badge {
  background: #f1f5f9;
  color: var(--mcard-muted);
  padding: 4px 10px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 800;
  display: inline-block;
}

.mcard-period-badge {
  margin-left: 6px;
  background: #ecfdf5;
  color: #047857;
  padding: 4px 8px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 700;
  display: inline-block;
}

.mcard-identity {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mcard-card-title {
  font-weight: 800;
  color: #0f172a;
  font-size: 14px;
}

.mcard-card-desc {
  font-size: 11px;
  color: var(--mcard-muted);
  font-weight: 500;
  line-height: 1.4;
}

.mcard-cell-center {
  display: flex;
  justify-content: center;
}

.mcard-meals-badge {
  background: #ecfdf5;
  color: var(--mcard-primary);
  border: 1px solid rgba(16, 185, 129, 0.15);
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 900;
  font-family: var(--okfood-font-number);
}

.mcard-price-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.mcard-original-price {
  font-size: 11px;
  color: var(--mcard-muted);
  text-decoration: line-through;
  font-family: var(--okfood-font-number);
}

.mcard-discount-price {
  font-size: 15px;
  font-weight: 800;
  color: var(--mcard-primary);
  font-family: var(--okfood-font-number);
}

.mcard-discount-price--empty,
.mcard-original-price--empty {
  opacity: 0.55;
  text-decoration: none;
}

.mcard-validity {
  color: var(--mcard-muted);
  font-weight: 700;
}

.mcard-sort-readonly {
  display: inline-block;
  min-width: 60px;
  padding: 6px 10px;
  border-radius: 10px;
  border: 1px solid var(--mcard-border);
  background: #f8fafc;
  text-align: center;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* 启用：仅展示态开关（编辑仍在弹窗 el-switch） */
.mcard-switch {
  display: inline-block;
  position: relative;
  width: 44px;
  height: 24px;
  background: #cbd5e1;
  border-radius: 34px;
  flex-shrink: 0;
}

.mcard-switch--on {
  background: var(--mcard-primary);
}

.mcard-switch-knob {
  position: absolute;
  height: 18px;
  width: 18px;
  left: 3px;
  bottom: 3px;
  background: #fff;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  transition: transform 0.3s;
}

.mcard-switch--on .mcard-switch-knob {
  transform: translateX(20px);
}

.mcard-remark {
  color: var(--mcard-muted);
  max-width: 150px;
  display: inline-block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcard-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.mcard-btn-action {
  border: none;
  padding: 8px 14px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.2s;
}

.mcard-btn-action--edit {
  background: #f1f5f9;
  color: #0f172a;
}

.mcard-btn-action--edit:hover {
  background: #e2e8f0;
}

.mcard-btn-action--delete {
  background: var(--mcard-danger-bg);
  color: var(--mcard-danger-text);
}

.mcard-btn-action--delete:hover {
  background: #fecaca;
}

/* ── 新建/编辑模版弹窗：紧凑尺寸 ── */
.mcard-template-dialog :deep(.el-dialog) {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid var(--mcard-border);
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.15);
  max-width: calc(100vw - 32px);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  margin: 0;
}

.mcard-template-dialog :deep(.el-dialog__header) {
  padding: 0;
  margin: 0;
}

.mcard-template-dialog :deep(.el-dialog__body) {
  padding: 0;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.mcard-template-dialog :deep(.el-dialog__footer) {
  padding: 0;
}

.mcard-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--mcard-border);
}

.mcard-modal-title {
  margin: 0;
  font-size: 15px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.25;
}

.mcard-modal-close {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 50%;
  background: #f1f5f9;
  color: var(--mcard-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background 0.2s,
    color 0.2s;
}

.mcard-modal-close:hover {
  background: #e2e8f0;
  color: #0f172a;
}

.mcard-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  max-height: calc(86vh - 96px);
}

.mcard-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
  align-items: start;
}

.mcard-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.mcard-field--span2 {
  grid-column: 1 / -1;
}

.mcard-field--split {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px 12px;
  align-items: start;
}

.mcard-field--switch {
  min-width: 48px;
}

.mcard-form-label {
  text-align: left;
  font-size: 12px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.3;
}

.mcard-form-control {
  width: 100%;
}

.mcard-form-control :deep(.el-input__wrapper) {
  padding: 1px 10px;
  border-radius: 8px;
  box-shadow: 0 0 0 1px var(--mcard-border) inset;
  background: #fff;
}

.mcard-form-control :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    0 0 0 1px var(--mcard-primary) inset,
    0 0 0 2px rgba(13, 92, 70, 0.08);
}

.mcard-form-control :deep(.el-input__inner) {
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
}

.mcard-form-control :deep(.el-radio-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
}

.mcard-form-control :deep(.el-radio),
.mcard-form-control :deep(.el-checkbox) {
  height: auto;
  margin-right: 0;
}

.mcard-form-control--number {
  width: 100%;
  --el-input-number-width: 100%;
}

.mcard-form-control--number :deep(.el-input__wrapper) {
  padding: 1px 8px;
}

.mcard-form-control--periods {
  min-height: 28px;
  display: flex;
  align-items: center;
}

.mcard-form-hint {
  margin: 4px 0 0;
  font-size: 11px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
}

.mcard-field--switch .mcard-form-switch {
  height: 28px;
  display: inline-flex;
  align-items: center;
}

.mcard-upload-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.mcard-upload-row .mcard-form-control {
  flex: 1;
  min-width: 0;
  width: auto;
}

.mcard-style-upload {
  flex-shrink: 0;
}

.mcard-style-upload :deep(.el-upload) {
  display: inline-block;
}

.mcard-btn-upload {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border: 1px solid var(--mcard-border);
  background: #fff;
  color: var(--mcard-muted);
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  transition:
    background 0.2s,
    border-color 0.2s,
    color 0.2s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.mcard-btn-upload:hover:not(:disabled) {
  background: #f1f5f9;
  border-color: #cbd5e1;
  color: #0f172a;
}

.mcard-btn-upload:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.mcard-upload-preview {
  width: 56px;
  height: 36px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--mcard-border);
  flex-shrink: 0;
}

.mcard-textarea-wrap {
  position: relative;
  width: 100%;
}

.mcard-textarea-control :deep(.el-textarea__inner) {
  padding: 6px 10px 20px;
  border-radius: 8px;
  border: 1px solid var(--mcard-border);
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  box-shadow: none;
  min-height: 44px;
  line-height: 1.45;
}

.mcard-textarea-control :deep(.el-textarea__inner:focus) {
  border-color: var(--mcard-primary);
  box-shadow: 0 0 0 2px rgba(13, 92, 70, 0.08);
}

.mcard-textarea-control--plain :deep(.el-textarea__inner) {
  padding: 6px 10px;
  min-height: 32px;
}

.mcard-char-counter {
  position: absolute;
  right: 8px;
  bottom: 4px;
  font-size: 10px;
  font-weight: 700;
  color: var(--mcard-muted);
  pointer-events: none;
}

.mcard-form-switch :deep(.el-switch__core) {
  width: 36px;
  height: 20px;
  border-radius: 34px;
}

.mcard-form-switch :deep(.el-switch__core .el-switch__action) {
  width: 14px;
  height: 14px;
}

.mcard-form-switch.is-checked :deep(.el-switch__core) {
  background-color: var(--mcard-primary);
  border-color: var(--mcard-primary);
}

.mcard-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 10px 16px;
  border-top: 1px solid var(--mcard-border);
  background: #f8fafc;
  border-bottom-left-radius: 16px;
  border-bottom-right-radius: 16px;
}

.mcard-btn-modal {
  padding: 7px 16px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.mcard-btn-modal--cancel {
  background: #fff;
  color: var(--mcard-muted);
  border: 1px solid var(--mcard-border);
}

.mcard-btn-modal--cancel:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.mcard-btn-modal--submit {
  background: var(--mcard-primary);
  color: #fff;
  box-shadow: 0 8px 16px -4px rgba(13, 92, 70, 0.25);
}

.mcard-btn-modal--submit:hover:not(:disabled) {
  background: var(--mcard-primary-hover);
}

.mcard-btn-modal--submit:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .mcard-form-grid {
    grid-template-columns: 1fr;
  }

  .mcard-field--split {
    grid-template-columns: minmax(0, 1fr) auto;
  }
}

</style>
