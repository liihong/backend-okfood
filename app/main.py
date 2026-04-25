import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, admin_couriers, admin_regions, admin_uploads, courier, menu, user, wechat_pay
from app.core.config import settings
from app.core.limiter import limiter
from app.db.schema_patches import (
    apply_member_addresses_map_door_columns,
    apply_members_tomorrow_leave_target_column,
)
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler
from app.services.upload_service import ensure_upload_root
from app.utils.response import success

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _http_detail_to_msg(detail: str | list | dict) -> str:
    """将 HTTPException / 校验错误的 detail 转为前端可读文案。"""
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = item.get("loc")
                msg = item.get("msg")
                parts.append(f"{loc}: {msg}" if loc is not None else str(msg))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "请求无效"
    return str(detail)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    ensure_upload_root()
    apply_members_tomorrow_leave_target_column()
    apply_member_addresses_map_door_columns()
    setup_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user.router, prefix="/api")
app.include_router(wechat_pay.router, prefix="/api")
app.include_router(menu.router, prefix="/api")
app.include_router(courier.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_couriers.router, prefix="/api")
app.include_router(admin_regions.router, prefix="/api")
app.include_router(admin_uploads.router, prefix="/api")

static_root = settings.upload_dir_resolved
static_root.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_root)), name="static")


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    """限流触发时仍返回统一 {code, data, msg}。"""
    return JSONResponse(
        status_code=429,
        content={"code": 429, "data": None, "msg": "请求过于频繁，请稍后再试"},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """将业务层抛出的 HTTPException 转为统一 {code, data, msg}。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "data": None,
            "msg": _http_detail_to_msg(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """请求体验证失败时返回统一格式。"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "data": None,
            "msg": _http_detail_to_msg(exc.errors()),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """未捕获异常：记录日志并返回统一 500。"""
    _ = exc
    logger.exception("未处理的服务器错误")
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "msg": "服务器内部错误"},
    )


@app.get("/health")
def health():
    return success(data={"status": "ok"}, msg="服务正常")
