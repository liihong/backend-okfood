<script setup>
defineOptions({ name: 'PrepMealPane' })
import { formatGrossAmount, formatNetAmount, formatPerPortion, formatYield } from '../../api/prepMenu.js'

defineProps({
  meal: { type: Object, required: true },
  portionDraft: { type: Function, required: true },
})
const emit = defineEmits(['portion', 'configure'])
</script>

<template>
  <div>
    <section v-for="day in meal.days" :key="day.slot" class="prep-day">
      <header class="prep-day-head">
        <div>
          <strong>{{ day.weekday }}</strong>
          <span class="prep-day-date">{{ day.menu_date }}</span>
          <span class="prep-day-name">{{ day.dish_name || '未排菜' }}</span>
          <el-tag v-if="day.portions_source === 'override'" size="small" type="warning">本次预估</el-tag>
        </div>
        <label v-if="day.dish_id" class="prep-portion">
          份数
          <el-input
            :model-value="portionDraft(meal.meal_period, day.slot)"
            placeholder="预估份数"
            style="width: 120px"
            @update:model-value="(value) => emit('portion', meal.meal_period, day.slot, value)"
          />
        </label>
      </header>
      <p v-if="day.status === 'no_dish'" class="prep-muted">这一天还没有排菜。</p>
      <p v-if="day.status === 'no_portions'" class="prep-warn">未填份数，无法估算。</p>
      <p v-if="day.dish_id && !day.has_sop" class="prep-warn">
        尚未配置配菜。
        <el-button link type="primary" @click="emit('configure', day.dish_id)">去配置</el-button>
      </p>
      <el-table v-if="day.status === 'ok'" :data="day.lines" size="small" empty-text="没有配菜">
        <el-table-column prop="name" label="配菜" min-width="120" />
        <el-table-column label="单份毛菜" min-width="100">
          <template #default="{ row }">{{ formatPerPortion(row.per_portion_gross, row.unit) }}</template>
        </el-table-column>
        <el-table-column label="出成率" width="90">
          <template #default="{ row }">{{ formatYield(row.yield_rate, row.unit) }}</template>
        </el-table-column>
        <el-table-column label="毛菜" min-width="100">
          <template #default="{ row }">{{ formatGrossAmount(row) }}</template>
        </el-table-column>
        <el-table-column label="净菜" min-width="100">
          <template #default="{ row }">{{ formatNetAmount(row) }}</template>
        </el-table-column>
      </el-table>
    </section>
    <section v-if="meal.ingredient_summary.length" class="prep-day">
      <h4 class="prep-sum-title">本餐段合计</h4>
      <el-table :data="meal.ingredient_summary" size="small">
        <el-table-column prop="name" label="食材" min-width="140" />
        <el-table-column label="毛菜" min-width="120">
          <template #default="{ row }">{{ formatGrossAmount(row) }}</template>
        </el-table-column>
        <el-table-column label="净菜" min-width="120">
          <template #default="{ row }">{{ formatNetAmount(row) }}</template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.prep-day {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 12px;
}
.prep-day-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}
.prep-day-date,
.prep-day-name {
  margin-left: 8px;
  color: #475569;
}
.prep-day-name {
  font-weight: 700;
  color: #0f172a;
}
.prep-portion {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #334155;
  font-size: 13px;
  flex-shrink: 0;
}
.prep-muted {
  margin: 0;
  color: #94a3b8;
  font-size: 13px;
}
.prep-warn {
  margin: 0 0 8px;
  color: #b45309;
  font-size: 13px;
}
.prep-sum-title {
  margin: 0 0 8px;
  font-size: 14px;
}
@media (max-width: 800px) {
  .prep-day-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
