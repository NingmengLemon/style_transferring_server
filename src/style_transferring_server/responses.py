"""统一 API 响应和异常定义。"""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from pydantic import BaseModel, ConfigDict

from .constants import ErrorCode, HttpStatus

logger = logging.getLogger("style_transferring_server")


class ApiError(Exception):
    """可映射到前端约定响应体的业务异常。"""

    def __init__(
        self,
        code: ErrorCode | int,
        message: str,
        http_status: HttpStatus | int = HttpStatus.BAD_REQUEST,
    ) -> None:
        self.code = int(code)
        self.message = message
        self.http_status = int(http_status)
        super().__init__(message)


class ErrorPayload(BaseModel):
    """失败响应体，供 error_response 统一序列化。"""

    model_config = ConfigDict(frozen=True)

    code: int
    message: str
    data: None = None


def error_response(code: int, message: str, http_status: int) -> JSONResponse:
    """构造统一失败响应。"""

    payload = ErrorPayload(code=int(code), message=message)
    return JSONResponse(
        status_code=int(http_status),
        content=payload.model_dump(),
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """FastAPI 业务异常处理器。"""

    logger.warning(
        "api error handled: method=%s path=%s code=%d http_status=%d message=%s req=%s",
        request.method,
        request.url.path,
        exc.code,
        exc.http_status,
        exc.message,
        getattr(request.state, "request_id", "-"),
    )
    return error_response(exc.code, exc.message, exc.http_status)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理器，避免返回非约定格式，同时不向客户端泄漏内部细节。"""

    logger.exception(
        "unhandled error: method=%s path=%s req=%s",
        request.method,
        request.url.path,
        getattr(request.state, "request_id", "-"),
    )
    return error_response(
        ErrorCode.GENERIC,
        "internal server error",
        HttpStatus.INTERNAL_SERVER_ERROR,
    )
