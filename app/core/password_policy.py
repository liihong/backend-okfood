"""管理员密码强度策略（安全审计：至少 8 位，四类字符中至少含 3 类）。"""

from __future__ import annotations

import re

PASSWORD_MIN_LENGTH = 8
PASSWORD_POLICY_MSG = (
    "密码至少 8 位，且须包含大写字母、小写字母、数字、特殊字符中的至少 3 种"
)


def password_complexity_score(password: str) -> int:
    score = 0
    if re.search(r"[A-Z]", password):
        score += 1
    if re.search(r"[a-z]", password):
        score += 1
    if re.search(r"\d", password):
        score += 1
    if re.search(r"[^\w\s]", password):
        score += 1
    return score


def validate_password_strength(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH or password_complexity_score(password) < 3:
        raise ValueError(PASSWORD_POLICY_MSG)
