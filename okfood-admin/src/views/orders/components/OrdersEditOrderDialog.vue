<script setup>
import MemberDeliveryMapPicker from '../../../components/MemberDeliveryMapPicker.vue'
import { formatMemberAddressOption } from '../utils/orderFormatters.js'
import { useOrdersManageInject } from '../composables/useOrdersManageInject.js'

const {
  editOpen,
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
  onEditAddrMapWarn,
  onEditDialogClosed,
} = useOrdersManageInject()
</script>

<template>
  <el-dialog
    v-model="editOpen"
    :title="'修改订单 · 配送/自提与收货地址'"
    width="920px"
    class="orders-edit-order-dialog"
    destroy-on-close
    align-center
    :close-on-click-modal="!editSaving"
    :close-on-press-escape="!editSaving"
    @closed="onEditDialogClosed"
  >
    <template v-if="editOrder">
      <p class="orders-edit-hint">
        订单 #{{ editOrder.id }}
        <template v-if="editOrder.product_title"> · {{ editOrder.product_title }}</template>
        · {{ editDialogMemberDisplayName }}
        {{ (editOrder.member_phone || '').trim() }}
      </p>
      <div class="orders-edit-field">
        <span class="orders-edit-label">履约方式</span>
        <el-radio-group v-model="editForm.store_pickup">
          <el-radio :value="false">配送到家</el-radio>
          <el-radio :value="true">门店自提</el-radio>
        </el-radio-group>
      </div>
      <div v-if="!editForm.store_pickup" class="orders-edit-field">
        <span class="orders-edit-label">收货地址</span>
        <el-select
          v-model="editForm.member_address_id"
          filterable
          placeholder="选择会员配送地址（可切换该会员名下其它地址）"
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
        <p v-if="!editAddrLoading && !editMemberAddresses.length" class="orders-edit-tip">
          该会员暂无配送地址，请先在会员档案「地址」中新建后再来绑定订单。
        </p>
      </div>

      <template v-if="!editForm.store_pickup && editAddrDraft">
        <div class="orders-edit-addr-sep" />
        <p class="orders-edit-subhint">
          以下与「会员档案 · 地址管理」一致：可修正收件人、电话、地图选点与门牌；
          <strong>保存时先写入会员地址</strong>（全店订单凡引用本条地址一并更新），再更新本订单绑定与配送摘要。
        </p>
        <div class="orders-edit-first-row">
          <el-space wrap :size="8" alignment="center">
            <span class="orders-edit-k">会员</span>
            <el-text truncated class="orders-edit-inline-name">{{ editDialogMemberDisplayName }}</el-text>
            <el-text type="info" truncated>{{ (editOrder.member_phone || '').trim() }}</el-text>
            <el-divider direction="vertical" />
            <span class="orders-edit-k">经纬度 GCJ-02</span>
            <el-tag size="small" type="info" effect="plain">{{ editHeadCoordDisplay }}</el-tag>
          </el-space>
        </div>
        <el-form label-position="top" size="small" class="orders-edit-addr-form">
          <el-row :gutter="12">
            <el-col :xs="24" :sm="12">
              <el-form-item label="收件人">
                <el-input
                  v-model="editAddrDraft.contact_name"
                  maxlength="100"
                  clearable
                  placeholder="收件人姓名"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="12">
              <el-form-item label="联系电话">
                <el-input v-model="editAddrDraft.contact_phone" maxlength="20" clearable placeholder="手机号" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="地图选点（GCJ-02）">
            <div class="orders-edit-map-wrap">
              <MemberDeliveryMapPicker
                :key="'orders-edit-ma-' + editAddrDraft.id"
                v-model:lng-str="editAddrDraft.lngStr"
                v-model:lat-str="editAddrDraft.latStr"
                v-model:map-location-text="editAddrDraft.map_location_text"
                :search-input-id="'orders-edit-amap-' + editAddrDraft.id"
                @warn="onEditAddrMapWarn"
              />
            </div>
          </el-form-item>
          <el-row :gutter="12">
            <el-col :xs="24" :sm="14">
              <el-form-item label="收货位置主文案（map_location_text）">
                <el-input
                  v-model="editAddrDraft.map_location_text"
                  type="textarea"
                  readonly
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  maxlength="500"
                  show-word-limit
                  placeholder="地图选点后自动填入，可与门牌拼成完整地址"
                />
              </el-form-item>
            </el-col>
            <el-col :xs="24" :sm="10">
              <el-form-item label="门牌（楼栋 / 单元 / 室号）">
                <el-input
                  v-model="editAddrDraft.door_detail"
                  type="textarea"
                  :autosize="{ minRows: 2, maxRows: 3 }"
                  maxlength="500"
                  placeholder="例如：3 号楼 1202"
                />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="地址备注">
            <el-input
              v-model="editAddrDraft.remarks"
              type="textarea"
              :autosize="{ minRows: 1, maxRows: 3 }"
              maxlength="500"
              placeholder="忌口等，可留空"
            />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="editAddrAlsoDefault">同时将本条设为该会员默认配送地址</el-checkbox>
          </el-form-item>
        </el-form>
      </template>

      <p v-else-if="editForm.store_pickup" class="orders-edit-tip orders-edit-tip--muted">
        门店自提无需维护收货地址。
      </p>
    </template>
    <template #footer>
      <el-button :disabled="editSaving" @click="editOpen = false">取消</el-button>
      <el-button type="primary" :loading="editSaving" @click="submitEditOrder">保存</el-button>
    </template>
  </el-dialog>
</template>
