<script setup>
import MemberDeliveryMapPicker from '../../../components/MemberDeliveryMapPicker.vue'
import { formatMemberAddressOption } from '../utils/orderFormatters.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  editOpen,
  editKind,
  editOrder,
  editSaving,
  editAddrLoading,
  editMemberAddresses,
  editAddrDraft,
  editAddrAlsoDefault,
  editForm,
  editDialogMemberDisplayName,
  editHeadCoordDisplay,
  submitEditOrder,
  startNewRetailAddress,
  useExistingRetailAddress,
  onEditAddrMapWarn,
  onEditDialogClosed,
} = useOrdersManageInject()
</script>

<template>
  <el-dialog
    v-model="editOpen"
    width="820px"
    class="orders-edit-order-dialog"
    destroy-on-close
    align-center
    append-to-body
    :close-on-click-modal="!editSaving"
    :close-on-press-escape="!editSaving"
    @closed="onEditDialogClosed"
  >
    <template #header>
      <div class="orders-edit-head">
        <strong>修改订单</strong>
        <span v-if="editOrder">
          #{{ editOrder.id }} · {{ editDialogMemberDisplayName }}
          {{ (editOrder.member_phone || '').trim() }}
        </span>
      </div>
    </template>

    <el-form
      v-if="editOrder"
      v-loading="editAddrLoading"
      element-loading-text="加载地址"
      label-position="top"
      size="small"
      class="orders-edit-form"
    >
      <div class="orders-edit-body" :class="{ 'is-pickup': editForm.store_pickup }">
        <section class="orders-edit-card orders-edit-card--main">
          <el-form-item label="履约">
            <el-radio-group v-model="editForm.store_pickup">
              <el-radio :value="false">配送到家</el-radio>
              <el-radio :value="true">门店自提</el-radio>
            </el-radio-group>
          </el-form-item>

          <template v-if="!editForm.store_pickup">
            <div class="orders-edit-addr-toolbar">
              <span class="orders-edit-k">收货地址</span>
              <el-button
                v-if="editKind === 'retail' && !(editAddrDraft && editAddrDraft.id == null)"
                type="primary"
                link
                @click="startNewRetailAddress"
              >
                登记新地址
              </el-button>
              <el-button
                v-else-if="editKind === 'retail' && editMemberAddresses.length"
                link
                @click="useExistingRetailAddress"
              >
                选用已有地址
              </el-button>
            </div>
            <el-select
              v-if="editMemberAddresses.length && !(editKind === 'retail' && editAddrDraft && editAddrDraft.id == null)"
              v-model="editForm.member_address_id"
              filterable
              :placeholder="editKind === 'retail' ? '选择已有商城地址' : '选择配送地址'"
              class="orders-edit-select"
              :loading="editAddrLoading"
            >
              <el-option
                v-for="a in editMemberAddresses"
                :key="a.id"
                :label="formatMemberAddressOption(a)"
                :value="Number(a.id)"
              />
            </el-select>
            <p v-if="editKind === 'retail' && editAddrDraft && editAddrDraft.id == null" class="orders-edit-tip">
              保存后只绑定本单，不改送餐地址。
            </p>
            <p v-else-if="!editAddrLoading && !editMemberAddresses.length" class="orders-edit-tip">
              {{ editKind === 'retail' ? '请用地图选点。' : '请先在会员档案新建配送地址。' }}
            </p>
          </template>

          <template v-if="!editForm.store_pickup && editAddrDraft">
            <div class="orders-edit-grid">
              <el-form-item label="收件人">
                <el-input
                  v-model="editAddrDraft.contact_name"
                  maxlength="100"
                  clearable
                  placeholder="姓名"
                />
              </el-form-item>
              <el-form-item label="联系电话">
                <el-input v-model="editAddrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
              </el-form-item>
            </div>
            <el-form-item label="地址备注">
              <el-input v-model="editAddrDraft.remarks" maxlength="500" clearable placeholder="可留空" />
            </el-form-item>
            <el-checkbox v-model="editAddrAlsoDefault" class="orders-edit-check">
              {{ editKind === 'retail' ? '设为默认商城地址' : '设为默认配送地址' }}
            </el-checkbox>
            <p class="orders-edit-coord">GCJ-02 {{ editHeadCoordDisplay }}</p>
            <p class="orders-edit-tip orders-edit-tip--muted">
              {{
                editKind === 'retail'
                  ? '不改会员送餐地址。'
                  : '保存会写回会员地址，引用本条的订单一起更新。'
              }}
            </p>
          </template>
          <p v-else-if="editForm.store_pickup" class="orders-edit-tip orders-edit-tip--muted">门店自提，无需地址</p>
        </section>

        <section v-if="!editForm.store_pickup && editAddrDraft" class="orders-edit-card orders-edit-card--map">
          <div class="orders-edit-map-wrap">
            <MemberDeliveryMapPicker
              :key="'orders-edit-ma-' + (editAddrDraft.id != null ? editAddrDraft.id : 'new')"
              v-model:lng-str="editAddrDraft.lngStr"
              v-model:lat-str="editAddrDraft.latStr"
              v-model:map-location-text="editAddrDraft.map_location_text"
              :search-input-id="'orders-edit-amap-' + (editAddrDraft.id != null ? editAddrDraft.id : 'new')"
              @warn="onEditAddrMapWarn"
            />
          </div>
          <el-form-item label="收货位置">
            <el-input
              v-model="editAddrDraft.map_location_text"
              readonly
              maxlength="500"
              placeholder="地图选点后自动填入"
            />
          </el-form-item>
          <el-form-item label="门牌">
            <el-input v-model="editAddrDraft.door_detail" maxlength="500" clearable placeholder="楼栋 / 室号" />
          </el-form-item>
        </section>
      </div>
    </el-form>

    <template #footer>
      <el-button round :disabled="editSaving" @click="editOpen = false">取消</el-button>
      <el-button type="primary" round :loading="editSaving" @click="submitEditOrder">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.orders-edit-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  min-width: 0;
}

