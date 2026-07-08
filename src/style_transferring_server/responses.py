"""统一 API 响应和异常定义。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("style_transferring_server")


@dataclass(frozen=True)
class ApiError(Exception):
    """可映射到前端约定响应体的业务异常。"""

    code: int
    message: str
    http_status: int = 400


def success(data: Any) -> dict[str, Any]:
    """构造统一成功响应。"""

    return {"code": 0, "message": "success", "data": data}


def error_response(code: int, message: str, http_status: int) -> JSONResponse:
    """构造统一失败响应。"""

    return JSONResponse(
        status_code=http_status,
        content={"code": code, "message": message, "data": None},
    )


async def api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
    """FastAPI 业务异常处理器。"""

    return error_response(exc.code, exc.message, exc.http_status)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器，避免返回非约定格式，同时不向客户端泄漏内部细节。"""

    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return error_response(1000, "internal server error", 500)
