/** 管理员密码强度策略（与后端 app/core/password_policy.py 一致） */
export const PASSWORD_POLICY_MSG =
  '密码至少 8 位，且须包含大写字母、小写字母、数字、特殊字符中的至少 3 种'

export function passwordComplexityScore(password) {
  let score = 0
  if (/[A-Z]/.test(password)) score += 1
  if (/[a-z]/.test(password)) score += 1
  if (/\d/.test(password)) score += 1
  if (/[^\w\s]/.test(password)) score += 1
  return score
}

export function isPasswordStrongEnough(password) {
  const pwd = String(password ?? '')
  return pwd.length >= 8 && passwordComplexityScore(pwd) >= 3
}
