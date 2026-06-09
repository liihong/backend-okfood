<script setup>
import { ref, watch } from 'vue'
import { X, UtensilsCrossed } from 'lucide-vue-next'
import { apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  member: { type: Object, default: null },
})

const emit = defineEmits(['saved'])

const submitting = ref(false)
const mealUnits = ref(1)
const remark = ref('')

watch(open, (v) => {
  if (!v) {
    mealUnits.value = 1
    remark.value = ''
    submitting.value = false
  }
})

async function submit() {
  const u = props.member
  if (!u?.id) return
  const units = Math.max(1, Math.min(50, Math.floor(Number(mealUnits.value) || 1)))
  submitting.value = true
  try {
    const data = await apiJson(
      `/api/admin/users/${Number(u.id)}/meal-compensation`,
      {
        method: 'POST',
        body: JSON.stringify({
          meal_units: units,
          remark: (remark.value || '').trim() || null,
        }),
      },
      { auth: true },
    )
    const after = data && typeof data === 'object' ? data.balance_after : null
    open.value = false
    showToast(
      after != null ? `已补餐 ${units} 次，剩余 ${after} 次` : `已补餐 ${units} 次`,
      'success',
    )
    emit('saved')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '补餐失败', 'error')
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div
    v-if="open"
    class="modal-overlay"
    v-esc-close="() => !submitting && (open = false)"
    @click.self="!submitting && (open = false)"
  >
    <div class="modal-card modal-card--meal-compensation">
      <div class="modal-header">
        <div class="header-info">
          <h3>补餐赔付</h3>
          <p>餐品问题 · 补回已消费次数</p>
        </div>
        <el-button text circle class="close-btn" :disabled="submitting" @click="open = false">
          <X :size="20" />
        </el-button>
      </div>
      <form class="modal-form" @submit.prevent="submit">
        <p v-if="member" class="modal-hint modal-hint--tight">
          {{ member.name || '—' }} · {{ member.phone || '' }}
          <span v-if="member.plan"> · {{ member.plan }}</span>
          <span v-if="member.balance != null"> · 当前剩余 {{ member.balance }} 次</span>
        </p>
        <p class="modal-hint meal-compensation-tip">
          因餐品质量问题等原因，将已消费次数补回会员余额。操作将写入审计日志，用户可在小程序消费记录中查看补送记录。
        </p>
        <div class="form-group">
          <label for="meal-compensation-units">补餐份数</label>
          <el-input-number
            id="meal-compensation-units"
            v-model="mealUnits"
            :min="1"
            :max="50"
            :step="1"
            :disabled="submitting"
            controls-position="right"
            class="meal-compensation-units-input"
          />
        </div>
        <div class="form-group">
          <label for="meal-compensation-remark">赔付说明（选填）</label>
          <el-input
            id="meal-compensation-remark"
            v-model="remark"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
            placeholder="如：6月8日午餐漏送配菜，补回1次"
            :disabled="submitting"
          />
        </div>
        <div class="modal-actions">
          <el-button :disabled="submitting" @click="open = false">取消</el-button>
          <el-button type="primary" native-type="submit" :loading="submitting">
            <UtensilsCrossed :size="16" aria-hidden="true" class="meal-compensation-btn-icon" />
            确认补餐
          </el-button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.modal-card--meal-compensation {
  max-width: 28rem;
}

.meal-compensation-tip {
  line-height: 1.5;
  margin-bottom: 0.5rem;
}

.meal-compensation-units-input {
  width: 100%;
}

.meal-compensation-units-input :deep(.el-input__wrapper) {
  width: 100%;
}

.meal-compensation-btn-icon {
  margin-right: 4px;
  vertical-align: -2px;
}
</style>
