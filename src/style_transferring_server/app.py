"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import ExceptionHandler

from .config import ensure_runtime_dirs, settings
from .constants import (
    DEFAULT_QUALITY,
    MILLISECONDS_PER_SECOND,
    REQUEST_ID_HEX_LENGTH,
    ApiPath,
    ErrorCode,
    HttpStatus,
    TransferDefault,
)
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
    TransferParameters,
    TransferResponse,
)
from .styles import style_registry
from .transfer import style_transfer_service

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """启动时准备目录、预热风格索引并尝试加载/预热模型。"""

    logger.info("startup step: ensuring runtime directories")
    ensure_runtime_dirs()
    logger.info(
        "server starting: host=%s port=%s device=%s static_dir=%s results_dir=%s wikiart_dir=%s",
        settings.host,
        settings.port,
        style_transfer_service.device,
        settings.static_dir,
        settings.results_dir,
        settings.wikiart_dir,
    )
    logger.info("startup step: loading style registry")
    _ = style_registry.styles
    logger.info("startup step: loading model")
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
            logger.info("startup step: warming up model")
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
    async def log_requests(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = uuid.uuid4().hex[:REQUEST_ID_HEX_LENGTH]
        request.state.request_id = request_id
        start = time.perf_counter()
        logger.info(
            "request received: method=%s path=%s query=%s client=%s content_type=%s content_length=%s req=%s",
            request.method,
            request.url.path,
            request.url.query or "-",
            request.client.host if request.client else "-",
            request.headers.get("content-type", "-"),
            request.headers.get("content-length", "-"),
            request_id,
        )
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = int((time.perf_counter() - start) * MILLISECONDS_PER_SECOND)
            logger.exception(
                "request failed before response: method=%s path=%s time_ms=%d req=%s",
                request.method,
                request.url.path,
                elapsed_ms,
                request_id,
            )
            raise
        elapsed_ms = int((time.perf_counter() - start) * MILLISECONDS_PER_SECOND)
        logger.info(
            "request completed: method=%s path=%s status=%d time_ms=%d req=%s",
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
    app.mount(
        ApiPath.STATIC_PREFIX,
        StaticFiles(directory=settings.static_dir),
        name="static",
    )

    @app.get(
        ApiPath.HEALTH,
        response_model=HealthResponse,
        responses={500: {"model": ErrorResponse}},
        summary="服务与模型状态检查",
    )
    async def health(request: Request) -> HealthResponse | JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "health check started: model_loaded=%s device=%s req=%s",
            style_transfer_service.model_loaded,
            style_transfer_service.device,
            request_id,
        )
        # 模型尚未加载时先尝试加载一次，让健康检查能如实反映真实状态。
        if not style_transfer_service.model_loaded:
            logger.info("health check loading model on demand: req=%s", request_id)
            try:
                style_transfer_service.load_model()
            except ApiError:
                # 加载失败：按契约返回 3003，供客户端在启动流程中感知故障。
                return error_response(
                    ErrorCode.MODEL_LOADING_FAILED,
                    "model loading failed",
                    HttpStatus.INTERNAL_SERVER_ERROR,
                )
        response = HealthResponse(
            data=HealthData(
                status="running",
                model_loaded=style_transfer_service.model_loaded,
                device=str(style_transfer_service.device),
            )
        )
        logger.info(
            "health check completed: model_loaded=%s device=%s req=%s",
            response.data.model_loaded,
            response.data.device,
            request_id,
        )
        return response

    @app.get(
        ApiPath.STYLES,
        response_model=StylesResponse,
        summary="获取可选风格列表",
    )
    async def styles(request: Request) -> StylesResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.info("styles endpoint started: req=%s", request_id)
        items = [StyleItem(**item) for item in style_registry.list_for_api()]
        logger.info(
            "styles endpoint completed: count=%d req=%s", len(items), request_id
        )
        return StylesResponse(data=StylesData(styles=items))

    @app.post(
        ApiPath.STYLE_TRANSFER,
        response_model=TransferResponse,
        responses={
            HttpStatus.BAD_REQUEST: {"model": ErrorResponse},
            HttpStatus.PAYLOAD_TOO_LARGE: {"model": ErrorResponse},
            HttpStatus.UNSUPPORTED_MEDIA_TYPE: {"model": ErrorResponse},
            HttpStatus.INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
            HttpStatus.SERVICE_UNAVAILABLE: {"model": ErrorResponse},
            HttpStatus.GATEWAY_TIMEOUT: {"model": ErrorResponse},
        },
        summary="执行图像风格迁移",
    )
    async def style_transfer(
        request: Request,
        # 注意：范围/枚举校验交给业务层 validate_parameters 处理，
        # 以返回约定的 3002/3001 业务码，而非表单层的 1000。
        image: UploadFile = File(..., description="内容图像（jpg/jpeg/png）"),
        style_id: str = Form(..., description="风格 ID"),
        style_strength: int = Form(
            TransferDefault.STYLE_STRENGTH,
            description="风格强度 0-100",
        ),
        content_weight: int = Form(
            TransferDefault.CONTENT_WEIGHT,
            description="内容保留程度 0-100",
        ),
        smoothness: int = Form(
            TransferDefault.SMOOTHNESS,
            description="细节平滑程度 0-100",
        ),
        quality: str = Form(DEFAULT_QUALITY, description="生成质量：fast/normal/hd"),
    ) -> TransferResponse:
        request_id = getattr(request.state, "request_id", "-")
        filename = image.filename or "upload.jpg"
        logger.info(
            "style-transfer endpoint started: style_id=%s filename=%s content_type=%s params=(%d,%d,%d,%s) req=%s",
            style_id,
            filename,
            image.content_type or "-",
            style_strength,
            content_weight,
            smoothness,
            quality,
            request_id,
        )
        style = style_registry.get(style_id)
        if style is None:
            logger.warning(
                "style-transfer rejected: style not found style_id=%s req=%s",
                style_id,
                request_id,
            )
            raise ApiError(
                ErrorCode.STYLE_NOT_FOUND,
                "style not found",
                HttpStatus.BAD_REQUEST,
            )
        logger.info(
            "style-transfer style resolved: style_id=%s artist=%s image_path=%s req=%s",
            style.style_id,
            style.artist,
            style.image_path,
            request_id,
        )
        params = TransferParameters.from_form_values(
            style_strength, content_weight, smoothness, quality
        )
        logger.info(
            "style-transfer parameters validated: params=%s req=%s",
            params.model_dump(),
            request_id,
        )
        data = await image.read()
        logger.info(
            "style-transfer upload read: filename=%s size=%dB req=%s",
            filename,
            len(data),
            request_id,
        )
        result = await style_transfer_service.transfer(
            data, filename, style, params, request_id=request_id
        )
        logger.info(
            "style-transfer endpoint completed: result_url=%s time_ms=%d req=%s",
            result.result_url,
            result.time_ms,
            request_id,
        )
        return TransferResponse(data=result)

    return app


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """将 FastAPI 表单校验错误映射为前端约定格式。"""

    logger.warning(
        "request validation failed: method=%s path=%s errors=%s req=%s",
        request.method,
        request.url.path,
        exc.errors(),
        getattr(request.state, "request_id", "-"),
    )
    return error_response(ErrorCode.GENERIC, "parameter error", HttpStatus.BAD_REQUEST)


app = create_app()
