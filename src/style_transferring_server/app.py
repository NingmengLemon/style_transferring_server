"""FastAPI 应用入口。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from typing import cast

from fastapi import FastAPI, File, Form, Request, UploadFile
from starlette.types import ExceptionHandler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR, ensure_runtime_dirs, settings
from .responses import (
    ApiError,
    api_error_handler,
    error_response,
    success,
    unhandled_error_handler,
)
from .styles import style_registry
from .transfer import style_transfer_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时准备目录、预热风格索引并尝试加载/预热模型。"""

    ensure_runtime_dirs()
    _ = style_registry.styles
    try:
        style_transfer_service.load_model()
    except ApiError:
        # 模型加载失败不阻止服务启动，健康检查会如实反映，
        # 真实请求会返回约定的 3003 错误码。
        pass
    else:
        if settings.warmup_on_startup:
            # 在后台线程预热，避免阻塞事件循环启动；
            # 消除首个真实请求的冷启动尖峰（cudnn autotune、显存分配）。
            await asyncio.to_thread(style_transfer_service.warmup)
    yield


def create_app() -> FastAPI:
    """创建后端 HTTP 应用。"""

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
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_error_handler))
    app.add_exception_handler(
        Exception, cast(ExceptionHandler, unhandled_error_handler)
    )
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_error_handler)
    )
    ensure_runtime_dirs()
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/api/health", response_model=None)
    async def health() -> dict[str, object] | JSONResponse:
        # 模型尚未加载时先尝试加载一次，让健康检查能如实反映真实状态。
        if not style_transfer_service.model_loaded:
            try:
                style_transfer_service.load_model()
            except ApiError:
                # 加载失败：按契约返回 3003，供客户端在启动流程中感知故障。
                return error_response(3003, "model loading failed", 500)
        return success(
            {
                "status": "running",
                "model_loaded": style_transfer_service.model_loaded,
                "device": str(style_transfer_service.device),
            }
        )

    @app.get("/api/styles")
    async def styles() -> dict[str, object]:
        return success({"styles": style_registry.list_for_api()})

    @app.post("/api/style-transfer")
    async def style_transfer(
        image: UploadFile = File(...),
        style_id: str = Form(...),
        style_strength: int = Form(70),
        content_weight: int = Form(50),
        smoothness: int = Form(30),
        quality: str = Form("fast"),
    ) -> dict[str, object]:
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
        return success(result)

    return app


async def validation_error_handler(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    """将 FastAPI 表单校验错误映射为前端约定格式。"""

    return error_response(1000, "parameter error", 400)


app = create_app()
