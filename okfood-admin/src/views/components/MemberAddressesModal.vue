<script setup>
import { ref, watch, computed } from 'vue'
import { X } from 'lucide-vue-next'
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
/** 当前编辑行：含地图用字符串经纬度 */
const addrEdit = ref(null)
/** 多条地址时下拉切换 */
const addrSelectedId = ref(null)

function formatAddrPca(a) {
  if (!a || typeof a !== 'object') return '—'
  const parts = [a.province, a.city, a.district].filter((x) => x && String(x).trim())
  return parts.length ? parts.join(' ') : '—'
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

function addrOptionLabel(a) {
  const tag = a.is_default ? '默认 · ' : ''
  return `${tag}${a.contact_name || '—'} ${a.contact_phone || ''}`.trim()
}

function onAddrSelectChange(id) {
  if (id == null || id === '') return
  const row = addrList.value.find((x) => Number(x.id) === Number(id))
  if (row) pickAddrEdit(row)
}

const addrHeadCoordDisplay = computed(() => {
  if (!addrEdit.value) return '—'
  const a = String(addrEdit.value.lngStr ?? '').trim()
  const b = String(addrEdit.value.latStr ?? '').trim()
  if (a && b) return `${a}, ${b}`
  return '未选点'
})

const addrHeadPcaDisplay = computed(() => {
  if (!addrEdit.value) return '—'
  const row = addrList.value.find((x) => Number(x.id) === Number(addrEdit.value.id))
  return formatAddrPca(row)
})

async function loadAddressesForMember() {
  const m = props.member
  if (!open.value || !m?.id) return
  addrList.value = []
  addrEdit.value = null
  addrSelectedId.value = null
  addrLoading.value = true
  try {
    const list = await apiJson(`/api/admin/users/${Number(m.id)}/addresses`, {}, { auth: true })
    addrList.value = Array.isArray(list) ? list : []
    const def = addrList.value.find((x) => x.is_default) || addrList.value[0]
    if (def) pickAddrEdit(def)
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
  if (mid != null) void loadAddressesForMember()
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
  if (!m?.id || !ed?.id) return
  addrSaving.value = true
  try {
    const payload = {
      contact_name: (ed.contact_name || '').trim(),
      contact_phone: (ed.contact_phone || '').trim(),
      map_location_text: (ed.map_location_text || '').trim() || null,
      door_detail: (ed.door_detail || '').trim() || null,
      remarks: (ed.remarks || '').trim() || null,
    }
    const lng = Number(String(ed.lngStr ?? '').trim())
    const lat = Number(String(ed.latStr ?? '').trim())
    if (Number.isFinite(lng) && Number.isFinite(lat)) {
      payload.location = { lng, lat }
    }
    await apiJson(
      `/api/admin/users/${Number(m.id)}/addresses/${Number(ed.id)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
      { auth: true },
    )
    showToast('地址已保存', 'success')
    const list = await apiJson(`/api/admin/users/${Number(m.id)}/addresses`, {}, { auth: true })
    addrList.value = Array.isArray(list) ? list : []
    const updated = addrList.value.find((x) => Number(x.id) === Number(ed.id))
    if (updated) pickAddrEdit(updated)
    emit('saved')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '保存失败', 'error')
  } finally {
    addrSaving.value = false
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
        <template v-else-if="addrList.length === 0">
          <el-empty description="该会员暂无配送地址记录。" :image-size="80" />
        </template>
        <template v-else>
          <el-select
            v-if="addrList.length > 1"
            v-model="addrSelectedId"
            class="members-addr-switch"
            placeholder="切换配送地址"
            filterable
            size="small"
            @change="onAddrSelectChange"
          >
            <el-option
              v-for="a in addrList"
              :key="a.id"
              :label="addrOptionLabel(a)"
              :value="Number(a.id)"
            />
          </el-select>

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
              <el-divider direction="vertical" class="members-addr-divider" />
              <span class="members-addr-k">省市区</span>
              <el-text size="small" class="members-addr-pca-line" truncated>{{ addrHeadPcaDisplay }}</el-text>
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
                  :key="'ma-' + addrEdit.id"
                  v-model:lng-str="addrEdit.lngStr"
                  v-model:lat-str="addrEdit.latStr"
                  v-model:map-location-text="addrEdit.map_location_text"
                  :search-input-id="'members-addr-amap-' + addrEdit.id"
                  @warn="onAddrMapWarn"
                />
              </div>
            </el-form-item>

            <el-row :gutter="12">
              <el-col :xs="24" :sm="14">
                <el-form-item label="地点信息（小区 / 道路 / POI）">
                  <el-input
                    v-model="addrEdit.map_location_text"
                    type="textarea"
                    :autosize="{ minRows: 2, maxRows: 4 }"
                    maxlength="500"
                    show-word-limit
                    placeholder="不含门牌；可与地图文案同步"
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
              <el-button type="primary" :loading="addrSaving" native-type="submit">保存地址</el-button>
            </el-form-item>
          </el-form>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.members-addr-modal-card {
  max-width: min(620px, 96vw);
}

.members-addr-modal-body {
  padding: 1rem 1.25rem 1.35rem;
  max-height: min(82vh, 680px);
  overflow: auto;
}

.members-addr-switch {
  width: 100%;
  margin-bottom: 10px;
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

.members-addr-actions :deep(.el-form-item__content) {
  justify-content: flex-end;
}
</style>
