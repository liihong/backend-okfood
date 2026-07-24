import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import admin, admin_catalog, admin_couriers, admin_douyin, admin_marketing, admin_regions, admin_retail_orders, admin_system, admin_uploads, catalog, courier, douyin_spi_notify, douyin_webhook_notify, home, menu, sf_open_notify, tenant, user, user_douyin, user_retail_orders, wechat_pay, wx_open_notify
from app.core.config import settings
from app.core.limiter import limiter
from app.jobs.scheduler import setup_scheduler, shutdown_scheduler
from app.services.shared.upload_service import ensure_upload_root
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


def _prewarm() -> None:
    """
    服务启动预热：
    1. 建立连接池（避免首请求 TCP 握手延迟）
    2. 触发循环依赖模块的首次 import（避免首请求 Python 模块解析延迟）
    3. 对核销舱高频表预热 InnoDB buffer pool

    任何异常不影响启动流程。
    """
    try:
        from sqlalchemy import text
        from app.db.session import SessionLocal

        db = SessionLocal()
        try:
            # 1. 建立连接池 + 验证 DB 可达
            db.execute(text("SELECT 1"))

            # 2. 预热 InnoDB buffer pool：核销舱涉及的核心表
            #    小数据量下这几张表全部进内存，后续查询直接命中缓存
            db.execute(text("SELECT id FROM members WHERE deleted_at IS NULL LIMIT 1"))
            db.execute(text("SELECT id FROM member_addresses WHERE is_default = 1 LIMIT 1"))
            db.execute(text("SELECT member_id FROM delivery_logs WHERE delivery_date >= CURDATE() - INTERVAL 7 DAY LIMIT 1"))
            db.execute(text("SELECT member_id FROM member_card_orders WHERE pay_status = 'paid' LIMIT 1"))
        finally:
            db.close()

        # 3. 触发循环依赖模块的首次 import，消除首请求模块解析开销
        import app.services.delivery.delivery_day_lock_service  # noqa: F401
        import app.services.delivery.delivery_sheet_push_snapshot_service  # noqa: F401
        import app.services.delivery.delivery_sheet_meal_units_service  # noqa: F401
        import app.services.member.member_card_order_service  # noqa: F401
        import app.services.admin.pickup_verification_service  # noqa: F401

        logger.info("DB 连接池与模块预热完成")
    except Exception:
        logger.warning("预热失败（不影响启动）", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    ensure_upload_root()
    setup_scheduler()
    _prewarm()
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
app.include_router(user_retail_orders.router, prefix="/api")
app.include_router(user_douyin.router, prefix="/api")
app.include_router(sf_open_notify.router_sf_callback, prefix="/api")
app.include_router(sf_open_notify.router_sf_oauth, prefix="/api")
app.include_router(douyin_spi_notify.router, prefix="/api")
app.include_router(douyin_webhook_notify.router, prefix="/api")
app.include_router(wechat_pay.router, prefix="/api")
app.include_router(menu.router, prefix="/api")
app.include_router(catalog.router, prefix="/api")
app.include_router(home.router, prefix="/api")
app.include_router(tenant.router, prefix="/api")
app.include_router(wx_open_notify.router, prefix="/api")
app.include_router(courier.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(admin_retail_orders.router, prefix="/api")
app.include_router(admin_catalog.router, prefix="/api")
app.include_router(admin_marketing.router, prefix="/api")
app.include_router(admin_douyin.router, prefix="/api")
app.include_router(admin_system.router, prefix="/api")
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
