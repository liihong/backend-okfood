<script setup>
import { ref, watch, computed, nextTick } from 'vue'
import { ElMessageBox } from 'element-plus'
import { apiJson, adminAccessToken, adminStoreBranding, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { useStorePrint } from '../../composables/useStorePrint.js'
import { buildGiftCouponLabelItems } from '../../utils/print/giftCouponLabelAdapter.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  deliveryDate: { type: String, default: '' },
  sheetView: { type: String, default: 'lunch' },
})
const emit = defineEmits(['update:visible'])

const { submitPrintJob, resolveScene, printing } = useStorePrint()
const loading = ref(false)
const redeeming = ref(false)
const reprinting = ref(false)
const rows = ref([])
const tableRef = ref(null)

const dialogVisible = computed({
  get: () => props.visible,
  set: (v) => emit('update:visible', v),
})

const bizDay = computed(
  () => String(props.deliveryDate || '').trim(),
)

function storeQuery() {
  return new URLSearchParams({
    delivery_date: bizDay.value,
    sheet_view: props.sheetView || 'lunch',
  }).toString()
}

async function loadList() {
  if (!adminAccessToken.value || !bizDay.value) return
  loading.value = true
  try {
    const data = await apiJson(`/api/admin/gift-coupons/today-deliverable?${storeQuery()}`, {}, { auth: true })
    rows.value = Array.isArray(data?.items) ? data.items : []
    await nextTick()
    onTableReady()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '加载失败', 'error')
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (v) => {
    if (v) void loadList()
  },
)

function selectedRows() {
  return tableRef.value?.getSelectionRows?.() || []
}

async function printRows(items, { afterRedeemMsg } = {}) {
  const cfg = await resolveScene('delivery_sheet')
  if (!cfg?.configured) {
    showToast('请先在系统管理 → 打印设置 → 配送标签 中配置打印机', 'error')
    return false
  }
  const storeName = String(adminStoreBranding.value?.store_name || '').trim() || 'OK饭'
  const printItems = buildGiftCouponLabelItems(items, bizDay.value, storeName)
  const result = await submitPrintJob('delivery_sheet', printItems, { silentToast: true })
  if (!result) {
    showToast(
      afterRedeemMsg
        ? `${afterRedeemMsg}打印失败，请用「补打今日已核销」再出标签`
        : '打印失败',
      'error',
    )
    return false
  }
  showToast(`已打印礼品券标签 ${printItems.length} 张`, 'success')
  return true
}

async function confirmPrintAndRedeem() {
  const picked = selectedRows()
  if (!picked.length) {
    showToast('请勾选今日要配送礼品券的会员', 'error')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将核销并打印 ${picked.length} 人的礼品券标签（未勾选、当天不在大表的人不会核销）。确定？`,
      '打印并核销礼品券',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  redeeming.value = true
  try {
    const data = await apiJson(
      `/api/admin/gift-coupons/redeem`,
      {
        method: 'POST',
        body: JSON.stringify({
          delivery_date: bizDay.value,
          sheet_view: props.sheetView || 'lunch',
          entitlement_ids: picked.map((r) => r.entitlement_id),
        }),
      },
      { auth: true },
    )
    const printList = Array.isArray(data?.items) ? data.items : picked
    const n = Number(data?.redeemed_count) || 0
    const already = Number(data?.already_redeemed_count) || 0
    const skipped = Number(data?.skipped_not_on_sheet) || 0
    const msg = `已核销 ${n} 人` + (already ? `，原已核销 ${already}` : '') + (skipped ? `，不在大表跳过 ${skipped}` : '')
    await printRows(printList, { afterRedeemMsg: `${msg}。` })
    await loadList()
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '核销失败', 'error')
  } finally {
    redeeming.value = false
  }
}

async function reprintToday() {
  reprinting.value = true
  try {
    const data = await apiJson(`/api/admin/gift-coupons/today-redeemed?${storeQuery()}`, {}, { auth: true })
    const items = Array.isArray(data?.items) ? data.items : []
    if (!items.length) {
      showToast('今日还没有已核销的礼品券', 'error')
      return
    }
    await printRows(items)
  } catch (e) {
    if (handleAdminLogout(e)) return
    showToast(e instanceof Error ? e.message : '补打失败', 'error')
  } finally {
    reprinting.value = false
  }
}

function onTableReady() {
  const tb = tableRef.value
  if (!tb || !rows.value.length) return
  for (const row of rows.value) {
    tb.toggleRowSelection(row, true)
  }
}
</script>

<template>
  <el-dialog v-model="dialogVisible" title="今日可送礼品券" width="860px" destroy-on-close>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      :title="`业务日 ${bizDay}。仅列出当天配送大表上、尚未核销的持券会员。勾选后打印厨房标签并自动核销；未上表的人不会核销。`"
      class="gift-today-alert"
    />
    <el-table
      ref="tableRef"
      v-loading="loading"
      :data="rows"
      stripe
      max-height="420"
      empty-text="今日大表没有可送礼品券的会员"
      @row-click="(row) => tableRef?.toggleRowSelection?.(row)"
    >
      <el-table-column type="selection" width="48" />
      <el-table-column prop="name" label="姓名" min-width="90" />
      <el-table-column prop="phone" label="手机" min-width="120" />
      <el-table-column prop="sheet_label" label="礼品" width="110" />
      <el-table-column prop="campaign_name" label="活动" min-width="140" />
      <el-table-column prop="area" label="片区" width="100" />
      <el-table-column prop="address_line" label="地址" min-width="180" show-overflow-tooltip />
    </el-table>
    <template #footer>
      <el-button :loading="reprinting || printing" @click="reprintToday">补打今日已核销</el-button>
      <el-button @click="dialogVisible = false">关闭</el-button>
      <el-button
        type="primary"
        :loading="redeeming || printing"
        :disabled="!rows.length"
        @click="confirmPrintAndRedeem"
      >
        打印标签并核销勾选
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.gift-today-alert {
  margin-bottom: 12px;
}
</style>
