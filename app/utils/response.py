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
    total: int,
    page: int = 1,
    page_size: int = 20,
    msg: str = "获取成功",
) -> dict[str, Any]:
    """分页列表成功响应。"""
    return success(
        data={"items": items, "total": total, "page": page, "page_size": page_size},
        msg=msg,
    )


def dump_model(model: BaseModel) -> dict[str, Any]:
    """将 Pydantic 模型转为 JSON 友好字典（枚举、日期等）。"""
    return model.model_dump(mode="json")
