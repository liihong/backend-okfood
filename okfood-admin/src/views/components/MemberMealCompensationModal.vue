<script setup>
import { ref, watch } from 'vue'
import { apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import OkfoodAdminDialogShell from '../../components/OkfoodAdminDialogShell.vue'
import MemberOperationContext from '../../components/MemberOperationContext.vue'

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
  <OkfoodAdminDialogShell
    v-model:open="open"
    title="补餐赔付"
    subtitle="餐品问题 · 补回已消费次数"
    size="md"
    :close-disabled="submitting"
    :close-on-backdrop="!submitting"
  >
    <template v-if="member" #operation-context>
      <MemberOperationContext
        dual-member-info
        :name="member.name"
        :phone="member.phone"
        :plan="member.plan"
        :balance="member.balance"
      />
    </template>
    <div class="okfood-dlg-hint-block" style="margin-top: 0">
      <span class="okfood-dlg-hint-block__label">审计与小程序可见性</span>
      <p class="okfood-dlg-hint-block__text">
        操作写入审计日志，用户可在小程序消费记录中查看补送记录。
      </p>
    </div>
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
        class="okfood-dlg-input-number"
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
    <template #footer>
      <el-button round :disabled="submitting" @click="open = false">取消</el-button>
      <el-button round type="primary" :loading="submitting" @click="submit">确认补餐</el-button>
    </template>
  </OkfoodAdminDialogShell>
</template>

