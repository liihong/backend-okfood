<script setup>
import { ref, watch } from 'vue'
import { X } from 'lucide-vue-next'
import { apiJson, handleAdminLogout } from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  /** mapAdminUserToRow 行；弹窗打开时应非空 */
  member: { type: Object, default: null },
  /** 与列表筛选一致：配送区域下拉 */
  regionOptions: { type: Array, default: () => [] },
})

const emit = defineEmits(['saved'])

const editSaving = ref(false)
/** 打开编辑弹窗时的套餐类型，用于判断是否与档案一致、是否提交 plan_type */
const editInitialPlanType = ref('次卡')
const editForm = ref({
  phone: '',
  name: '',
  address: '',
  remarks: '',
  daily_meal_units: 1,
  plan_type: '次卡',
  use_auto_area: false,
  balance: 0,
  delivery_start_date: '',
  store_pickup: false,
  delivery_deferred: false,
  delivery_region_id: '',
})

watch(
  () => editForm.value.delivery_deferred,
  (v) => {
    if (v) editForm.value.store_pickup = false
  },
)

/** 不含所属片区：优先 detail_address，否则从旧版「片区 + 详细」串去掉 u.area 前缀 */
function memberAddressDetailWithoutArea(u) {
  const detail = typeof u.detail_address === 'string' ? u.detail_address.trim() : ''
  if (detail) return detail
  const rawAddr = String(u.address || '').trim()
  if (!rawAddr || rawAddr.startsWith('（未设置')) return ''
  const areaTag = String(u.area || '').trim()
  if (areaTag && areaTag !== '—' && rawAddr.startsWith(areaTag)) {
    return rawAddr.slice(areaTag.length).trim()
  }
  return rawAddr
}

function fillFormFromMember(u) {
  const p0 = u.plan && u.plan !== '—' ? u.plan : '次卡'
  editInitialPlanType.value = p0
  const dr =
    u.delivery_region_id != null && u.delivery_region_id !== '' ? String(u.delivery_region_id) : ''
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    address: memberAddressDetailWithoutArea(u),
    remarks: u.remarks || '',
    daily_meal_units: Math.max(1, Math.min(50, Number(u.daily_meal_units) || 1)),
    plan_type: p0,
    use_auto_area: false,
    balance: Math.max(0, Math.min(999999, Math.floor(Number(u.balance) || 0))),
    delivery_start_date:
      typeof u.delivery_start_date === 'string' && u.delivery_start_date.trim()
        ? u.delivery_start_date.trim().slice(0, 10)
        : '',
    store_pickup: u.store_pickup === true,
    delivery_deferred: u.delivery_deferred === true,
    delivery_region_id: dr,
  }
}

watch(
  [open, () => props.member],
  ([isOpen, m]) => {
    if (isOpen && m && typeof m === 'object') fillFormFromMember(m)
  },
  { flush: 'sync' },
)

function close() {
  open.value = false
}

