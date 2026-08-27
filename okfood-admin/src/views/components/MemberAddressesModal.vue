<script setup>
import { ref, watch, computed } from 'vue'
import { X, Plus, ChevronLeft } from 'lucide-vue-next'
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
/** 手机端分步：列表 / 编辑（桌面端双栏始终同时显示） */
const mobilePane = ref('list')

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

/** 点击「新增」：准备空白表单，手机端切到编辑页 */
function onClickNewAddress() {
  startNewAddress()
  mobilePane.value = 'edit'
}

/** 点击列表条目：填入表单，手机端切到编辑页 */
function onSelectAddr(a) {
  pickAddrEdit(a)
  mobilePane.value = 'edit'
}

function backToAddrList() {
  mobilePane.value = 'list'
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
    mobilePane.value = 'list'
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
    class="modal-overlay members-addr-overlay"
    v-esc-close="close"
    @click.self="close()"
  >
    <div class="modal-card modal-card--member-edit members-addr-modal-card">
      <div class="modal-header members-addr-header">
        <div class="header-info">
          <h3>地址管理</h3>
          <p>MEMBER ADDRESSES</p>
        </div>
        <button type="button" class="close-btn members-addr-close" @click="close()">
          <X :size="18" />
        </button>
      </div>
      <div class="modal-form members-addr-modal-body">
        <div v-if="addrLoading">
          <el-skeleton animated :rows="4" />
        </div>
        <div
          v-else
          class="members-addr-layout"
          :class="{ 'is-mobile-edit': mobilePane === 'edit' }"
        >
            <aside class="members-addr-list-pane" aria-label="会员全部地址">
              <div class="members-addr-list-head">
                <p class="members-addr-list-hint">
                  共 {{ addrList.length }} 条
                  <span class="members-addr-list-hint-desk"> · 点击条目在右侧编辑</span>
                  <span class="members-addr-list-hint-mobi"> · 点击条目编辑</span>
                </p>
                <el-button
                  type="primary"
                  link
                  size="small"
                  :disabled="!canAddAddress || addrSaving || addrDefaultSaving"
                  @click="onClickNewAddress"
                >
                  <Plus :size="14" :stroke-width="2.5" />
                  新增
                </el-button>
              </div>
              <div class="members-addr-list-scroll">
                <div
                  v-if="isCreatingAddress"
                  class="members-addr-list-item members-addr-list-item--active members-addr-list-item--draft"
                  role="button"
                  tabindex="0"
                  @click="mobilePane = 'edit'"
                  @keydown.enter.prevent="mobilePane = 'edit'"
                >
                  <div class="members-addr-list-item-top">
                    <el-tag size="small" type="warning" effect="plain">新建</el-tag>
                    <span class="members-addr-list-item-name">未保存</span>
                  </div>
                  <div class="members-addr-list-item-addr">填写后点击「创建地址」</div>
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
                  @click="onSelectAddr(a)"
                  @keydown.enter.prevent="onSelectAddr(a)"
                >
                  <div class="members-addr-list-item-top">
                    <el-tag v-if="a.is_default" size="small" type="success" effect="plain">默认</el-tag>
                    <span class="members-addr-list-item-name">{{ a.contact_name || '—' }}</span>
                    <span class="members-addr-list-item-phone">{{ a.contact_phone || '—' }}</span>
                  </div>
                  <div class="members-addr-list-item-addr" :title="a.full_address || ''">
                    {{ a.full_address || '—' }}
                  </div>
                  <div v-if="a.area" class="members-addr-list-item-area">{{ a.area }}</div>
                </div>
                <p v-if="!addrList.length && !isCreatingAddress" class="members-addr-list-empty">
                  暂无配送地址
                </p>
              </div>
            </aside>

            <div class="members-addr-edit-pane">
              <div class="members-addr-edit-toolbar">
                <el-button text size="small" class="members-addr-back-btn" @click="backToAddrList">
                  <ChevronLeft :size="16" :stroke-width="2.25" />
                  返回列表
                </el-button>
              </div>
              <div v-if="member && addrEdit" class="members-addr-first-row">
                <el-space wrap :size="6" alignment="center">
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
                <el-row :gutter="8">
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

                <el-form-item label="地图选点" class="members-addr-map-form-item">
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

                <el-row :gutter="8">
                  <el-col :xs="24" :sm="14">
                    <el-form-item label="收货位置">
                      <el-input
                        v-model="addrEdit.map_location_text"
                        type="textarea"
                        readonly
                        :autosize="{ minRows: 1, maxRows: 3 }"
                        maxlength="500"
                        placeholder="地图选点后自动填入"
                      />
                    </el-form-item>
                  </el-col>
                  <el-col :xs="24" :sm="10">
                    <el-form-item label="门牌号">
                      <el-input
                        v-model="addrEdit.door_detail"
                        type="textarea"
                        :autosize="{ minRows: 1, maxRows: 2 }"
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
                    :autosize="{ minRows: 1, maxRows: 2 }"
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
                        size="small"
                        :loading="addrDefaultSaving"
                        :disabled="addrSaving"
                        @click.prevent="makeCurrentAddressDefault"
                      >
                        设为默认
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
                    <el-button
                      type="primary"
                      size="small"
                      class="members-addr-save-btn"
                      :loading="addrSaving"
                      :disabled="addrDefaultSaving"
                      native-type="submit"
                    >
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
.members-addr-overlay {
  padding: max(0.5rem, env(safe-area-inset-top, 0px)) 0.75rem
    max(0.5rem, env(safe-area-inset-bottom, 0px));
}

.modal-card.modal-card--member-edit.members-addr-modal-card {
  max-width: min(760px, 100%);
  border-radius: 12px;
}

.members-addr-modal-body {
  padding: 0.7rem 0.85rem 0.85rem;
  max-height: min(78vh, 620px);
  overflow: auto;
  gap: 0;
}

.members-addr-header {
  padding: 0.4rem 0.9rem 0.4rem 1rem;
}

.members-addr-header .header-info h3 {
  font-size: 1.1rem;
}

.members-addr-header .header-info p {
  margin-top: 1px;
  letter-spacing: 1.5px;
  font-size: 10px;
}

.members-addr-close {
  width: 2rem;
  height: 2rem;
}

.members-addr-layout {
  display: grid;
  grid-template-columns: minmax(168px, 210px) 1fr;
  gap: 10px;
  align-items: start;
}

.members-addr-list-pane {
  position: sticky;
  top: 0;
}

.members-addr-list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 8px;
}

