<script setup>
import { ref, watch, computed } from 'vue'
import { X, UserPen, CircleHelp, Info, Save, MapPin } from 'lucide-vue-next'
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
  skip_subscription_saturday: false,
  delivery_deferred: false,
  delivery_region_id: '',
})

watch(
  () => editForm.value.delivery_deferred,
  (v) => {
    if (v) editForm.value.store_pickup = false
  },
)

/** 默认配送地址只读展示（与档案同步，不在此弹窗编辑） */
const addressDisplayText = computed(() => (editForm.value.address || '').trim())

/** 不含所属片区：map_location_text + door_detail；否则从列表 address 去掉片区前缀 */
function memberAddressDetailWithoutArea(u) {
  const mapT = typeof u.map_location_text === 'string' ? u.map_location_text.trim() : ''
  const door = typeof u.door_detail === 'string' ? u.door_detail.trim() : ''
  const detail = [mapT, door].filter(Boolean).join(' ').trim()
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
    skip_subscription_saturday: u.skip_subscription_saturday === true,
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
  if (!(editForm.value.address || '').trim()) {
    showToast('默认配送地址为空，请先在会员列表「地址」中维护后再保存', 'error')
    return
  }
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
      skip_subscription_saturday: editForm.value.skip_subscription_saturday === true,
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
  <div v-if="open" class="modal-overlay" v-esc-close="close" @click.self="close">
    <div class="modal-card modal-card--member-edit mem-root">
      <form class="mem-form" @submit.prevent="submitEditMember">
        <!-- 顶栏（参考稿 #064e3b） -->
        <header class="mem-top">
          <div class="mem-top-left">
            <div class="mem-top-ico" aria-hidden="true">
              <UserPen :size="16" :stroke-width="2.25" />
            </div>
            <div>
              <h1 class="mem-top-title">修改会员信息</h1>
              <p class="mem-top-sub">Edit Member Profile</p>
            </div>
          </div>
          <button type="button" class="mem-top-close" @click="close">
            <X :size="20" aria-hidden="true" />
          </button>
        </header>

        <!-- 主区：单列居中 max-w-3xl，可滚动 -->
        <div class="mem-main">
          <div class="mem-main-inner">
            <!-- 1. 会员基础档案 -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">会员基础档案</h2>
              </div>
              <div class="mem-grid-2">
                <div class="mem-field">
                  <label class="mem-lab">会员手机号</label>
                  <input
                    class="mem-input mem-input-readonly font-mono"
                    type="text"
                    :value="editForm.phone"
                    readonly
                  />
                </div>
                <div class="mem-field">
                  <label class="mem-lab">姓名</label>
                  <input
                    v-model="editForm.name"
                    type="text"
                    required
                    maxlength="100"
                    class="mem-input"
                    placeholder="请输入姓名"
                  />
                </div>
              </div>
            </section>

            <!-- 默认配送地址（只读，位于档案与权益之间） -->
            <section class="mem-sec mem-sec--addr">
              <div class="mem-addr-head">
                <div class="mem-addr-head-main">
                  <MapPin :size="14" class="mem-addr-head-ico" aria-hidden="true" />
                  <h2 class="mem-addr-title">默认配送地址</h2>
                </div>
                <p class="mem-addr-foot">
                  注：如需修改地址，请前往地址库或通过工单重新绑定。
                </p>
              </div>
              <div class="mem-addr-box">
                <p class="mem-addr-text">
                  {{ addressDisplayText || '未设置配送地址' }}
                </p>
              </div>
            </section>

            <!-- 2. 权益资产 -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">权益资产</h2>
              </div>
              <div class="mem-grid-3">
                <div class="mem-field">
                  <label class="mem-lab mem-lab-inline">
                    剩余次数
                    <CircleHelp
                      class="mem-tip"
                      :size="14"
                      title="直接修改将产生余额流水（管理端调整）；常规续卡请走开卡工单入账"
                    />
                  </label>
                  <div class="mem-affix">
                    <input
                      v-model.number="editForm.balance"
                      type="number"
                      min="0"
                      max="999999"
                      step="1"
                      required
                      class="mem-input mem-input-em mem-affix-inp"
                    />
                    <span class="mem-affix-suf">次</span>
                  </div>
                </div>
                <div class="mem-field">
                  <label class="mem-lab">每配送日份数</label>
                  <div class="mem-affix">
                    <input
                      v-model.number="editForm.daily_meal_units"
                      type="number"
                      min="1"
                      max="50"
                      step="1"
                      required
                      class="mem-input mem-affix-inp"
                    />
                    <span class="mem-affix-suf">份</span>
                  </div>
                </div>
                <div class="mem-field">
                  <label class="mem-lab">套餐类型</label>
                  <select v-model="editForm.plan_type" class="mem-input">
                    <option value="周卡">周卡</option>
                    <option value="月卡">月卡</option>
                    <option value="次卡">次卡</option>
                  </select>
                </div>
              </div>
            </section>

            <!-- 3. 配送与时间设置 -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">配送与时间设置</h2>
              </div>

              <div class="mem-grid-2">
                <div class="mem-field">
                  <label class="mem-lab mem-lab-inline">
                    配送片区
                    <Info
                      class="mem-tip"
                      :size="14"
                      title="勾选自动划区后保存将忽略此处手动所选；否则先地理编码再以所选片区覆盖"
                    />
                  </label>
                  <select
                    v-model="editForm.delivery_region_id"
                    class="mem-input"
                    :disabled="editForm.use_auto_area"
                  >
                    <option value="">未分配</option>
                    <option v-for="r in regionOptions" :key="r.id" :value="String(r.id)">
                      {{ r.name || '—' }}
                    </option>
                  </select>
                </div>
                <div class="mem-field">
                  <label class="mem-lab">业务起送日期</label>
                  <input v-model="editForm.delivery_start_date" type="date" class="mem-input" />
                </div>
              </div>

              <label class="mem-auto-chk">
                <input v-model="editForm.use_auto_area" type="checkbox" />
                <span>保存时按当前地址重新自动划区</span>
              </label>
              <p class="mem-hint-soft">
                未勾选时：保存会先按地址地理编码划区，再以您所选片区覆盖。勾选后忽略手动片区。
              </p>

              <div class="mem-chk-band">
                <label class="mem-chk mem-chk--red">
                  <input v-model="editForm.delivery_deferred" type="checkbox" />
                  <span>暂停配送</span>
                </label>
                <label class="mem-chk mem-chk--blue">
                  <input
                    v-model="editForm.store_pickup"
                    type="checkbox"
                    :disabled="editForm.delivery_deferred"
                  />
                  <span>门店自提</span>
                </label>
                <label class="mem-chk mem-chk--amber">
                  <input v-model="editForm.skip_subscription_saturday" type="checkbox" />
                  <span>周六不参与</span>
                </label>
              </div>
            </section>

            <!-- 4. 备注 -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">备注</h2>
              </div>
              <textarea
                v-model="editForm.remarks"
                maxlength="500"
                class="mem-input mem-ta"
                placeholder="请在此输入特别说明或客户需求..."
              ></textarea>
            </section>
          </div>
        </div>

        <footer class="mem-ft">
          <div class="mem-ft-inner">
            <button type="submit" class="mem-btn mem-btn-primary" :disabled="editSaving">
              <Save :size="16" aria-hidden="true" />
              {{ editSaving ? '保存中…' : '确认并保存修改' }}
            </button>
            <button type="button" class="mem-btn mem-btn-ghost" @click="close">取消</button>
          </div>
        </footer>
      </form>
    </div>
  </div>
</template>

<style scoped>
.font-mono {
  font-family: ui-monospace, monospace;
}

/* 弹窗本体：单列、接近参考稿「整页中间容器」宽度 */
.mem-root {
  width: min(48rem, calc(100vw - 1.25rem));
  max-height: calc(100dvh - 2rem);
  padding: 0 !important;
  overflow: hidden;
  border-radius: 1rem !important;
  display: flex;
  flex-direction: column;
}

.mem-form {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.mem-top {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.72rem 1.35rem;
  background: #064e3b;
  color: #fff;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  z-index: 3;
}

.mem-top-left {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.mem-top-ico {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.1);
}

.mem-top-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.mem-top-sub {
  margin: 3px 0 0;
  font-size: 9px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.2em;
  opacity: 0.58;
}

.mem-top-close {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s ease;
}

.mem-top-close:hover {
  background: rgba(255, 255, 255, 0.12);
}

.mem-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: #f8fafc;
  scrollbar-width: thin;
}

.mem-main-inner {
  box-sizing: border-box;
  max-width: 48rem;
  margin: 0 auto;
  padding: 1rem 1.25rem;
  padding-bottom: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

@media (min-width: 768px) {
  .mem-main-inner {
    padding: 1.35rem 1.5rem 2rem;
  }
}

.mem-sec {
  flex-shrink: 0;
  background: #fff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 1.15rem 1.2rem;
}

.mem-sec--addr {
  background: rgba(236, 253, 245, 0.45);
  border-color: rgba(167, 243, 208, 0.8);
}

.mem-sec-head {
  display: flex;
  align-items: center;
  gap: 0.46rem;
  margin-bottom: 0.92rem;
}

.mem-bar {
  width: 3px;
  height: 14px;
  border-radius: 999px;
  background: #10b981;
}

.mem-sec-title {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 800;
  color: #1e293b;
}

.mem-addr-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem 0.85rem;
  flex-wrap: wrap;
  margin-bottom: 0.72rem;
}

.mem-addr-head-main {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  min-width: 0;
  flex-shrink: 0;
}

.mem-addr-head-ico {
  color: #059669;
}

.mem-addr-title {
  margin: 0;
  font-size: 0.688rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: rgba(6, 78, 59, 0.9);
}

.mem-addr-box {
  padding: 0.75rem 0.85rem;
  background: #fff;
  border-radius: 10px;
  border: 1px solid rgba(167, 243, 208, 0.55);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.mem-addr-text {
  margin: 0;
  font-size: 0.875rem;
  font-weight: 600;
  line-height: 1.58;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-word;
}

.mem-addr-foot {
  margin: 0;
  flex: 1 1 12rem;
  min-width: 0;
  font-size: 10px;
  line-height: 1.42;
  color: #94a3b8;
  text-align: right;
}

.mem-field {
  min-width: 0;
}

.mem-lab {
  display: flex;
  align-items: center;
  margin-bottom: 0.4rem;
  font-size: 0.7rem;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mem-lab-inline {
  gap: 0.2rem;
}

.mem-tip {
  flex-shrink: 0;
  color: #94a3b8;
  cursor: help;
}

.mem-tip:hover {
  color: #059669;
}

.mem-input {
  box-sizing: border-box;
  width: 100%;
  padding: 0.58rem 0.82rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  font-size: 0.9rem;
  font-weight: 600;
  color: #0f172a;
  outline: none;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    background 0.2s ease;
}

.mem-input:not(:disabled):hover {
  background: #fafbfc;
}

.mem-input:focus {
  background: #fff;
  border-color: #059669;
  box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.1);
}

.mem-input-readonly {
  cursor: default;
  color: #64748b !important;
  background: #f1f5f9 !important;
  border-color: #e2e8f0 !important;
  box-shadow: none !important;
}

.mem-input-em {
  font-weight: 800;
  color: #047857 !important;
}

select.mem-input {
  cursor: pointer;
}

.mem-grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

.mem-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}

.mem-affix {
  position: relative;
}

.mem-affix-inp {
  padding-right: 2.2rem;
}

.mem-affix-suf {
  position: absolute;
  right: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  pointer-events: none;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
}

.mem-auto-chk {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-top: 0.75rem;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  color: #64748b;
  user-select: none;
}

.mem-auto-chk input {
  width: 15px;
  height: 15px;
  accent-color: #059669;
}

.mem-hint-soft {
  margin: 0.35rem 0 0;
  font-size: 10px;
  line-height: 1.45;
  color: #94a3b8;
}

.mem-chk-band {
  margin-top: 1rem;
  padding-top: 0.72rem;
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1.35rem;
}

.mem-chk {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  user-select: none;
}

.mem-chk span {
  font-size: 0.75rem;
  font-weight: 600;
  color: #475569;
}

.mem-chk input {
  width: 16px;
  height: 16px;
  border-radius: 4px;
}

.mem-chk--red input {
  accent-color: #ef4444;
}

.mem-chk--blue input {
  accent-color: #3b82f6;
}

.mem-chk--amber input {
  accent-color: #d97706;
}

.mem-chk:hover span {
  color: #0f172a;
}

.mem-ta {
  resize: none;
  min-height: 80px;
  font-weight: 500;
  font-size: 0.875rem;
  line-height: 1.48;
}

.mem-ft {
  flex-shrink: 0;
  height: 80px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 1rem;
  background: #fff;
  border-top: 1px solid #e2e8f0;
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.05);
  z-index: 4;
}