async function submitEditMember() {
  if (!editForm.value.phone) return
  editSaving.value = true
  try {
    const payload = {
      phone: editForm.value.phone,
      name: editForm.value.name.trim(),
      remarks: editForm.value.remarks.trim() || null,
      address: editForm.value.address.trim() || null,
      daily_meal_units: Math.max(1, Math.min(50, Number(editForm.value.daily_meal_units) || 1)),
      balance: Math.max(0, Math.min(999999, Math.floor(Number(editForm.value.balance) || 0))),
      delivery_start_date: editForm.value.delivery_start_date?.trim()
        ? editForm.value.delivery_start_date.trim().slice(0, 10)
        : null,
      store_pickup: editForm.value.store_pickup === true,
      delivery_deferred: editForm.value.delivery_deferred === true,
    }
    if (editForm.value.use_auto_area) {
      payload.use_auto_area = true
    } else {
      const dr = editForm.value.delivery_region_id
      payload.delivery_region_id = dr === '' || dr == null ? null : Number(dr)
    }
    const pt = String(editForm.value.plan_type || '次卡').trim() || '次卡'
    if (pt !== editInitialPlanType.value) {
      payload.plan_type = pt
    }
    await apiJson(
      '/api/admin/member/profile',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      { auth: true },
    )
    close()
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
    editSaving.value = false
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
    <div class="modal-card modal-card--member-edit">
      <div class="modal-header">
        <div class="header-info">
          <h3>修改会员信息</h3>
          <p>EDIT MEMBER PROFILE</p>
        </div>
        <button type="button" class="close-btn" @click="close()">
          <X :size="20" />
        </button>
      </div>
      <form class="modal-form modal-form--member-two-col" @submit.prevent="submitEditMember">
        <div class="form-group">
          <label>手机号</label>
          <input :value="editForm.phone" type="text" disabled class="input-disabled" />
        </div>
        <div class="form-group">
          <label>姓名</label>
          <input v-model="editForm.name" required maxlength="100" />
        </div>
        <div class="form-group form-group--span-full">
          <label>默认配送地址</label>
          <textarea v-model="editForm.address" required rows="3" maxlength="500"></textarea>
        </div>
        <div class="form-group form-group--span-full">
          <label>配送片区</label>
          <select
            v-model="editForm.delivery_region_id"
            class="input-delivery-area"
            :disabled="editForm.use_auto_area"
          >
            <option value="">未分配</option>
            <option v-for="r in regionOptions" :key="r.id" :value="String(r.id)">
              {{ r.name || '—' }}
            </option>
          </select>
          <label class="checkbox-row">
            <input v-model="editForm.use_auto_area" type="checkbox" />
            <span>保存时按地址/坐标重新自动划区（勾选后忽略下方手动片区）</span>
          </label>
          <p class="modal-hint">
            下拉列表与列表筛选一致（仅启用中的配送区域）。未勾选自动划区时，保存会先按地址地理编码划区，再以您选择的片区覆盖。
          </p>
        </div>
        <div class="form-group form-group--span-full member-delivery-block">
          <label>开始配送日期（起送业务日）</label>
          <div class="member-delivery-controls-row">
            <div class="member-delivery-date-wrap">
              <input v-model="editForm.delivery_start_date" type="date" />
            </div>
            <label class="checkbox-row member-delivery-check">
              <input v-model="editForm.delivery_deferred" type="checkbox" />
              <span>暂停配送（会员卡停用）</span>
            </label>
            <label class="checkbox-row member-delivery-check">
              <input
                v-model="editForm.store_pickup"
                type="checkbox"
                :disabled="editForm.delivery_deferred"
              />
              <span>门店自提（不到家配送，仍计入备餐大表「门店自提」分组）</span>
            </label>
          </div>
          <p class="modal-hint">
            上海业务日：该日及之后才进入配送排期；留空表示未设置起送日。保存时会与「未开卡 / 余额」等规则一并生效；勾选「暂停配送」时保存会清空起送日。
          </p>
          <p class="modal-hint">
            与小程序「暂不配送 / 先不开卡」为同一数据字段。勾选后不参与配送大表/分拣、不计入开卡分货，并会清空起送日、关闭门店自提。取消勾选且有余额时恢复为在册活跃（是否排期仍取决于起送日等条件）。
          </p>
        </div>
        <div class="form-group">
          <label>会员剩余次数</label>
          <input
            v-model.number="editForm.balance"
            type="number"
            min="0"
            max="999999"
            step="1"
            required
          />
          <p class="modal-hint">
            直接修改当前剩余订餐次数；与旧值的差额会写入余额流水（原因：管理端调整）。常规续卡仍建议走「开卡工单」入账。
          </p>
        </div>
        <div class="form-group">
          <label>每配送日份数</label>
          <input
            v-model.number="editForm.daily_meal_units"
            type="number"
            min="1"
            max="50"
            step="1"
            required
          />
          <p class="modal-hint">例如购 2 张周卡、同日需送 2 份时填 2；确认送达将按该倍数扣减剩余次数。</p>
        </div>
        <div class="form-group">
          <label>套餐类型（档案标签）</label>
          <select v-model="editForm.plan_type" class="input-delivery-area">
            <option value="周卡">周卡</option>
            <option value="月卡">月卡</option>
            <option value="次卡">次卡</option>
          </select>
          <p class="modal-hint">
            仅同步列表与小程序展示的套餐角标，不会增减剩余次数；次数增减须通过「开卡工单」同步入账。若续月卡后角标仍为周卡，可在此改为月卡。
          </p>
        </div>
        <div class="form-group">
          <label>备注（忌口等）</label>
          <textarea v-model="editForm.remarks" rows="4" maxlength="500" placeholder="可留空"></textarea>
        </div>
        <button type="submit" class="btn-submit-order" :disabled="editSaving">
          {{ editSaving ? '保存中…' : '保存' }}
        </button>
      </form>
    </div>
  </div>
</template>