.members-addr-list-hint {
  margin: 0;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  line-height: 1.35;
}

.members-addr-list-hint-mobi {
  display: none;
}

.members-addr-list-empty {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.members-addr-list-item--draft {
  border-style: dashed;
}

.members-addr-list-scroll {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: min(52vh, 460px);
  overflow: auto;
  padding-right: 2px;
}

.members-addr-list-item {
  text-align: left;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  padding: 6px 8px;
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
  gap: 5px;
  flex-wrap: wrap;
  margin-bottom: 2px;
}

.members-addr-list-item-name {
  font-weight: 600;
  font-size: 12px;
  line-height: 1.3;
}

.members-addr-list-item-phone {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.members-addr-list-item-addr {
  font-size: 11px;
  line-height: 1.4;
  color: var(--el-text-color-regular);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.members-addr-list-item-area {
  font-size: 10px;
  color: var(--el-text-color-secondary);
  margin-top: 3px;
}

.members-addr-edit-pane {
  min-width: 0;
}

.members-addr-edit-toolbar {
  display: none;
}

.members-addr-first-row {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.members-addr-k {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}

.members-addr-name {
  max-width: 6.5rem;
}

.members-addr-divider {
  margin: 0 2px !important;
  height: 12px !important;
}

.members-addr-coord-tag {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.members-addr-el-form {
  margin-top: 0;
}

.members-addr-el-form :deep(.el-form-item) {
  margin-bottom: 8px;
}

.members-addr-el-form :deep(.el-form-item__label) {
  margin-bottom: 2px !important;
  font-size: 12px;
  line-height: 1.3;
}

.members-addr-map-form-item :deep(.el-form-item__content) {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.members-addr-map-wrap {
  width: 100%;
}

.members-addr-map-wrap :deep(.mdmp) {
  margin-bottom: 0;
}

.members-addr-map-wrap :deep(.mdmp-search) {
  flex-wrap: nowrap;
  gap: 6px;
  margin-bottom: 6px;
}

.members-addr-map-wrap :deep(.mdmp-search-input) {
  min-width: 0;
  flex: 1;
}

.members-addr-map-wrap :deep(.mdmp-search-btn) {
  padding: 0.4rem 0.75rem;
  font-size: 12px;
}

.members-addr-map-wrap :deep(.mdmp-map) {
  height: min(148px, 24vh);
  min-height: 120px;
  border-radius: 8px;
}

.members-addr-actions {
  margin-bottom: 0 !important;
}

.members-addr-actions-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
}

.members-addr-actions-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-height: 28px;
}

.members-addr-actions :deep(.el-form-item__content) {
  display: block;
}

@media (max-width: 720px) {
  .members-addr-overlay {
    padding: 0;
    align-items: stretch;
    justify-content: stretch;
  }

  .modal-card.modal-card--member-edit.members-addr-modal-card {
    max-width: 100%;
    max-height: 100dvh;
    height: 100%;
    border-radius: 0;
    width: 100%;
  }

  .members-addr-header {
    padding: 0.45rem 0.7rem 0.45rem 0.85rem;
    padding-top: max(0.45rem, env(safe-area-inset-top, 0px));
  }

  .members-addr-modal-body {
    padding: 0.65rem 0.75rem max(0.85rem, env(safe-area-inset-bottom, 0px));
    max-height: none;
    flex: 1 1 auto;
  }

  .members-addr-layout {
    display: block;
  }

  .members-addr-list-pane {
    position: static;
  }

  .members-addr-list-scroll {
    max-height: none;
  }

  .members-addr-list-item {
    padding: 8px 10px;
  }

  .members-addr-list-hint-desk {
    display: none;
  }

  .members-addr-list-hint-mobi {
    display: inline;
  }

  /* 手机：列表与编辑分步，避免双栏挤在一起 */
  .members-addr-layout:not(.is-mobile-edit) .members-addr-edit-pane {
    display: none;
  }

  .members-addr-layout.is-mobile-edit .members-addr-list-pane {
    display: none;
  }

  .members-addr-edit-toolbar {
    display: flex;
    align-items: center;
    margin: -2px 0 8px;
  }

  .members-addr-back-btn {
    padding-left: 0;
    margin-left: -4px;
  }

  .members-addr-map-wrap :deep(.mdmp-map) {
    height: min(160px, 28vh);
    min-height: 132px;
  }

  .members-addr-actions-inner {
    flex-direction: column;
    align-items: stretch;
  }

  .members-addr-save-btn {
    width: 100%;
  }

  .members-addr-coord-tag {
    max-width: 100%;
  }

  .members-addr-name {
    max-width: 8rem;
  }
}
</style>
