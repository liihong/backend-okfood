"""顺丰同城开放平台 HTTP 推送（无 JWT；验签依赖 SF_OPEN_DEV_ID + SF_OPEN_SECRET）。"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.core.deps import SessionDep
from app.services.sf_callback_service import persist_oauth_style_callback, process_sf_notify

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sf-open", tags=["顺丰同城回调"])


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


@router.post("/notify/delivery-status")
async def sf_notify_delivery_status(
    request: Request,
    db: SessionDep,
    sign: Annotated[str | None, Query()] = None,
):
    """配送状态更改（例：order_status 10/12/15 等）。顺丰需在控制台填本 URL。"""
    raw = await _read_body_async(request)
    logger.info("顺丰回调 delivery-status len=%s sign=%s", len(raw), bool(sign))
    ok, err = process_sf_notify(db=db, route_kind="delivery_status", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.post("/notify/order-complete")
async def sf_notify_order_complete(request: Request, db: SessionDep, sign: Annotated[str | None, Query()] = None):
    raw = await _read_body_async(request)
    logger.info("顺丰回调 order-complete len=%s", len(raw))
    ok, err = process_sf_notify(db=db, route_kind="order_complete", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.post("/notify/cancel-by-sf")
async def sf_notify_cancel_by_sf(request: Request, db: SessionDep, sign: Annotated[str | None, Query()] = None):
    raw = await _read_body_async(request)
    ok, err = process_sf_notify(db=db, route_kind="cancel_by_sf", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.post("/notify/delivery-exception")
async def sf_notify_delivery_exception(request: Request, db: SessionDep, sign: Annotated[str | None, Query()] = None):
    raw = await _read_body_async(request)
    ok, err = process_sf_notify(db=db, route_kind="delivery_exception", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.post("/notify/rider-cancel")
async def sf_notify_rider_cancel(request: Request, db: SessionDep, sign: Annotated[str | None, Query()] = None):
    raw = await _read_body_async(request)
    ok, err = process_sf_notify(db=db, route_kind="rider_cancel", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.post("/notify/auto-shop")
async def sf_notify_auto_shop(request: Request, db: SessionDep, sign: Annotated[str | None, Query()] = None):
    raw = await _read_body_async(request)
    ok, err = process_sf_notify(db=db, route_kind="auto_shop", raw_body=raw, sign_query=sign)
    if not ok:
        return _sf_json_err(err or "reject", 500)
    return _sf_json_ok()


@router.get("/oauth/callback")
def sf_oauth_callback_get(request: Request, db: SessionDep):
    q = dict(request.query_params)
    persist_oauth_style_callback(db, route_kind="oauth_callback", query_params=q, raw_body="")
    return _sf_json_ok()


@router.post("/oauth/callback")
async def sf_oauth_callback_post(request: Request, db: SessionDep):
    q = dict(request.query_params)
    raw = await _read_body_async(request)
    persist_oauth_style_callback(db, route_kind="oauth_callback", query_params=q, raw_body=raw)
    return _sf_json_ok()


@router.get("/oauth/revoke")
def sf_oauth_revoke_get(request: Request, db: SessionDep):
    q = dict(request.query_params)
    persist_oauth_style_callback(db, route_kind="oauth_revoke", query_params=q, raw_body="")
    return _sf_json_ok()


@router.post("/oauth/revoke")
async def sf_oauth_revoke_post(request: Request, db: SessionDep):
    q = dict(request.query_params)
    raw = await _read_body_async(request)
    persist_oauth_style_callback(db, route_kind="oauth_revoke", query_params=q, raw_body=raw)
    return _sf_json_ok()
