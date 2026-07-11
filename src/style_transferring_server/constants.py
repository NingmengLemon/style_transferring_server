"""项目范围内复用的常量与枚举。

集中放置 API 路径、业务错误码、图片约束和风格迁移默认参数，避免核心
模块散落 magic number/string。仅保留确实需要贴近算法解释的数值在算法
函数附近。
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Final, Literal


class ApiPath(StrEnum):
    """HTTP 路径前缀。"""

    API_PREFIX = "/api"
    STATIC_PREFIX = "/static"
    HEALTH = "/api/health"
    STYLES = "/api/styles"
    STYLE_TRANSFER = "/api/style-transfer"
    CUSTOM_STYLE_TRANSFER = "/api/custom-style-transfer"


class StaticSubdir(StrEnum):
    """静态资源子目录。"""

    STYLES = "styles"
    RESULTS = "results"


class ErrorCode(IntEnum):
    """前后端约定的业务错误码。"""

    SUCCESS = 0
    GENERIC = 1000
    IMAGE_REQUIRED = 2001
    IMAGE_UNREADABLE = 2002
    IMAGE_UNSUPPORTED_TYPE = 2003
    IMAGE_TOO_LARGE = 2004
    IMAGE_INVALID_SIZE = 2005
    STYLE_NOT_FOUND = 3001
    INVALID_TRANSFER_PARAMETER = 3002
    MODEL_LOADING_FAILED = 3003
    STYLE_TRANSFER_FAILED = 3004
    CUDA_OUT_OF_MEMORY = 3005
    INFERENCE_TIMEOUT = 3006


class HttpStatus(IntEnum):
    """本项目常用 HTTP 状态码。"""

    BAD_REQUEST = 400
    PAYLOAD_TOO_LARGE = 413
    UNSUPPORTED_MEDIA_TYPE = 415
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504

    IM_A_TEAPOT = 418


class ImageConstraint(IntEnum):
    """上传图片约束。"""

    MIN_SIDE = 16
    MAX_SIDE = 12_000
    BYTES_PER_MEBIBYTE = 1024 * 1024


class TransferDefault(IntEnum):
    """风格迁移表单参数默认值。"""

    STYLE_STRENGTH = 70
    CONTENT_WEIGHT = 50
    SMOOTHNESS = 30


DEFAULT_QUALITY: Final[Literal["fast", "normal", "hd"]] = "fast"
SUPPORTED_UPLOAD_EXTENSIONS: Final = frozenset({"jpg", "jpeg", "png"})
SUPPORTED_IMAGE_FORMATS: Final = frozenset({"jpeg", "png"})
RESULT_FILENAME_PREFIX: Final = "result_"
RESULT_IMAGE_FORMAT: Final = "PNG"
STYLE_PREVIEW_IMAGE_FORMAT: Final = "JPEG"
STYLE_PREVIEW_QUALITY: Final = 88
REQUEST_ID_HEX_LENGTH: Final = 8
MILLISECONDS_PER_SECOND: Final = 1000
RGB_CHANNELS: Final = 3
WARMUP_IMAGE_SIZE: Final = 64
WARMUP_RGB_VALUE: Final = 127
SMOOTHNESS_FILTER_THRESHOLD: Final = 0.45
SMOOTHNESS_RADIUS_SCALE: Final = 0.8
