<script setup>
import { ref, watch, computed, onActivated } from 'vue'
import { X, UserPen, CircleHelp, Info, Save, Truck } from 'lucide-vue-next'
import {
  apiJson,
  handleAdminLogout,
  mapAdminUserToRow,
  mealScopeLabelFromPeriods,
  membershipTemplatePlanLabel,
} from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'

/** 档案套餐无法匹配已开启卡包时的占位值，避免下拉空白 */
const CURRENT_PLAN_VALUE = '__current__'

/** 统一「月卡 · 全餐」与「月卡·全餐」，避免下拉对不上已选模版 */
function normalizePlanLabel(s) {
  return String(s || '')
    .replace(/\s*·\s*/g, '·')
    .trim()
}

/**
 * 与后端 `_plan_for_membership_template` 对齐：种类文案 / 餐次 → 周卡/月卡/次卡
 * @param {Record<string, unknown> | null | undefined} tpl
 */
function planTypeFromTemplate(tpl) {
  const kl = String(tpl?.kind_label || '').trim()
  const pk = String(tpl?.period_kind || '').trim().toLowerCase()
  if (kl.includes('月') || pk === 'monthly') return '月卡'
  if (kl.includes('周') || pk === 'weekly') return '周卡'
  const mg = Number(tpl?.meals_grant) || 0
  if (mg >= 18) return '月卡'
  if (mg >= 6) return '周卡'
  return '次卡'
}

/**
 * 将档案当前套餐匹配到本店卡包（种类 + 餐段优先）
 * @param {Array<Record<string, unknown>>} templates
 * @param {Record<string, unknown> | null | undefined} member
 */
function matchMemberTemplate(templates, member) {
  const list = Array.isArray(templates) ? templates : []
  if (!list.length || !member) return null
  const planBase = String(member.planBase || member.plan_type || '').trim()
  const display = normalizePlanLabel(member.plan)
  const scope = mealScopeLabelFromPeriods(member.entitled_meal_periods)
  // 仅精确匹配，避免把「月卡 · 全餐」错配成租户另一张「月卡 · 午餐」
  const byDisplay = display
    ? list.find((t) => normalizePlanLabel(membershipTemplatePlanLabel(t)) === display)
    : null
  if (byDisplay?.id != null) return Number(byDisplay.id)
  const exact = list.find((t) => {
    const kl = String(t.kind_label || '').trim()
    return kl === planBase && mealScopeLabelFromPeriods(t.meal_periods) === scope
  })
  if (exact?.id != null) return Number(exact.id)
  return null
}

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  /** mapAdminUserToRow 行；弹窗打开时应非空 */
  member: { type: Object, default: null },
  /** 与列表筛选一致：配送区域下拉 */
  regionOptions: { type: Array, default: () => [] },
})

const emit = defineEmits(['saved'])

