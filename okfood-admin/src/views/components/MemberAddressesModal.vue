<script setup>
import { ref, watch, computed } from 'vue'
import { X, Plus } from 'lucide-vue-next'
import MemberDeliveryMapPicker from '../../components/MemberDeliveryMapPicker.vue'
import { apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  /** 列表行会员，需含 id / name / phone */
  member: { type: Object, default: null },
})

const emit = defineEmits(['saved'])

const addrList = ref([])
const addrLoading = ref(false)
const addrSaving = ref(false)
const addrDefaultSaving = ref(false)
/** 当前编辑行：含地图用字符串经纬度 */
const addrEdit = ref(null)
/** 当前选中的地址 id（列表高亮与表单联动） */
const addrSelectedId = ref(null)

const currentAddrRow = computed(() =>
  addrList.value.find((x) => Number(x.id) === Number(addrSelectedId.value)),
)

/** 右侧表单是否为「新建」（尚无地址 id） */
const isCreatingAddress = computed(() => Boolean(addrEdit.value) && addrEdit.value.id == null)

const canAddAddress = computed(() => addrList.value.length < 20)

function blankAddrEdit() {
  const m = props.member
  return {
    id: null,
    contact_name: (m?.name || '').trim(),
    contact_phone: (m?.phone || '').trim(),
    map_location_text: '',
    door_detail: '',
    remarks: '',
    lngStr: '',
    latStr: '',
  }
}

function startNewAddress() {
  if (!canAddAddress.value) {
    showToast('每位会员最多保存 20 条地址', 'error')
    return
  }
  addrSelectedId.value = null
  addrEdit.value = blankAddrEdit()
}

function pickAddrEdit(a) {
  const lng = a.location?.lng
  const lat = a.location?.lat
  addrSelectedId.value = Number(a.id)
  addrEdit.value = {
    id: a.id,
    contact_name: a.contact_name || '',
    contact_phone: a.contact_phone || '',
    map_location_text: a.map_location_text || '',
    door_detail: a.door_detail || '',
    remarks: a.remarks || '',
    lngStr: lng != null && lng !== '' ? String(lng) : '',
    latStr: lat != null && lat !== '' ? String(lat) : '',
  }
}

const addrHeadCoordDisplay = computed(() => {
  if (!addrEdit.value) return '—'
  const a = String(addrEdit.value.lngStr ?? '').trim()
  const b = String(addrEdit.value.latStr ?? '').trim()
  if (a && b) return `${a}, ${b}`
  return '未选点'
})

/**
 * @param {number | null} [preferId] 刷新后优先选中该地址（保存/设默认后保持编辑对象）
 */
async function loadAddressesForMember(preferId = null) {
  const m = props.member
  if (!open.value || !m?.id) return
  addrList.value = []
  addrEdit.value = null
  addrSelectedId.value = null
  addrLoading.value = true
  try {
    const list = await apiJson(`/api/admin/users/${Number(m.id)}/addresses`, {}, { auth: true })
    addrList.value = Array.isArray(list) ? list : []
    const pref =
      preferId != null ? addrList.value.find((x) => Number(x.id) === Number(preferId)) : null
    const def = pref || addrList.value.find((x) => x.is_default) || addrList.value[0]
    if (def) pickAddrEdit(def)
    else startNewAddress()
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载地址失败', 'error')
    open.value = false
  } finally {
    addrLoading.value = false
  }
}

watch([open, () => props.member?.id], ([isOpen, mid]) => {
  if (!isOpen) {
    addrList.value = []
    addrEdit.value = null
    addrSelectedId.value = null
    return
  }
  if (mid != null) void loadAddressesForMember(null)
})

function close() {
  open.value = false
}

function onAddrMapWarn(msg) {
  const s = typeof msg === 'string' && msg.trim() ? msg.trim() : '地图提示'
  showToast(s, 'error')
}

