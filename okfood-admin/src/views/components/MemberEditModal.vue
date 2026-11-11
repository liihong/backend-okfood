<script setup>
import { ref, watch, computed, onActivated } from 'vue'
import { Info, Truck } from 'lucide-vue-next'
import {
  apiJson,
  handleAdminLogout,
  mapAdminUserToRow,
  mealScopeLabelFromPeriods,
  membershipTemplatePlanLabel,
} from '../../admin/core.js'
import { showToast } from '../../composables/useToast.js'
import { confirmForceReinstateDelivery } from '../../composables/confirmForceReinstateDelivery.js'
import OkfoodAdminDialogShell from '../../components/OkfoodAdminDialogShell.vue'
import MemberOperationContext from '../../components/MemberOperationContext.vue'

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
/** 多张卡文案相同时不猜第一张，避免把「午餐包月」错绑成「一周午餐」 */
function uniqueTemplateId(hits) {
  if (!Array.isArray(hits) || hits.length !== 1 || hits[0]?.id == null) return null
  return Number(hits[0].id)
}

function matchMemberTemplate(templates, member) {
  const list = Array.isArray(templates) ? templates : []
  if (!list.length || !member) return null
  const planBase = String(member.planBase || member.plan_type || '').trim()
  const display = normalizePlanLabel(member.plan)
  const scope = mealScopeLabelFromPeriods(member.entitled_meal_periods)
  // 仅精确且唯一匹配，避免把「月卡 · 全餐」错配成另一张「月卡 · 午餐」
  if (display) {
    const byDisplay = uniqueTemplateId(
      list.filter((t) => normalizePlanLabel(membershipTemplatePlanLabel(t)) === display),
    )
    if (byDisplay != null) return byDisplay
  }
  const exact = uniqueTemplateId(
    list.filter((t) => {
      const kl = String(t.kind_label || '').trim()
      return kl === planBase && mealScopeLabelFromPeriods(t.meal_periods) === scope
    }),
  )
  if (exact != null) return exact
  return uniqueTemplateId(
    list.filter(
      (t) => planTypeFromTemplate(t) === planBase && mealScopeLabelFromPeriods(t.meal_periods) === scope,
    ),
  )
}

const open = defineModel('open', { type: Boolean, default: false })

const props = defineProps({
  /** mapAdminUserToRow 行；弹窗打开时应非空 */
  member: { type: Object, default: null },
  /** 与列表筛选一致：配送区域下拉 */
  regionOptions: { type: Array, default: () => [] },
})

const emit = defineEmits(['saved'])

/** 晚餐指定配送日说明：小屏收进 tooltip，桌面仍展示全文 */
const DINNER_SCHEDULE_HINT =
  '只影响晚餐日程，不改变上面的暂停配送。选择日期不会自动暂停。赠送晚餐默认暂停，指定某一天才进晚餐单；正式晚餐未暂停时仍按每天配送。'

