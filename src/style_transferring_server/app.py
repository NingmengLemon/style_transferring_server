"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ExceptionHandler

from .config import ensure_runtime_dirs, settings
from .logging_config import configure_logging, get_logger
from .responses import (
    ApiError,
    api_error_handler,
    error_response,
    unhandled_error_handler,
)
from .schemas import (
    ErrorResponse,
    HealthData,
    HealthResponse,
    StyleItem,
    StylesData,
    StylesResponse,
    TransferResponse,
)
from .styles import style_registry
from .transfer import style_transfer_service

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时准备目录、预热风格索引并尝试加载/预热模型。"""

    ensure_runtime_dirs()
    logger.info(
        "server starting: host=%s port=%s device=%s",
        settings.host,
        settings.port,
        style_transfer_service.device,
    )
    _ = style_registry.styles
    try:
        style_transfer_service.load_model()
    except ApiError:
        # 模型加载失败不阻止服务启动，健康检查会如实反映，
        # 真实请求会返回约定的 3003 错误码。
        logger.error("model failed to load at startup; will retry on request")
    else:
        if settings.warmup:
            # 在后台线程预热，避免阻塞事件循环启动；
            # 消除首个真实请求的冷启动尖峰（cudnn autotune、显存分配）。
            await asyncio.to_thread(style_transfer_service.warmup)
    yield
    logger.info("server shutting down")


def create_app() -> FastAPI:
    """创建后端 HTTP 应用。"""

    configure_logging()
    app = FastAPI(
        title="个性化数字艺术创作系统后端",
        description="基于 FastAPI、PyTorch 和 VGG19 的图像风格迁移服务。",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "%s %s -> %d (%dms) [req=%s]",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(
        Exception, cast(ExceptionHandler, unhandled_error_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_error_handler)
    )
    ensure_runtime_dirs()
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @app.get(
        "/api/health",
        response_model=HealthResponse,
        responses={500: {"model": ErrorResponse}},
        summary="服务与模型状态检查",
    )
    async def health() -> HealthResponse | JSONResponse:
        # 模型尚未加载时先尝试加载一次，让健康检查能如实反映真实状态。
        if not style_transfer_service.model_loaded:
            try:
                style_transfer_service.load_model()
            except ApiError:
                # 加载失败：按契约返回 3003，供客户端在启动流程中感知故障。
                return error_response(3003, "model loading failed", 500)
        return HealthResponse(
            data=HealthData(
                status="running",
                model_loaded=style_transfer_service.model_loaded,
                device=str(style_transfer_service.device),
            )
        )

    @app.get(
        "/api/styles",
        response_model=StylesResponse,
        summary="获取可选风格列表",
    )
    async def styles() -> StylesResponse:
        items = [StyleItem(**item) for item in style_registry.list_for_api()]
        return StylesResponse(data=StylesData(styles=items))

    @app.post(
        "/api/style-transfer",
        response_model=TransferResponse,
        responses={
            400: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            415: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
        summary="执行图像风格迁移",
    )
    async def style_transfer(
        # 注意：范围/枚举校验交给业务层 validate_parameters 处理，
        # 以返回约定的 3002/3001 业务码，而非表单层的 1000。
        image: UploadFile = File(..., description="内容图像（jpg/jpeg/png）"),
        style_id: str = Form(..., description="风格 ID"),
        style_strength: int = Form(70, description="风格强度 0-100"),
        content_weight: int = Form(50, description="内容保留程度 0-100"),
        smoothness: int = Form(30, description="细节平滑程度 0-100"),
        quality: str = Form("fast", description="生成质量：fast/normal/hd"),
    ) -> TransferResponse:
        style = style_registry.get(style_id)
        if style is None:
            raise ApiError(3001, "style not found", 400)
        params = style_transfer_service.validate_parameters(
            style_strength, content_weight, smoothness, quality
        )
        data = await image.read()
        result = await style_transfer_service.transfer(
            data, image.filename or "upload.jpg", style, params
        )
        return TransferResponse(data=result)

    return app


async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    """将 FastAPI 表单校验错误映射为前端约定格式。"""

    return error_response(1000, "parameter error", 400)


app = create_app()
