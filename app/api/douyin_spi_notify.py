"""抖音生活服务 SPI 回调（无 JWT；验签依赖 client_key + client_secret）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.deps import SessionDep
from app.services.douyin.spi_callback_service import (
    douyin_spi_json,
    process_douyin_async_cancel_fulfil_notify,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/douyin/spi", tags=["抖音 SPI 回调"])


@router.post("/async-cancel-fulfil")
async def douyin_spi_async_cancel_fulfil(request: Request, db: SessionDep):
    """券撤销核销 / 跨单撤销核销异步回调（cert.fulfil.async_cancel_fulfil）。"""
    raw = await request.body()
    query_params = {k: v for k, v in request.query_params.multi_items()}
    header_client_key = request.headers.get("x-life-clientkey") or request.headers.get("X-Life-Clientkey")
    header_sign = request.headers.get("x-life-sign") or request.headers.get("X-Life-Sign")
    try:
        error_code, description = process_douyin_async_cancel_fulfil_notify(
            db,
            raw_body=raw,
            query_params=query_params,
            header_client_key=header_client_key,
            header_sign=header_sign,
        )
    except Exception:
        logger.exception("抖音 SPI 撤销核销回调处理异常")
        db.rollback()
        return JSONResponse(status_code=200, content=douyin_spi_json(error_code=2100001, description="internal error"))
    return JSONResponse(status_code=200, content=douyin_spi_json(error_code=error_code, description=description))