const editSaving = ref(false)
const reinstateBusy = ref(false)
/** 打开编辑弹窗时的套餐类型，用于判断是否与档案一致、是否提交 plan_type */
const editInitialPlanType = ref('次卡')
/** 打开时选中的卡包模版 id；换模版即使仍是月卡也要提交，否则不落库、不写操作记录 */
const editInitialTemplateId = ref(CURRENT_PLAN_VALUE)
/** 打开时的片区，仅用户改片区或勾选自动划区时才提交，避免备注保存误写地址行 */
const editInitialDeliveryRegionId = ref('')
/** 打开时的晚餐暂停和指定日，只在有变化时提交，避免改姓名时误改晚餐日程 */
const editInitialDinnerPaused = ref(false)
const editInitialDinnerDeliverOn = ref('')
const profileLoading = ref(false)
/** 本店会员卡管理中的卡（含已下架），下拉按卡逐条列出，不再按餐段收成「午餐/晚餐」 */
const membershipTemplates = ref([])
const membershipTemplatesLoading = ref(false)
const editForm = ref({
  phone: '',
  name: '',
  remarks: '',
  plan_type: '次卡',
  membership_template_id: CURRENT_PLAN_VALUE,
  use_auto_area: false,
  delivery_start_date: '',
  store_pickup: false,
  skip_subscription_saturday: false,
  delivery_deferred: false,
  dinner_delivery_paused: false,
  dinner_deliver_on: '',
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

/** 会员卡管理里关掉上架的卡；档案仍可指定，小程序开卡不行 */
function templateIsOffShelf(tpl) {
  return tpl?.is_active === false || tpl?.is_active === 0
}

/** 下拉只显示会员卡管理里的种类简称，不拼卡片全名和餐段 */
function templateSelectLabel(tpl) {
  return String(tpl?.kind_label || '').trim() || String(tpl?.name || '').trim() || '会员卡'
}

/** 会员卡管理中的每一张卡 → 下拉一项（含已下架，便于指定全餐） */
const planOptions = computed(() => {
  const opts = []
  for (const t of membershipTemplates.value) {
    const id = Number(t?.id)
    if (!Number.isFinite(id) || id <= 0) continue
    opts.push({ id, label: templateSelectLabel(t), planType: planTypeFromTemplate(t) })
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

/** 选中已下架卡时说明：档案仍按其餐段更新，小程序开卡不受影响 */
const selectedShelfHint = computed(() => {
  const id = editForm.value.membership_template_id
  if (id == null || id === CURRENT_PLAN_VALUE) return ''
  const tpl = membershipTemplates.value.find((t) => Number(t.id) === Number(id))
  if (!tpl || !templateIsOffShelf(tpl)) return ''
  const scope = mealScopeLabelFromPeriods(tpl.meal_periods)
  return `这张卡已在会员卡管理下架，保存后仍按「${scope}」更新该会员的餐段，不改剩余次数。`
})

watch(planOptions, (opts) => {
  if (editForm.value.membership_template_id !== CURRENT_PLAN_VALUE) return
  const currentLabel =
    (props.member?.plan && String(props.member.plan).trim()) ||
    String(editForm.value.plan_type || '').trim()
  const currentNorm = normalizePlanLabel(currentLabel)
  const hits = opts.filter(
    (o) => o.id !== CURRENT_PLAN_VALUE && normalizePlanLabel(o.label) === currentNorm,
  )
  const hit = hits.length === 1 ? hits[0] : null
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
    const data = await apiJson('/api/admin/catalog/membership-templates', {}, { auth: true })
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
  editInitialDeliveryRegionId.value = dr
  editInitialDinnerPaused.value = u.dinner_delivery_paused === true
  editInitialDinnerDeliverOn.value = typeof u.dinner_deliver_on === 'string' ? u.dinner_deliver_on.slice(0, 10) : ''
  editForm.value = {
    phone: u.phone,
    name: u.name || '',
    remarks: u.remarks || '',
    plan_type: p0,
    membership_template_id: matchedId != null ? matchedId : CURRENT_PLAN_VALUE,
    use_auto_area: false,
    delivery_start_date:
      typeof u.delivery_start_date === 'string' && u.delivery_start_date.trim()
        ? u.delivery_start_date.trim().slice(0, 10)
        : '',
    store_pickup: u.store_pickup === true,
    skip_subscription_saturday: u.skip_subscription_saturday === true,
    delivery_deferred: u.delivery_deferred === true,
    dinner_delivery_paused: u.dinner_delivery_paused === true,
    dinner_deliver_on:
      typeof u.dinner_deliver_on === 'string' && u.dinner_deliver_on.trim()
        ? u.dinner_deliver_on.trim().slice(0, 10)
        : '',
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

/** 标签页 keep-alive 切回且弹窗仍打开时，同步姓名、套餐、配送等档案字段 */
onActivated(() => {
  if (open.value && props.member) void refreshMemberFormFromServer(props.member)
})

function close() {
  if (editSaving.value || profileLoading.value) return
  open.value = false
}

/** 是否展示晚餐配送安排（有晚餐权益、余次、暂停或指定配送日） */
function showDinnerScheduleFor(u) {
  if (!u) return false
  const periods = Array.isArray(u.entitled_meal_periods) ? u.entitled_meal_periods : []
  if (periods.includes('dinner')) return true
  if ((Number(u.dinner_balance) || 0) > 0) return true
  if (u.dinner_delivery_paused === true) return true
  if (String(u.dinner_deliver_on || '').trim()) return true
  return false
}

const showDinnerSchedule = computed(() => showDinnerScheduleFor(props.member))

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
  const ok = await confirmForceReinstateDelivery(u, periodLabel)
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
    const payload = {
      phone: editForm.value.phone,
      name: editForm.value.name.trim(),
      remarks: editForm.value.remarks.trim() || null,
      delivery_start_date: String(editForm.value.delivery_start_date ?? '').trim()
        ? String(editForm.value.delivery_start_date).trim().slice(0, 10)
        : null,
      store_pickup: isStorePickup,
      skip_subscription_saturday: editForm.value.skip_subscription_saturday === true,
      delivery_deferred: editForm.value.delivery_deferred === true,
    }
    // 晚餐暂停和指定配送日分开提交。只改日期不会把暂停勾上，也不改上面的整体暂停。
    if (showDinnerSchedule.value) {
      if (editForm.value.dinner_delivery_paused !== editInitialDinnerPaused.value) {
        payload.dinner_delivery_paused = editForm.value.dinner_delivery_paused === true
      }
      const nextDinnerDate = String(editForm.value.dinner_deliver_on ?? '').trim().slice(0, 10)
      const prevDinnerDate = String(editInitialDinnerDeliverOn.value ?? '').trim().slice(0, 10)
      if (nextDinnerDate !== prevDinnerDate) {
        payload.dinner_deliver_on = nextDinnerDate || null
      }
    }
    // 剩余次数、晚餐次数、每配送日份数不在本弹窗提交，避免改姓名/配送时误写余额或份数
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
    open.value = false
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
  <OkfoodAdminDialogShell
    v-model:open="open"
    title="修改会员信息"
    subtitle="地址请在「地址」入口单独维护 · 次数在「修改次数」"
    size="wide"
    fit-content
    dlg-class="okfood-admin-dlg--edit-fit"
    :close-disabled="editSaving || profileLoading"
    :close-on-backdrop="!editSaving && !profileLoading"
    @close="close"
  >
    <template v-if="member" #operation-context>
      <MemberOperationContext :name="member.name" :phone="member.phone" :plan="member.plan" />
    </template>
    <div v-loading="profileLoading" class="okfood-mem-edit-inner">
      <section class="okfood-mem-edit-sec">
        <div class="okfood-mem-edit-sec-head">
          <span class="okfood-mem-edit-bar" aria-hidden="true"></span>
          <h3 class="okfood-mem-edit-sec-title">档案与套餐</h3>
        </div>
        <div class="okfood-mem-edit-grid-3">
          <div class="okfood-mem-edit-field">
            <label class="okfood-mem-edit-lab">会员手机号</label>
            <el-input
              class="okfood-mem-edit-input okfood-mem-edit-input--ro"
              :model-value="editForm.phone"
              disabled
            />
          </div>
          <div class="okfood-mem-edit-field">
            <label class="okfood-mem-edit-lab">姓名</label>
            <el-input
              v-model="editForm.name"
              maxlength="100"
              placeholder="请输入姓名"
              clearable
              class="okfood-mem-edit-input"
            />
          </div>
          <div class="okfood-mem-edit-field">
            <label class="okfood-mem-edit-lab">本店会员卡</label>
            <el-select
              v-model="editForm.membership_template_id"
              class="okfood-mem-edit-input"
              :loading="membershipTemplatesLoading"
              filterable
              :fit-input-width="false"
              :placeholder="
                membershipTemplatesLoading
                  ? '加载本店会员卡…'
                  : planOptions.length
                    ? '请选择本店会员卡'
                    : '暂无会员卡'
              "
            >
              <el-option
                v-for="opt in planOptions"
                :key="String(opt.id)"
                :label="opt.label"
                :value="opt.id"
              />
            </el-select>
            <p v-if="selectedShelfHint" class="okfood-mem-edit-hint-soft">
              {{ selectedShelfHint }}
            </p>
          </div>
        </div>
        <p
          v-if="!membershipTemplatesLoading && !membershipTemplates.length"
          class="okfood-mem-edit-hint-soft okfood-mem-edit-hint-soft--full"
        >
          暂无会员卡，请先在「会员卡管理」中创建。
        </p>
      </section>

      <section class="okfood-mem-edit-sec">
        <div class="okfood-mem-edit-sec-head">
          <span class="okfood-mem-edit-bar" aria-hidden="true"></span>
          <h3 class="okfood-mem-edit-sec-title">配送与时间设置</h3>
        </div>

        <div
          class="okfood-mem-edit-delivery-grid"
          :class="{ 'okfood-mem-edit-delivery-grid--dinner': showDinnerSchedule }"
        >
          <div class="okfood-mem-edit-field okfood-mem-edit-field--region">
            <div class="okfood-mem-edit-lab-row">
              <label class="okfood-mem-edit-lab okfood-mem-edit-lab--inline">
                配送片区
                <el-tooltip placement="top">
                  <template #content>
                    <div class="okfood-mem-edit-tip-body">{{ autoAreaHintText }}</div>
                  </template>
                  <span class="okfood-mem-edit-lab-tip-wrap">
                    <Info class="okfood-mem-edit-lab-tip" :size="13" />
                  </span>
                </el-tooltip>
              </label>
              <el-checkbox
                v-model="editForm.use_auto_area"
                :disabled="editForm.store_pickup"
                class="okfood-mem-edit-auto-inline"
                title="仅勾选后保存才按已有坐标重算片区，不会改小区名或门牌"
              >
                自动划区
              </el-checkbox>
            </div>
            <el-select
              v-model="editForm.delivery_region_id"
              class="okfood-mem-edit-input okfood-mem-edit-region-select"
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
          </div>
          <div class="okfood-mem-edit-field">
            <label class="okfood-mem-edit-lab">业务起送日期</label>
            <el-date-picker
              v-model="editForm.delivery_start_date"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="选择日期"
              class="okfood-mem-edit-input okfood-mem-edit-date"
              clearable
            />
          </div>
          <div v-if="showDinnerSchedule" class="okfood-mem-edit-field">
            <label class="okfood-mem-edit-lab">
              晚餐指定配送日
              <el-tooltip placement="top">
                <template #content>
                  <div class="okfood-mem-edit-tip-body">{{ DINNER_SCHEDULE_HINT }}</div>
                </template>
                <span class="okfood-mem-edit-dinner-hint-trigger" tabindex="0" aria-label="晚餐指定配送日说明">
                  <Info class="okfood-mem-edit-lab-tip" :size="13" />
                </span>
              </el-tooltip>
            </label>
            <el-date-picker
              v-model="editForm.dinner_deliver_on"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="不指定"
              class="okfood-mem-edit-input okfood-mem-edit-date"
              clearable
            />
          </div>
        </div>
        <p
          v-if="showDinnerSchedule"
          class="okfood-mem-edit-dinner-hint okfood-mem-edit-dinner-hint--desk"
        >
          {{ DINNER_SCHEDULE_HINT }}
        </p>

        <div class="okfood-mem-edit-chk-band okfood-mem-edit-chk-band--one-row">
          <el-checkbox
            v-model="editForm.store_pickup"
            :disabled="editForm.delivery_deferred"
            class="okfood-mem-edit-chk-el okfood-mem-edit-chk-el--blue"
          >
            门店自提
          </el-checkbox>
          <el-checkbox
            v-model="editForm.delivery_deferred"
            class="okfood-mem-edit-chk-el okfood-mem-edit-chk-el--red"
          >
            暂停配送
          </el-checkbox>
          <el-checkbox
            v-if="showDinnerSchedule"
            v-model="editForm.dinner_delivery_paused"
            class="okfood-mem-edit-chk-el okfood-mem-edit-chk-el--red"
          >
            暂停晚餐
          </el-checkbox>
          <el-checkbox
            v-model="editForm.skip_subscription_saturday"
            class="okfood-mem-edit-chk-el okfood-mem-edit-chk-el--amber"
          >
            周六不参与
          </el-checkbox>
          <el-tooltip placement="top">
            <template #content>
              <div class="okfood-mem-edit-tip-body">
                若会员今日已推单冻结且早上取消请假需补送，可点此强制写入当日配送大表；须先取消请假且会员符合配送条件。
              </div>
            </template>
            <span class="okfood-mem-edit-reinstate-wrap">
              <button
                type="button"
                class="okfood-mem-edit-reinstate-btn"
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

      <section class="okfood-mem-edit-sec">
        <div class="okfood-mem-edit-sec-head">
          <span class="okfood-mem-edit-bar" aria-hidden="true"></span>
          <h3 class="okfood-mem-edit-sec-title">备注</h3>
        </div>
        <el-input
          v-model="editForm.remarks"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 3 }"
          maxlength="500"
          show-word-limit
          class="okfood-mem-edit-input okfood-mem-edit-ta"
          placeholder="请在此输入特别说明或客户需求..."
        />
      </section>
    </div>
    <template #footer>
      <el-button round :disabled="editSaving" @click="close">取消</el-button>
      <el-button
        round
        type="primary"
        :loading="editSaving"
        :disabled="profileLoading"
        @click="submitEditMember"
      >
        {{ profileLoading ? '同步档案中…' : '确认并保存修改' }}
      </el-button>
    </template>
  </OkfoodAdminDialogShell>
</template>
