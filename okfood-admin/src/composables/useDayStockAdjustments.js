/** 日库存损耗流水：报损耗、拉流水 */
import { ref } from 'vue'
import { apiJson, adminAccessToken } from '../admin/core.js'
import { showToast } from './useToast.js'

export const DAY_STOCK_REASON_OPTIONS = [
  { value: 'spill', label: '配送撒漏' },
  { value: 'kitchen_taste', label: '后厨试吃' },
  { value: 'kitchen_waste', label: '后厨报损' },
  { value: 'comp_meal', label: '客诉补餐' },
  { value: 'count_correction', label: '盘点校正' },
  { value: 'other', label: '其他' },
]

/**
 * @param {{ onSuccess?: () => void }} [opts]
 */
export function useDayStockAdjustments(opts = {}) {
  const modalOpen = ref(false)
  const modalMealPeriod = ref('lunch')
  const modalBusinessDate = ref('')
  const modalDelta = ref(-1)
  const modalReason = ref('spill')
  const modalRemark = ref('')
  const submitting = ref(false)

  /** @param {{ businessDate: string, mealPeriod?: string }} p */
  function openAdjustModal(p) {
    modalBusinessDate.value = p.businessDate
    modalMealPeriod.value = p.mealPeriod || 'lunch'
    modalDelta.value = -1
    modalReason.value = 'spill'
    modalRemark.value = ''
    modalOpen.value = true
  }

  async function submitAdjustment() {
    if (!adminAccessToken.value) return
    if (!modalBusinessDate.value) {
      showToast('缺少业务日', 'error')
      return
    }
    const delta = Number(modalDelta.value)
    if (!Number.isFinite(delta) || delta === 0) {
      showToast('份数须为非零整数（负数减库存）', 'error')
      return
    }
    if (modalReason.value === 'other' && !String(modalRemark.value || '').trim()) {
      showToast('选择「其他」时请填写备注', 'error')
      return
    }
    submitting.value = true
    try {
      await apiJson(
        '/api/admin/day-stock/adjustments',
        {
          method: 'POST',
          body: JSON.stringify({
            business_date: modalBusinessDate.value,
            meal_period: modalMealPeriod.value,
            delta: Math.trunc(delta),
            reason_code: modalReason.value,
            remark: modalRemark.value || null,
          }),
        },
        { auth: true },
      )
      showToast('损耗已记录', 'success')
      modalOpen.value = false
      opts.onSuccess?.()
    } catch (e) {
      showToast(e instanceof Error ? e.message : '提交失败', 'error')
    } finally {
      submitting.value = false
    }
  }

  return {
    modalOpen,
    modalMealPeriod,
    modalBusinessDate,
    modalDelta,
    modalReason,
    modalRemark,
    submitting,
    openAdjustModal,
    submitAdjustment,
  }
}
