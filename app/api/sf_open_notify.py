"""顺丰同城开放平台 HTTP 推送（无 JWT；验签依赖 SF_OPEN_DEV_ID + SF_OPEN_SECRET）。

路由与蜂巢控制台配置一致：/api/sf/callback/*、/api/sf/oauth/*。
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.deps import SessionDep
from app.services.sf_callback_service import persist_oauth_style_callback, process_sf_notify

logger = logging.getLogger(__name__)

router_sf_callback = APIRouter(prefix="/sf/callback", tags=["顺丰同城回调"])
router_sf_oauth = APIRouter(prefix="/sf/oauth", tags=["顺丰同城授权回调"])


def _sf_json_ok() -> JSONResponse:
    return JSONResponse(content={"error_code": 0, "error_msg": "success"})


def _sf_json_err(msg: str, code: int = 500) -> JSONResponse:
    """顺丰侧通常以 HTTP 200 + body 内 error_code 表示业务失败，避免平台无限重试。"""
    return JSONResponse(status_code=200, content={"error_code": code, "error_msg": msg})


async def _read_body_async(request: Request) -> str:
    raw = await request.body()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="replace")


def _pick_sign(request: Request, query_sign: str | None) -> str | None:
    """顺丰约定：sign 在 URL Query；兼容大小写别名。须保证网关把 ?sign= 原样转到后端。"""
    for s in (
        (query_sign or "").strip(),
        (request.query_params.get("sign") or "").strip(),
        (request.query_params.get("Sign") or "").strip(),
        (request.query_params.get("signature") or "").strip(),
    ):
        if s:
            return s
    return None


async def _dispatch_sf_notify(
    request: Request,
    db: SessionDep,
    route_kind: str,
    *,
    log_tag: str,
    sign: str | None,
) -> JSONResponse:
    raw = await _read_body_async(request)
    eff_sign = _pick_sign(request, sign)
    logger.info("顺丰回调 %s len=%s sign_in_query=%s", log_tag, len(raw), bool(eff_sign))
    ok, err = process_sf_notify(db=db, route_kind=route_kind, raw_body=raw, sign_query=eff_sign)
    if not ok:
        logger.warning(
            "顺丰回调业务校验未通过(响应体 error_code≠0，蜂巢常判为失败): tag=%s err=%s query_param_keys=%s",
            log_tag,
            err,
            list(dict.fromkeys(request.query_params.keys())),
        )
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router_sf_callback.post("/delivery-status")
async def sf_callback_delivery_status(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    """配送状态更改。"""
    return await _dispatch_sf_notify(
        request, db, "delivery_status", log_tag="delivery-status", sign=sign
    )


@router_sf_callback.post("/order-completed")
async def sf_callback_order_completed(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    """订单完成（控制台路径为 order-completed）。"""
    return await _dispatch_sf_notify(
        request, db, "order_complete", log_tag="order-completed", sign=sign
    )


@router_sf_callback.post("/cancel-by-sf")
async def sf_callback_cancel_by_sf(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    return await _dispatch_sf_notify(
        request, db, "cancel_by_sf", log_tag="cancel-by-sf", sign=sign
    )


@router_sf_callback.post("/delivery-exception")
async def sf_callback_delivery_exception(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    return await _dispatch_sf_notify(
        request, db, "delivery_exception", log_tag="delivery-exception", sign=sign
    )


@router_sf_callback.post("/rider-cancel")
async def sf_callback_rider_cancel(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    return await _dispatch_sf_notify(
        request, db, "rider_cancel", log_tag="rider-cancel", sign=sign
    )


@router_sf_callback.post("/auto-shop")
async def sf_callback_auto_shop(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    return await _dispatch_sf_notify(request, db, "auto_shop", log_tag="auto-shop", sign=sign)


@router_sf_oauth.get("/callback")
def sf_oauth_callback_get(request: Request, db: SessionDep):
    q = dict(request.query_params)
    persist_oauth_style_callback(db, route_kind="oauth_callback", query_params=q, raw_body="")
    return _sf_json_ok()


@router_sf_oauth.post("/callback")
async def sf_oauth_callback_post(request: Request, db: SessionDep):
    q = dict(request.query_params)
    raw = await _read_body_async(request)
    persist_oauth_style_callback(db, route_kind="oauth_callback", query_params=q, raw_body=raw)
    return _sf_json_ok()


@router_sf_oauth.get("/revoke")
def sf_oauth_revoke_get(request: Request, db: SessionDep):
    q = dict(request.query_params)
    persist_oauth_style_callback(db, route_kind="oauth_revoke", query_params=q, raw_body="")
    return _sf_json_ok()


@router_sf_oauth.post("/revoke")
async def sf_oauth_revoke_post(request: Request, db: SessionDep):
    q = dict(request.query_params)
    raw = await _read_body_async(request)
    persist_oauth_style_callback(db, route_kind="oauth_revoke", query_params=q, raw_body=raw)
    return _sf_json_ok()
