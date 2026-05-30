"""顺丰推单失败文案：管理端展示用，避免原始错误码/「超时」等误导表述。"""

from __future__ import annotations

# 顺丰开放平台常见：预付费账户余额不足
SF_ERROR_BALANCE_INSUFFICIENT = 3302

MSG_BALANCE_INSUFFICIENT = (
    "顺丰预付费账户余额不足，请登录顺丰同城商户后台充值后再推单"
)
MSG_PUSH_BUSY = "当前有推单任务进行中，请稍候几秒再试"
MSG_SKIPPED_AFTER_BALANCE = (
    "顺丰账户余额不足，本条未向顺丰发起推单；充值后请重试"
)


def is_sf_balance_insufficient(*, error_code: int | None, message: str | None = None) -> bool:
    """是否为顺丰预付费余额不足（按错误码或原文关键词判断）。"""
    if error_code == SF_ERROR_BALANCE_INSUFFICIENT:
        return True
    m = (message or "").strip()
    if not m:
        return False
    return any(k in m for k in ("余额不足", "预付费", "请及时充值"))


def sf_push_user_message(*, error_code: int | None, message: str | None = None) -> str:
    """将顺丰/系统原始错误转为管理端可读提示。"""
    if is_sf_balance_insufficient(error_code=error_code, message=message):
        return MSG_BALANCE_INSUFFICIENT
    raw = (message or "").strip()
    if raw:
        return raw[:500]
    if error_code is not None and int(error_code) >= 0:
        return f"顺丰创单失败（错误码 {int(error_code)}）"
    return "顺丰创单失败"


def classify_sf_push_exception(exc: BaseException) -> tuple[int, str, str]:
    """
    解析推单 HTTP 异常，返回 (error_code, raw_message, user_message)。
    """
    from app.services.sf_open.client import SfOpenApiError

    if isinstance(exc, SfOpenApiError):
        ec = int(exc.error_code) if exc.error_code is not None else -1
        raw = str(exc)[:1000]
        return ec, raw, sf_push_user_message(error_code=ec, message=raw)
    raw = str(exc)[:1000]
    return -2, raw, sf_push_user_message(error_code=-2, message=raw)
