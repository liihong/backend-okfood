<script setup>
import { DAY_STOCK_REASON_OPTIONS } from '../../composables/useDayStockAdjustments.js'

defineProps({
  open: { type: Boolean, default: false },
  mealPeriod: { type: String, default: 'lunch' },
  businessDate: { type: String, default: '' },
  delta: { type: Number, default: -1 },
  reason: { type: String, default: 'spill' },
  remark: { type: String, default: '' },
  submitting: { type: Boolean, default: false },
})

defineEmits(['update:open', 'update:delta', 'update:reason', 'update:remark', 'submit'])
</script>

<template>
  <div v-if="open" class="dsa-backdrop" @click.self="$emit('update:open', false)">
    <div class="dsa-dialog" role="dialog" aria-labelledby="dsa-title">
      <h3 id="dsa-title" class="dsa-title">
        报损耗 · {{ mealPeriod === 'dinner' ? '晚餐' : '午餐' }} · {{ businessDate || '—' }}
      </h3>
      <p class="dsa-hint">剩余库存不可直接修改，请通过流水扣减并选择原因。</p>
      <label class="dsa-field">
        <span>扣减份数（负数）</span>
        <input
          type="number"
          max="-1"
          inputmode="numeric"
          :value="delta"
          @input="$emit('update:delta', Number($event.target.value))"
        />
      </label>
      <label class="dsa-field">
        <span>原因</span>
        <select :value="reason" @change="$emit('update:reason', $event.target.value)">
          <option v-for="o in DAY_STOCK_REASON_OPTIONS" :key="o.value" :value="o.value">
            {{ o.label }}
          </option>
        </select>
      </label>
      <label class="dsa-field">
        <span>备注（选「其他」必填）</span>
        <input
          type="text"
          maxlength="500"
          :value="remark"
          @input="$emit('update:remark', $event.target.value)"
        />
      </label>
      <div class="dsa-actions">
        <button type="button" class="dsa-btn dsa-btn--ghost" @click="$emit('update:open', false)">取消</button>
        <button type="button" class="dsa-btn dsa-btn--primary" :disabled="submitting" @click="$emit('submit')">
          {{ submitting ? '提交中…' : '确认记录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dsa-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.dsa-dialog {
  width: min(420px, 100%);
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 20px 50px rgba(15, 23, 42, 0.2);
}
.dsa-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 700;
}
.dsa-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #64748b;
}
.dsa-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 13px;
}
.dsa-field input,
.dsa-field select {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
}
.dsa-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
.dsa-btn {
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 14px;
  cursor: pointer;
}
.dsa-btn--ghost {
  border: 1px solid #e2e8f0;
  background: #fff;
}
.dsa-btn--primary {
  border: none;
  background: #059669;
  color: #fff;
}
.dsa-btn--primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
