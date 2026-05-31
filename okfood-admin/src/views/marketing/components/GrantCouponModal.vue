<script setup>
import { ref, watch, computed } from 'vue'
import { X } from 'lucide-vue-next'
import { apiJson, handleAdminLogout } from '../../../admin/core.js'
import { showToast } from '../../../composables/useToast.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  storeId: { type: Number, default: 1 },
})
const emit = defineEmits(['update:visible', 'saved'])

const saving = ref(false)
const templates = ref([])
const grantMode = ref('single')
const form = ref({ template_id: null, member_phone: '', member_phones_text: '', remark: '' })

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

/** 解析批量手机号：换行、逗号、分号分隔，去重 */
function parsePhones(text) {
  const seen = new Set()
  const out = []
  for (const part of String(text || '').split(/[\n,;，；\s]+/)) {
    const ph = part.trim().replace(/\s+/g, '').replace(/-/g, '')
    if (!ph || seen.has(ph)) continue
    seen.add(ph)
    out.push(ph)
  }
  return out
}

async function loadTemplates() {
  try {
    const data = await apiJson(
      `/api/admin/marketing/coupon-templates?store_id=${props.storeId}&active_only=true&page_size=100`,
      {},
      { auth: true },
    )
    templates.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    if (handleAdminLogout(e)) return
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      grantMode.value = 'single'
      form.value = { template_id: null, member_phone: '', member_phones_text: '', remark: '' }
      void loadTemplates()
    }
  },
)

function close() {
  dialogVisible.value = false
}

async function submit() {
  const tid = form.value.template_id
  if (!tid) {
    showToast('请选择券种', 'error')
    return
  }

  const remark = form.value.remark.trim() || null

  if (grantMode.value === 'single') {
    const phone = form.value.member_phone.trim().replace(/\s+/g, '').replace(/-/g, '')
    if (!phone) {
      showToast('请填写会员手机号', 'error')
      return
    }
  } else {
    const phones = parsePhones(form.value.member_phones_text)
    if (!phones.length) {
      showToast('请填写至少一个有效手机号', 'error')
      return
    }
  }

  saving.value = true
  try {
    if (grantMode.value === 'single') {
      const phone = form.value.member_phone.trim().replace(/\s+/g, '').replace(/-/g, '')
      await apiJson(
        `/api/admin/marketing/member-coupons/grant?store_id=${props.storeId}`,
        {
          method: 'POST',
          body: JSON.stringify({
            template_id: tid,
            member_phone: phone,
            remark,
          }),
        },
        { auth: true },
      )
      showToast('发放成功', 'success')
    } else {
      const phones = parsePhones(form.value.member_phones_text)
      const data = await apiJson(
        `/api/admin/marketing/member-coupons/grant-batch?store_id=${props.storeId}`,
        {
          method: 'POST',
          body: JSON.stringify({
            template_id: tid,
            member_phones: phones,
            remark,
          }),
        },
        { auth: true },
      )
      const ok = Number(data?.success_count || 0)
      const failed = Array.isArray(data?.failed) ? data.failed : []
      if (ok <= 0) {
        const first = failed[0]
        showToast(first?.reason || '批量发放失败', 'error')
        return
      }
      if (failed.length) {
        showToast(`成功 ${ok} 个，失败 ${failed.length} 个`, 'warning')
      } else {
        showToast(`成功发放 ${ok} 张优惠券`, 'success')
      }
    }
    emit('saved')
    close()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '发放失败', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    class="grant-coupon-dialog"
    width="520px"
    align-center
    destroy-on-close
    :show-close="false"
  >
    <template #header>
      <div class="grant-modal-header">
        <h3 class="grant-modal-title">发放优惠券</h3>
        <button type="button" class="grant-modal-close" aria-label="关闭" @click="close">
          <X :size="18" stroke-width="2.5" />
        </button>
      </div>
    </template>

    <el-form label-position="top" class="grant-form" @submit.prevent="submit">
      <el-form-item label="券种" required>
        <el-select
          v-model="form.template_id"
          placeholder="请选择券种"
          filterable
          style="width: 100%"
        >
          <el-option
            v-for="t in templates"
            :key="t.id"
            :label="`${t.name}（减 ${t.discount_yuan} 元）`"
            :value="t.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="发放方式">
        <el-radio-group v-model="grantMode">
          <el-radio value="single">单个发放</el-radio>
          <el-radio value="batch">批量发放</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="grantMode === 'single'" label="会员手机号" required>
        <el-input
          v-model="form.member_phone"
          maxlength="20"
          placeholder="请输入会员注册手机号"
          clearable
        />
      </el-form-item>

      <el-form-item v-else label="会员手机号" required>
        <el-input
          v-model="form.member_phones_text"
          type="textarea"
          :rows="5"
          placeholder="每行一个手机号，或用逗号、分号分隔"
        />
        <p class="field-hint">最多 200 个手机号，重复号码会自动去重</p>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" maxlength="500" placeholder="可选" clearable />
      </el-form-item>

      <div class="grant-modal-foot">
        <el-button @click="close">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">确认发放</el-button>
      </div>
    </el-form>
  </el-dialog>
</template>

<style scoped>
.grant-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.grant-modal-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #0f172a;
}
.grant-modal-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}
.grant-modal-close:hover {
  background: #f1f5f9;
  color: #0f172a;
}
.grant-form {
  padding-top: 4px;
}
.field-hint {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.grant-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}
</style>