.mem-ft-inner {
  box-sizing: border-box;
  max-width: 48rem;
  width: 100%;
  margin: 0 auto;
  display: flex;
  gap: 0.85rem;
  align-items: center;
}

.mem-btn {
  height: 3rem;
  border-radius: 12px;
  font-weight: 800;
  font-size: 0.9rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  cursor: pointer;
  border: none;
  transition:
    transform 0.12s ease,
    background 0.15s ease,
    opacity 0.15s ease;
}

.mem-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.mem-btn-primary {
  flex: 3;
  background: #047857;
  color: #fff;
  box-shadow: 0 4px 18px rgba(6, 78, 59, 0.12);
}

.mem-btn-primary:hover:not(:disabled) {
  background: #065f46;
}

.mem-btn-primary:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.mem-btn-ghost {
  flex: 1;
  background: #fff;
  border: 1px solid #e2e8f0 !important;
  color: #64748b;
}

.mem-btn-ghost:hover {
  background: #f8fafc;
}

@media (max-width: 680px) {
  .mem-grid-2,
  .mem-grid-3 {
    grid-template-columns: 1fr;
  }

  .mem-addr-foot {
    flex-basis: 100%;
    text-align: left;
  }

  .mem-main-inner {
    padding-left: 0.95rem;
    padding-right: 0.95rem;
  }

  .mem-ft-inner {
    flex-direction: column;
    height: auto;
    gap: 0.5rem;
  }

  .mem-ft {
    height: auto;
    padding-top: 0.65rem;
    padding-bottom: 0.75rem;
  }

  .mem-btn-primary,
  .mem-btn-ghost {
    flex: none;
    width: 100%;
  }
}
</style>
