import {
  isPaidCardAwaitingSetup,
  shouldPromptMemberCardPay,
} from '@/utils/memberProfile.js'

const CARD_LIST_URL = '/packageUser/pages/membershipCardList/membershipCardList'
const MEMBER_SETUP_PAY_URL = '/packageUser/pages/memberSetup/memberSetup?from=pay'

/**
 * 未开卡（剩余餐次为 0）时拦截请假、暂停配送、份数管理等自助履约操作。
 * @param {object | null | undefined} profile GET /api/user/me 的 data
 * @returns {boolean} true=可继续；false=已弹窗拦截
 */
export function guardMemberDeliverySelfService(profile) {
  if (!profile || typeof profile !== 'object') {
    promptBuyMemberCard()
    return false
  }
  if (isPaidCardAwaitingSetup(profile)) {
    promptCompleteMemberSetup()
    return false
  }
  if (shouldPromptMemberCardPay(profile)) {
    promptBuyMemberCard()
    return false
  }
  return true
}

function promptBuyMemberCard() {
  uni.showModal({
    title: '尚未开卡',
    content: '请假、暂停配送等功能需先购买自律卡包并开通计划。',
    confirmText: '去购卡',
    cancelText: '知道了',
    confirmColor: '#0e5a44',
    success: (res) => {
      if (!res.confirm) return
      uni.navigateTo({ url: CARD_LIST_URL })
    },
  })
}

function promptCompleteMemberSetup() {
  uni.showModal({
    title: '待完善配送',
    content: '您已购卡，请先完善配送信息后再使用请假、暂停配送等功能。',
    confirmText: '去设置',
    cancelText: '知道了',
    confirmColor: '#0e5a44',
    success: (res) => {
      if (!res.confirm) return
      uni.navigateTo({ url: MEMBER_SETUP_PAY_URL })
    },
  })
}
