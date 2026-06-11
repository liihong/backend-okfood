import { inject } from 'vue'
import { ORDERS_MANAGE_KEY } from '../constants.js'

/** 子组件注入订单管理上下文 */
export function useOrdersManageInject() {
  const ctx = inject(ORDERS_MANAGE_KEY)
  if (!ctx) {
    throw new Error('useOrdersManageInject 必须在 OrdersManageView 内使用')
  }
  return ctx
}
