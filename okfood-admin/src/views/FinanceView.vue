<script setup>
import { reactive, ref } from 'vue'
import { DollarSign, History } from 'lucide-vue-next'

const financeStats = reactive({
  todayRevenue: '—',
  monthRevenue: '—',
  targetPercent: 0,
})

const transactions = ref([])
</script>

<template>
  <section class="tab-content animate-up">
    <div class="finance-grid">
      <div class="finance-card primary">
        <DollarSign class="bg-icon" :size="80" />
        <p class="f-label">今日成交成交 / TODAY</p>
        <div class="f-main">
          <span class="f-val">¥ {{ financeStats.todayRevenue }}</span>
        </div>
      </div>
      <div class="finance-card white">
        <p class="f-label-dark">本月累计 / MONTHLY</p>
        <p class="f-val-dark">¥ {{ financeStats.monthRevenue }}</p>
        <div class="progress-wrap">
          <div class="progress-text">
            <span>目标进度</span><span>{{ financeStats.targetPercent }}%</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: financeStats.targetPercent + '%' }"></div>
          </div>
        </div>
      </div>
    </div>

    <div class="table-container table-container-finance">
      <div class="table-header">
        <div class="finance-section-head">
          <History :size="20" /> 最近交易流水记录
        </div>
      </div>
      <AdminTable variant="default" :data="transactions" row-key="id" empty-text="">
        <template #empty>
          <span class="members-loading">暂无流水；对接财务/支付查询接口后展示。</span>
        </template>
        <el-table-column prop="id" label="流水号" min-width="120" class-name="t-sub" />
        <el-table-column label="客户" min-width="120">
          <template #default="{ row: t }">
            <div class="t-name">{{ t.user }}</div>
          </template>
        </el-table-column>
        <el-table-column label="支付金额" min-width="100">
          <template #default="{ row: t }">
            <span class="font-black">¥ {{ t.amount }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="time" label="支付时间" min-width="140" class-name="t-sub" />
        <el-table-column label="状态" align="right" min-width="88" class-name="td-paid">
          <template #default>已支付</template>
        </el-table-column>
      </AdminTable>
    </div>
  </section>
</template>