const editSaving = ref(false)
const reinstateBusy = ref(false)
/** 打开编辑弹窗时的套餐类型，用于判断是否与档案一致、是否提交 plan_type */
const editInitialPlanType = ref('次卡')
/** 打开时选中的卡包模版 id；换模版即使仍是月卡也要提交，否则不落库、不写操作记录 */
const editInitialTemplateId = ref(CURRENT_PLAN_VALUE)
/** 打开/刷新表单时的剩余次数，仅用户主动修改时才提交 balance，避免 keep-alive 快照误覆盖 */
const editInitialBalance = ref(0)
/** 打开时的片区，仅用户改片区或勾选自动划区时才提交，避免备注保存误写地址行 */
const editInitialDeliveryRegionId = ref('')
const profileLoading = ref(false)
/** 当前租户已开启的会员卡模版（套餐类型下拉） */
const membershipTemplates = ref([])
const membershipTemplatesLoading = ref(false)
const editForm = ref({
  phone: '',
  name: '',
  remarks: '',
  daily_meal_units: 1,
  plan_type: '次卡',
  membership_template_id: CURRENT_PLAN_VALUE,
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

watch(
  () => editForm.value.store_pickup,
  (v) => {
    if (v) editForm.value.use_auto_area = false
  },
)

/** 自动划区勾选说明：自提时不参与划区 */
const autoAreaHintText = computed(() =>
  editForm.value.store_pickup
    ? '门店自提不参与配送划区。'
    : '仅勾选后保存才会按已有坐标重算片区；不改片区则不提交，避免动到地址。',
)

function normalizeBalance(v) {
  return Math.max(0, Math.min(999999, Math.floor(Number(v) || 0)))
}

/** 当前租户已开启卡包 → 套餐下拉选项（按展示文案去重） */
const planOptions = computed(() => {
  const seen = new Set()
  const opts = []
  for (const t of membershipTemplates.value) {
    const id = Number(t?.id)
    if (!Number.isFinite(id) || id <= 0) continue
    const label = membershipTemplatePlanLabel(t)
    const labelKey = normalizePlanLabel(label)
    if (seen.has(labelKey)) continue
    seen.add(labelKey)
    opts.push({ id, label, planType: planTypeFromTemplate(t) })
  }
  const selected = editForm.value.membership_template_id
  if (selected === CURRENT_PLAN_VALUE) {
    const currentLabel =
      (props.member?.plan && String(props.member.plan).trim()) ||
      String(editForm.value.plan_type || '次卡').trim() ||
      '次卡'
    const currentNorm = normalizePlanLabel(currentLabel)
    if (!opts.some((o) => normalizePlanLabel(o.label) === currentNorm)) {
      opts.unshift({
        id: CURRENT_PLAN_VALUE,
        label: currentLabel,
        planType: editInitialPlanType.value || '次卡',
      })
    }
  }
  return opts
})

watch(planOptions, (opts) => {
  if (editForm.value.membership_template_id !== CURRENT_PLAN_VALUE) return
  const currentLabel =
    (props.member?.plan && String(props.member.plan).trim()) ||
    String(editForm.value.plan_type || '').trim()
  const currentNorm = normalizePlanLabel(currentLabel)
  const hit = opts.find(
    (o) => o.id !== CURRENT_PLAN_VALUE && normalizePlanLabel(o.label) === currentNorm,
  )
  if (hit) {
    editForm.value.membership_template_id = hit.id
    // 打开时自动对上卡包，初始值一并对齐，避免未改下拉却误提交
    if (editInitialTemplateId.value === CURRENT_PLAN_VALUE) {
      editInitialTemplateId.value = hit.id
    }
  }
})

async function loadMembershipTemplates() {
  membershipTemplatesLoading.value = true
  try {
    const data = await apiJson(
      '/api/admin/catalog/membership-templates?active_only=true',
      {},
      { auth: true },
    )
    membershipTemplates.value = Array.isArray(data) ? data : []
  } catch (e) {
    membershipTemplates.value = []
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) throw e
    showToast(e instanceof Error ? e.message : '加载本店会员卡失败', 'error')
  } finally {
    membershipTemplatesLoading.value = false
  }
}

function resolveSelectedPlanType() {
  const id = editForm.value.membership_template_id
  if (id == null || id === CURRENT_PLAN_VALUE) {
    return String(editForm.value.plan_type || '次卡').trim() || '次卡'
  }
  const hit = planOptions.value.find((o) => String(o.id) === String(id))
  if (hit?.planType) return hit.planType
  const tpl = membershipTemplates.value.find((t) => Number(t.id) === Number(id))
  if (tpl) return planTypeFromTemplate(tpl)
  return String(editForm.value.plan_type || '次卡').trim() || '次卡'
}

function fillFormFromMember(u) {
  // 提交口径用 planBase（周卡/月卡/次卡），勿用列表展示文案「月卡 · 全餐」
  const p0 = u.planBase && u.planBase !== '—' ? String(u.planBase).trim() : '次卡'
  editInitialPlanType.value = p0
  const matchedId = matchMemberTemplate(membershipTemplates.value, u)
  editInitialTemplateId.value = matchedId != null ? matchedId : CURRENT_PLAN_VALUE
  const dr =
    u.delivery_region_id != null && u.delivery_region_id !== '' ? String(u.delivery_region_id) : ''
  const balance = normalizeBalance(u.balance)
  editInitialBalance.value = balance
  editInitialDeliveryRegionId.value = dr
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    remarks: u.remarks || '',
    daily_meal_units: Math.max(1, Math.min(50, Number(u.daily_meal_units) || 1)),
    plan_type: p0,
    membership_template_id: matchedId != null ? matchedId : CURRENT_PLAN_VALUE,
    use_auto_area: false,
    balance,
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

/** 打开弹窗时拉取最新档案与本店卡包，避免列表 keep-alive 缓存与送达扣次不同步 */
async function refreshMemberFormFromServer(u) {
  if (!u || typeof u !== 'object') return
  const phone = String(u.phone || '').trim()
  if (!phone) {
    try {
      await loadMembershipTemplates()
    } catch (e) {
      const status = e && typeof e.status === 'number' ? e.status : 0
      if (status === 401) {
        alert('登录已过期，请重新登录')
        handleAdminLogout()
        return
      }
    }
    fillFormFromMember(u)
    return
  }
  profileLoading.value = true
  try {
    const params = new URLSearchParams({ q: phone, page: '1', page_size: '1' })
    const [data] = await Promise.all([
      apiJson(`/api/admin/users?${params}`, {}, { auth: true }),
      loadMembershipTemplates(),
    ])
    const rawItems = Array.isArray(data?.items) ? data.items : []
    const fresh = rawItems.length ? mapAdminUserToRow(rawItems[0], 0) : u
    fillFormFromMember(fresh)
  } catch (e) {
    fillFormFromMember(u)
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '加载最新会员档案失败，已使用列表数据', 'error')
  } finally {
    profileLoading.value = false
  }
}

watch(
  [open, () => props.member],
  ([isOpen, m]) => {
    if (isOpen && m && typeof m === 'object') void refreshMemberFormFromServer(m)
  },
  { flush: 'sync' },
)

/** 标签页 keep-alive 切回且弹窗仍打开时，同步最新剩余次数等字段 */
onActivated(() => {
  if (open.value && props.member) void refreshMemberFormFromServer(props.member)
})

function close() {
  open.value = false
}

/** 从会员档案推断餐段（纯晚餐卡默认 dinner，否则 lunch） */
function resolveMemberMealPeriod(u) {
  const periods = Array.isArray(u?.entitled_meal_periods) ? u.entitled_meal_periods : []
  if (periods.includes('dinner') && !periods.includes('lunch')) return 'dinner'
  return 'lunch'
}

/** 推单冻结后取消请假：强制加入当天配送大表（独立接口，不影响其它锁表逻辑） */
async function forceReinstateToDeliverySheet() {
  const u = props.member
  if (!u?.phone || reinstateBusy.value) return
  const mealPeriod = resolveMemberMealPeriod(u)
  const periodLabel = mealPeriod === 'dinner' ? '晚餐' : '午餐'
  const ok = window.confirm(
    `确认将 ${u.name || u.phone} 强制加入今日${periodLabel}配送大表？\n仅用于推单后取消请假需当日补送；其他锁表逻辑不变。`,
  )
  if (!ok) return
  reinstateBusy.value = true
  try {
    await apiJson(
      '/api/admin/delivery-sheet/reinstate-member',
      {
        method: 'POST',
        body: JSON.stringify({ phone: u.phone, meal_period: mealPeriod }),
      },
      { auth: true },
    )
    showToast('已强制加入当天配送大表', 'success')
  } catch (e) {
    const status = e && typeof e.status === 'number' ? e.status : 0
    if (status === 401) {
      alert('登录已过期，请重新登录')
      handleAdminLogout()
      return
    }
    showToast(e instanceof Error ? e.message : '强制加入失败', 'error')
  } finally {
    reinstateBusy.value = false
  }
}

async function submitEditMember() {
  if (!editForm.value.phone) return
  if (profileLoading.value) return
  const isStorePickup = editForm.value.store_pickup === true
  editSaving.value = true
  try {
    const balanceVal = normalizeBalance(editForm.value.balance)
    const payload = {
      phone: editForm.value.phone,
      name: editForm.value.name.trim(),
      remarks: editForm.value.remarks.trim() || null,
      daily_meal_units: Math.max(1, Math.min(50, Number(editForm.value.daily_meal_units) || 1)),
      delivery_start_date: String(editForm.value.delivery_start_date ?? '').trim()
        ? String(editForm.value.delivery_start_date).trim().slice(0, 10)
        : null,
      store_pickup: isStorePickup,
      skip_subscription_saturday: editForm.value.skip_subscription_saturday === true,
      delivery_deferred: editForm.value.delivery_deferred === true,
    }
    // 仅运营主动修改剩余次数时才提交，避免暂停配送等操作附带过期 balance 写库
    if (balanceVal !== editInitialBalance.value) {
      payload.balance = balanceVal
    }
    // 不提交 address。片区仅在勾选自动划区或手动改了下拉时才提交，避免备注保存写地址行。
    if (editForm.value.use_auto_area) {
      payload.use_auto_area = true
    } else {
      const dr = editForm.value.delivery_region_id
      const next = dr === '' || dr == null ? '' : String(dr)
      if (next !== String(editInitialDeliveryRegionId.value || '')) {
        payload.delivery_region_id = next === '' ? null : Number(dr)
      }
    }
    const pt = resolveSelectedPlanType()
    const selectedTplId = editForm.value.membership_template_id
    const hasRealTpl =
      selectedTplId != null && selectedTplId !== CURRENT_PLAN_VALUE && Number(selectedTplId) > 0
    const templateChanged =
      hasRealTpl && String(selectedTplId) !== String(editInitialTemplateId.value)
    const planTypeChanged = pt !== editInitialPlanType.value
    // 换卡包（含同为月卡但餐段不同）或周/月/次变化都要提交，否则后端不改套餐、不写操作记录
    if (templateChanged || planTypeChanged) {
      payload.plan_type = pt
      if (hasRealTpl) {
        payload.membership_template_id = Number(selectedTplId)
      }
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
            <!-- 1. 会员基础档案（地址不在此编辑，请走地址管理） -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">会员基础档案</h2>
              </div>
              <div class="mem-grid-2">
                <div class="mem-field">
                  <label class="mem-lab">会员手机号</label>
                  <el-input
                    class="mem-input-el mem-input-readonly"
                    :model-value="editForm.phone"
                    disabled
                  />
                </div>
                <div class="mem-field">
                  <label class="mem-lab">姓名</label>
                  <el-input
                    v-model="editForm.name"
                    maxlength="100"
                    placeholder="请输入姓名"
                    clearable
                    class="mem-input-el"
                  />
                </div>
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
                    <el-tooltip
                      content="直接修改将产生余额流水（管理端调整）；常规续卡请走开卡工单入账"
                      placement="top"
                    >
                      <span class="mem-tip-wrap">
                        <CircleHelp class="mem-tip" :size="13" />
                      </span>
                    </el-tooltip>
                  </label>
                  <div class="mem-affix mem-affix--el-row">
                    <el-input-number
                      v-model="editForm.balance"
                      :min="0"
                      :max="999999"
                      :step="1"
                      controls-position="right"
                      class="mem-input-el mem-affix-inp-el"
                    />
                    <span class="mem-affix-suf-el">次</span>
                  </div>
                </div>
                <div class="mem-field">
                  <label class="mem-lab mem-lab-inline">
                    每配送日份数
                    <el-tooltip placement="top">
                      <template #content>
                        <div class="mem-tip-body">
                          修改后次日配送日起生效，当日备餐/顺丰推单份数不变；若须调整当日配送请协调顺丰或厨房。
                        </div>
                      </template>
                      <span class="mem-tip-wrap">
                        <CircleHelp class="mem-tip" :size="13" />
                      </span>
                    </el-tooltip>
                  </label>
                  <div class="mem-affix mem-affix--el-row">
                    <el-input-number
                      v-model="editForm.daily_meal_units"
                      :min="1"
                      :max="50"
                      :step="1"
                      controls-position="right"
                      class="mem-input-el mem-affix-inp-el"
                    />
                    <span class="mem-affix-suf-el">份</span>
                  </div>
                </div>
                <div class="mem-field">
                  <label class="mem-lab">套餐类型</label>
                  <el-select
                    v-model="editForm.membership_template_id"
                    class="mem-input-el mem-select-el"
                    :loading="membershipTemplatesLoading"
                    :placeholder="
                      membershipTemplatesLoading
                        ? '加载本店会员卡…'
                        : planOptions.length
                          ? '请选择本店会员卡'
                          : '暂无已开启的会员卡'
                    "
                  >
                    <el-option
                      v-for="opt in planOptions"
                      :key="String(opt.id)"
                      :label="opt.label"
                      :value="opt.id"
                    />
                  </el-select>
                  <p
                    v-if="!membershipTemplatesLoading && !membershipTemplates.length"
                    class="mem-hint-soft"
                  >
                    暂无已开启的卡包，请先在「会员卡管理」中创建并开启。
                  </p>
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
                    <el-tooltip placement="top">
                      <template #content>
                        <div class="mem-tip-body">{{ autoAreaHintText }}</div>
                      </template>
                      <span class="mem-tip-wrap">
                        <Info class="mem-tip" :size="13" />
                      </span>
                    </el-tooltip>
                  </label>
                  <div class="mem-region-row">
                    <el-select
                      v-model="editForm.delivery_region_id"
                      class="mem-input-el mem-select-el"
                      :disabled="editForm.use_auto_area"
                      clearable
                      placeholder="未分配"
                    >
                      <el-option label="未分配" value="" />
                      <el-option
                        v-for="r in regionOptions"
                        :key="r.id"
                        :label="r.name || '—'"
                        :value="String(r.id)"
                      />
                    </el-select>
                    <el-checkbox
                      v-model="editForm.use_auto_area"
                      :disabled="editForm.store_pickup"
                      class="mem-auto-inline"
                      title="仅勾选后保存才按已有坐标重算片区，不会改小区名或门牌"
                    >
                      自动划区
                    </el-checkbox>
                  </div>
                </div>
                <div class="mem-field">
                  <label class="mem-lab">业务起送日期</label>
                  <el-date-picker
                    v-model="editForm.delivery_start_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                    class="mem-date-picker"
                    clearable
                  />
                </div>
              </div>

              <div class="mem-chk-band">
                <el-checkbox v-model="editForm.delivery_deferred" class="mem-chk-el mem-chk-el--red">
                  暂停配送
                </el-checkbox>
                <el-checkbox
                  v-model="editForm.store_pickup"
                  :disabled="editForm.delivery_deferred"
                  class="mem-chk-el mem-chk-el--blue"
                >
                  门店自提
                </el-checkbox>
                <el-checkbox
                  v-model="editForm.skip_subscription_saturday"
                  class="mem-chk-el mem-chk-el--amber"
                >
                  周六不参与
                </el-checkbox>
                <el-tooltip placement="top">
                  <template #content>
                    <div class="mem-tip-body">
                      若会员今日已推单冻结且早上取消请假需补送，可点此强制写入当日配送大表；须先取消请假且会员符合配送条件。
                    </div>
                  </template>
                  <span class="mem-reinstate-wrap">
                    <button
                      type="button"
                      class="mem-reinstate-btn"
                      :disabled="reinstateBusy || editSaving"
                      @click="forceReinstateToDeliverySheet"
                    >
                      <Truck :size="14" aria-hidden="true" />
                      {{ reinstateBusy ? '加入中…' : '强制加入当天配送大表' }}
                    </button>
                  </span>
                </el-tooltip>
              </div>
            </section>

            <!-- 4. 备注：空时两行，有内容时最多三行 -->
            <section class="mem-sec">
              <div class="mem-sec-head">
                <span class="mem-bar" aria-hidden="true"></span>
                <h2 class="mem-sec-title">备注</h2>
              </div>
              <el-input
                v-model="editForm.remarks"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 3 }"
                maxlength="500"
                show-word-limit
                class="mem-input-el mem-ta-el"
                placeholder="请在此输入特别说明或客户需求..."
              />
            </section>
          </div>
        </div>

        <footer class="mem-ft">
          <div class="mem-ft-inner">
            <button type="submit" class="mem-btn mem-btn-primary" :disabled="editSaving || profileLoading">
              <Save :size="16" aria-hidden="true" />
              {{ profileLoading ? '同步档案中…' : editSaving ? '保存中…' : '确认并保存修改' }}
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
  font-family: var(--okfood-font-number);
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
  padding: 0.5rem 1.15rem;
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
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
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
  margin: 1px 0 0;
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
  padding: 0.7rem 1.15rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.mem-sec {
  flex-shrink: 0;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  padding: 0.7rem 0.9rem;
}

.mem-sec-head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
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

.mem-field {
  min-width: 0;
}

.mem-lab {
  display: flex;
  align-items: center;
  margin-bottom: 0.25rem;
  font-size: 0.7rem;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.mem-lab-inline {
  gap: 0.2rem;
}

.mem-tip-wrap {
  display: inline-flex;
  align-items: center;
  cursor: help;
  line-height: 1;
}

.mem-tip {
  flex-shrink: 0;
  color: #94a3b8;
}

.mem-tip-wrap:hover .mem-tip {
  color: #059669;
}

.mem-tip-body {
  max-width: 280px;
  line-height: 1.5;
  font-size: 12px;
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
  gap: 0.55rem 0.85rem;
}

.mem-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.55rem 0.85rem;
}

.mem-region-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.mem-region-row .mem-select-el {
  flex: 1;
  min-width: 0;
}

.mem-auto-inline {
  flex-shrink: 0;
  margin-right: 0 !important;
  white-space: nowrap;
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

.mem-affix--el-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.mem-affix-inp-el {
  flex: 1;
  min-width: 0;
}
.mem-affix-suf-el {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
}
.mem-input-el {
  width: 100%;
}
.mem-input-readonly :deep(.el-input__wrapper) {
  background: #f1f5f9;
}
.mem-select-el {
  width: 100%;
}
.mem-date-picker {
  width: 100%;
}
.mem-ta-el {
  width: 100%;
}

.mem-hint-soft {
  margin: 0.28rem 0 0;
  font-size: 10px;
  line-height: 1.4;
  color: #94a3b8;
}

.mem-chk-band {
  margin-top: 0.55rem;
  padding-top: 0.5rem;
  border-top: 1px solid #f1f5f9;
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem 0.85rem;
  align-items: center;
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

.mem-reinstate-wrap {
  display: inline-flex;
}

.mem-reinstate-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.28rem 0.62rem;
  border: 1px solid rgba(16, 185, 129, 0.45);
  border-radius: 8px;
  background: rgba(236, 253, 245, 0.85);
  color: #047857;
  font-size: 0.75rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.mem-reinstate-btn:hover:not(:disabled) {
  background: rgba(209, 250, 229, 0.95);
  border-color: rgba(16, 185, 129, 0.65);
}

.mem-reinstate-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
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
  height: 2.35rem;
  border-radius: 10px;
  font-weight: 800;
  font-size: 0.85rem;
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

  .mem-region-row {
    flex-wrap: wrap;
  }

  .mem-main-inner {
    padding-left: 0.75rem;
    padding-right: 0.75rem;
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
