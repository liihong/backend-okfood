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
      <table class="data-table">
        <thead>
          <tr>
            <th>流水号</th>
            <th>客户</th>
            <th>支付金额</th>
            <th>支付时间</th>
            <th class="text-right">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!transactions.length">
            <td colspan="5" class="members-loading">暂无流水；对接财务/支付查询接口后展示。</td>
          </tr>
          <template v-else>
            <tr v-for="t in transactions" :key="t.id">
              <td class="t-sub">{{ t.id }}</td>
              <td>
                <div class="t-name">{{ t.user }}</div>
              </td>
              <td class="font-black">¥ {{ t.amount }}</td>
              <td class="t-sub">{{ t.time }}</td>
              <td class="text-right td-paid">已支付</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>
