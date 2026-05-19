"""SQL LIKE 用户输入转义，避免 % _ 扩大匹配范围。"""


def escape_like_fragment(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
