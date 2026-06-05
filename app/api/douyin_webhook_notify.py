"""抖音生活服务 Webhooks（无 JWT；verify_webhook 回显 challenge）。"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.core.deps import SessionDep
from app.services.douyin.webhook_service import process_douyin_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/douyin", tags=["抖音 Webhooks"])


@router.post("/webhook")
async def douyin_webhook(request: Request, db: SessionDep):
    """Webhooks 请求网址：保存时平台 POST verify_webhook，需回显 challenge。"""
    raw = await request.body()
    signature = request.headers.get("X-Douyin-Signature") or request.headers.get("x-douyin-signature")
    try:
        status_code, body = process_douyin_webhook(db, raw, signature=signature)
    except Exception:
        logger.exception("抖音 Webhook 处理异常")
        return Response(status_code=500, content="internal error", media_type="text/plain")

    if body is not None:
        # 平台要求 ResponseBody 为 text 格式 JSON
        return Response(
            status_code=status_code,
            content=json.dumps(body, ensure_ascii=False),
            media_type="text/plain",
        )
    if status_code >= 400:
        return Response(status_code=status_code, content="fail", media_type="text/plain")
    return JSONResponse(status_code=200, content={})