async function saveMemberAddress() {
  const m = props.member
  const ed = addrEdit.value
  if (!m?.id || !ed) return
  const name = (ed.contact_name || '').trim()
  const phone = (ed.contact_phone || '').trim()
  const mapT = (ed.map_location_text || '').trim()
  const doorT = (ed.door_detail || '').trim()
  if (!name) {
    showToast('请填写收件人', 'error')
    return
  }
  if (!phone) {
    showToast('请填写联系电话', 'error')
    return
  }
  const lng = Number(String(ed.lngStr ?? '').trim())
  const lat = Number(String(ed.latStr ?? '').trim())
  const hasCoords = Number.isFinite(lng) && Number.isFinite(lat) && !(lng === 0 && lat === 0)
  if (!hasCoords) {
    showToast('请使用地图搜索或点击地图选点', 'error')
    return
  }
  if (isCreatingAddress.value) {
    if (!mapT) {
      showToast('请填写收货位置主文案（地图选点后自动填入）', 'error')
      return
    }
  } else if (!ed.id) {
    return
  }

  addrSaving.value = true
  try {
    const payload = {
      contact_name: name,
      contact_phone: phone,
      map_location_text: mapT || null,
      door_detail: doorT || null,
      remarks: (ed.remarks || '').trim() || null,
    }
    if (hasCoords) {
      payload.location = { lng, lat }
    }
    if (isCreatingAddress.value) {
      payload.map_location_text = mapT
      payload.is_default = addrList.value.length === 0
      const created = await apiJson(
        `/api/admin/users/${Number(m.id)}/addresses`,
        { method: 'POST', body: JSON.stringify(payload) },
        { auth: true },
      )
      showToast('地址已创建', 'success')
      emit('saved')
      const newId = created?.id != null ? Number(created.id) : null
      await loadAddressesForMember(newId)
      return
    }
    const savedId = Number(ed.id)
    await apiJson(
      `/api/admin/users/${Number(m.id)}/addresses/${savedId}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
      { auth: true },
    )
    showToast('保存成功', 'success')
    emit('saved')
    await loadAddressesForMember(savedId)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : isCreatingAddress.value ? '创建失败' : '保存失败', 'error')
  } finally {
    addrSaving.value = false
  }
}

async function makeCurrentAddressDefault() {
  const m = props.member
  const ed = addrEdit.value
  if (!m?.id || !ed?.id) return
  if (currentAddrRow.value?.is_default) return
  const aid = Number(ed.id)
  addrDefaultSaving.value = true
  try {
    await apiJson(
      `/api/admin/users/${Number(m.id)}/addresses/${aid}`,
      { method: 'PATCH', body: JSON.stringify({ is_default: true }) },
      { auth: true },
    )
    showToast('已设为默认配送地址', 'success')
    emit('saved')
    await loadAddressesForMember(aid)
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '设置默认失败', 'error')
  } finally {
    addrDefaultSaving.value = false
  }
}
</script>

<template>
  <div
    v-if="open"
    class="modal-overlay"
    v-esc-close="close"
    @click.self="close()"
  >
    <div class="modal-card modal-card--member-edit members-addr-modal-card">
      <div class="modal-header">
        <div class="header-info">
          <h3>地址管理</h3>
          <p>MEMBER ADDRESSES</p>
        </div>
        <button type="button" class="close-btn" @click="close()">
          <X :size="20" />
        </button>
      </div>
      <div class="modal-form members-addr-modal-body">
        <div v-if="addrLoading">
          <el-skeleton animated :rows="5" />
        </div>
        <div v-else class="members-addr-layout">
            <aside class="members-addr-list-pane" aria-label="会员全部地址">
              <div class="members-addr-list-head">
                <p class="members-addr-list-hint">
                  共 {{ addrList.length }} 条 · 点击条目在右侧编辑
                </p>
                <el-button
                  type="primary"
                  link
                  :disabled="!canAddAddress || addrSaving || addrDefaultSaving"
                  @click="startNewAddress"
                >
                  <Plus :size="14" :stroke-width="2.5" />
                  新增地址
                </el-button>
              </div>
              <div class="members-addr-list-scroll">
                <div
                  v-if="isCreatingAddress"
                  class="members-addr-list-item members-addr-list-item--active members-addr-list-item--draft"
                >
                  <div class="members-addr-list-item-top">
                    <el-tag size="small" type="warning" effect="plain">新建</el-tag>
                    <span class="members-addr-list-item-name">未保存</span>
                  </div>
                  <div class="members-addr-list-item-addr">在右侧填写后点击「创建地址」</div>
                </div>
                <div
                  v-for="a in addrList"
                  :key="a.id"
                  role="button"
                  tabindex="0"
                  class="members-addr-list-item"
                  :class="{
                    'members-addr-list-item--active': !isCreatingAddress && addrSelectedId === Number(a.id),
                  }"
                  @click="pickAddrEdit(a)"
                  @keydown.enter.prevent="pickAddrEdit(a)"
                >
                  <div class="members-addr-list-item-top">
                    <el-tag v-if="a.is_default" size="small" type="success" effect="plain">默认</el-tag>
                    <span class="members-addr-list-item-name">{{ a.contact_name || '—' }}</span>
                  </div>
                  <div class="members-addr-list-item-phone">{{ a.contact_phone || '—' }}</div>
                  <div class="members-addr-list-item-addr" :title="a.full_address || ''">
                    {{ a.full_address || '—' }}
                  </div>
                  <div class="members-addr-list-item-area">{{ a.area || '—' }}</div>
                </div>
                <p v-if="!addrList.length && !isCreatingAddress" class="members-addr-list-empty">
                  暂无配送地址
                </p>
              </div>
            </aside>

            <div class="members-addr-edit-pane">
              <div v-if="member && addrEdit" class="members-addr-first-row">
                <el-space wrap :size="8" alignment="center">
                  <span class="members-addr-k">会员</span>
                  <el-text truncated class="members-addr-name">{{ member.name || '—' }}</el-text>
                  <el-text type="info" truncated>{{ member.phone || '' }}</el-text>
                  <el-divider direction="vertical" class="members-addr-divider" />
                  <span class="members-addr-k">经纬度</span>
                  <el-tag size="small" type="info" effect="plain" class="members-addr-coord-tag">{{
                    addrHeadCoordDisplay
                  }}</el-tag>
                </el-space>
              </div>

              <el-form
                v-if="addrEdit"
                label-position="top"
                size="small"
                class="members-addr-el-form"
                @submit.prevent="saveMemberAddress"
              >
                <el-row :gutter="12">
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="收件人">
                      <el-input v-model="addrEdit.contact_name" maxlength="100" clearable placeholder="收件人姓名" />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="12">
                    <el-form-item label="联系电话">
                      <el-input v-model="addrEdit.contact_phone" maxlength="20" clearable placeholder="手机号" />
                    </el-form-item>
                  </el-col>
                </el-row>

                <el-form-item label="地图选点（GCJ-02）" class="members-addr-map-form-item">
                  <div class="members-addr-map-wrap">
                    <MemberDeliveryMapPicker
                      :key="'ma-' + (addrEdit.id != null ? addrEdit.id : 'new')"
                      v-model:lng-str="addrEdit.lngStr"
                      v-model:lat-str="addrEdit.latStr"
                      v-model:map-location-text="addrEdit.map_location_text"
                      :search-input-id="'members-addr-amap-' + (addrEdit.id != null ? addrEdit.id : 'new')"
                      @warn="onAddrMapWarn"
                    />
                  </div>
                </el-form-item>

                <el-row :gutter="12">
                  <el-col :xs="24" :sm="14">
                    <el-form-item label="收货位置主文案（map_location_text）">
                      <el-input
                        v-model="addrEdit.map_location_text"
                        type="textarea"
                        readonly
                        :autosize="{ minRows: 2, maxRows: 4 }"
                        maxlength="500"
                        show-word-limit
                        placeholder="地图选点自动填入；可与门牌拼接为完整收货地址"
                      />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="10">
                    <el-form-item label="门牌（楼栋 / 单元 / 室号）">
                      <el-input
                        v-model="addrEdit.door_detail"
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
                    v-model="addrEdit.remarks"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 3 }"
                    maxlength="500"
                    placeholder="忌口等，可留空"
                  />
                </el-form-item>

                <el-form-item class="members-addr-actions">
                  <div class="members-addr-actions-inner">
                    <div class="members-addr-actions-left">
                      <el-tag
                        v-if="isCreatingAddress && addrList.length === 0"
                        size="small"
                        type="success"
                        effect="plain"
                      >
                        保存后将设为默认地址
                      </el-tag>
                      <el-button
                        v-else-if="currentAddrRow && !currentAddrRow.is_default"
                        type="warning"
                        plain
                        :loading="addrDefaultSaving"
                        :disabled="addrSaving"
                        @click.prevent="makeCurrentAddressDefault"
                      >
                        设为默认配送地址
                      </el-button>
                      <el-tag
                        v-else-if="currentAddrRow && currentAddrRow.is_default"
                        size="small"
                        type="success"
                        effect="plain"
                      >
                        当前为默认地址
                      </el-tag>
                    </div>
                    <el-button type="primary" :loading="addrSaving" :disabled="addrDefaultSaving" native-type="submit">
                      {{ isCreatingAddress ? '创建地址' : '保存地址' }}
                    </el-button>
                  </div>
                </el-form-item>
              </el-form>
            </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.members-addr-modal-card {
  max-width: min(920px, 98vw);
}

.members-addr-modal-body {
  padding: 1rem 1.25rem 1.35rem;
  max-height: min(82vh, 720px);
  overflow: auto;
}

.members-addr-layout {
  display: grid;
  grid-template-columns: minmax(200px, 268px) 1fr;
  gap: 14px;
  align-items: start;
}

@media (max-width: 720px) {
  .members-addr-layout {
    grid-template-columns: 1fr;
  }
}

.members-addr-list-pane {
  position: sticky;
  top: 0;
}

.members-addr-list-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
}

.members-addr-list-hint {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.members-addr-list-empty {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.members-addr-list-item--draft {
  cursor: default;
  border-style: dashed;
}

.members-addr-list-scroll {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: min(56vh, 520px);
  overflow: auto;
  padding-right: 2px;
}

.members-addr-list-item {
  text-align: left;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 10px 8px;
  cursor: pointer;
  background: var(--el-fill-color-blank);
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}

.members-addr-list-item:hover {
  border-color: var(--el-color-primary-light-5);
}

.members-addr-list-item--active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.members-addr-list-item-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.members-addr-list-item-name {
  font-weight: 600;
  font-size: 13px;
}

.members-addr-list-item-phone {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.members-addr-list-item-addr {
  font-size: 12px;
  line-height: 1.45;
  color: var(--el-text-color-regular);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.members-addr-list-item-area {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
}

.members-addr-edit-pane {
  min-width: 0;
}

.members-addr-first-row {
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.members-addr-k {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.members-addr-name {
  max-width: 7rem;
}

.members-addr-divider {
  margin: 0 2px !important;
  height: 14px !important;
}

.members-addr-coord-tag {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.members-addr-pca-line {
  max-width: min(200px, 36vw);
  vertical-align: middle;
}

.members-addr-el-form {
  margin-top: 2px;
}

.members-addr-el-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.members-addr-map-form-item :deep(.el-form-item__content) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.members-addr-tip {
  padding: 6px 10px;
}

.members-addr-tip :deep(.el-alert__title) {
  font-size: 12px;
  line-height: 1.45;
}

.members-addr-tip-text {
  font-size: 12px;
}

.members-addr-map-wrap {
  width: 100%;
}

.members-addr-map-wrap :deep(.mdmp-map) {
  height: min(188px, 30vh);
  min-height: 150px;
}

.members-addr-actions {
  margin-bottom: 0 !important;
}

.members-addr-actions-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
}

.members-addr-actions-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-height: 32px;
}

.members-addr-actions :deep(.el-form-item__content) {
  display: block;
}
</style>
