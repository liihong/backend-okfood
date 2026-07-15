"""统一 API 响应：所有接口返回 {code, data, msg}。"""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel


class ResponseCode(IntEnum):
    """200 表示成功；失败时 body 内 code 可与 HTTP 状态码一致。"""

    OK = 200


def success(*, data: Any = None, msg: str = "成功") -> dict[str, Any]:
    """构造成功响应。"""
    return {"code": int(ResponseCode.OK), "data": data, "msg": msg}


def fail(*, msg: str, code: int = 400) -> dict[str, Any]:
    """构造失败响应（需配合对应 HTTP 状态码返回时由路由层使用）。"""
    return {"code": code, "data": None, "msg": msg}


def page_response(
    *,
    items: Any,
    total: int | None,
    page: int = 1,
    page_size: int = 20,
    msg: str = "获取成功",
    summary: Any | None = None,
    has_more: bool | None = None,
) -> dict[str, Any]:
    """分页列表成功响应。可选 ``summary`` 附在 data 内；``total=None`` 表示未统计（客户端沿用缓存）。"""
    data: dict[str, Any] = {"items": items, "page": page, "page_size": page_size}
    if total is not None:
        data["total"] = total
    if has_more is not None:
        data["has_more"] = has_more
    if summary is not None:
        data["summary"] = summary
    return success(data=data, msg=msg)


def dump_model(model: BaseModel) -> dict[str, Any]:
    """将 Pydantic 模型转为 JSON 友好字典（枚举、日期等）。"""
    return model.model_dump(mode="json")