.orders-edit-head strong {
  font-size: 16px;
  font-weight: 800;
  color: #1d1f21;
}

.orders-edit-head span {
  font-size: 13px;
  font-weight: 700;
  color: var(--el-color-primary-dark-2, #c75f48);
  white-space: nowrap;
}

.orders-edit-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr);
  gap: 10px;
  align-items: stretch;
}

.orders-edit-body.is-pickup {
  grid-template-columns: minmax(0, 420px);
}

.orders-edit-card {
  min-width: 0;
  padding: 12px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
}

.orders-edit-card--main {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
}

.orders-edit-card--main :deep(.el-form-item) {
  margin-bottom: 0;
}

.orders-edit-card--map {
  display: flex;
  flex-direction: column;
}

.orders-edit-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 10px;
}

.orders-edit-form :deep(.el-form-item) {
  margin-bottom: 8px;
}

.orders-edit-form :deep(.el-form-item__label) {
  margin-bottom: 2px;
  padding: 0;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.2;
  color: #64748b;
}

.orders-edit-form :deep(.el-select) {
  width: 100%;
}

.orders-edit-k {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.orders-edit-addr-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.orders-edit-select {
  width: 100%;
}

.orders-edit-map-wrap {
  height: 220px;
  margin-bottom: 8px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.orders-edit-map-wrap :deep(.mdmp) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.orders-edit-map-wrap :deep(.mdmp-search) {
  margin-bottom: 6px;
}

.orders-edit-map-wrap :deep(.mdmp-map) {
  flex: 1 1 auto;
  height: auto;
  min-height: 0;
}

.orders-edit-map-wrap :deep(.mdmp-search-btn) {
  height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--el-color-primary);
}

.orders-edit-coord {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
}

.orders-edit-check {
  height: auto;
  white-space: normal;
}

.orders-edit-tip {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.4;
  color: #c2410c;
}

.orders-edit-tip--muted {
  color: #64748b;
}

@media (max-width: 860px) {
  .orders-edit-body,
  .orders-edit-body.is-pickup {
    grid-template-columns: 1fr;
  }
}
</style>

<style>
.orders-edit-order-dialog.el-dialog,
.el-overlay .orders-edit-order-dialog.el-dialog {
  border-radius: 16px;
  padding: 0;
  background: #f7fafb;
  max-width: calc(100vw - 32px);
}

.orders-edit-order-dialog .el-dialog__header,
.el-overlay .orders-edit-order-dialog .el-dialog__header {
  margin: 0;
  padding: 14px 18px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 16px 16px 0 0;
}

.orders-edit-order-dialog .el-dialog__body,
.el-overlay .orders-edit-order-dialog .el-dialog__body {
  padding: 12px 14px;
  background: #f7fafb;
}

.orders-edit-order-dialog .el-dialog__footer,
.el-overlay .orders-edit-order-dialog .el-dialog__footer {
  padding: 10px 16px 14px;
  background: #fff;
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 0 0 16px 16px;
}
</style>
