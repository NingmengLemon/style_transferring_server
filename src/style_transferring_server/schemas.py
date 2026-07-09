"""API 请求/响应的 Pydantic 数据模型。

这些模型对应 ``docs/风格迁移项目API文档.md`` 中的前后端约定，
并作为 FastAPI 的 ``response_model``，从而在 ``/openapi.json`` 中
暴露完整的数据结构。
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")

# 生成质量档位。
Quality = Literal["fast", "normal", "hd"]


class ApiResponse(BaseModel, Generic[DataT]):
    """统一成功响应包装。"""

    code: int = Field(default=0, description="状态码，0 表示成功")
    message: str = Field(default="success", description="描述信息")
    data: DataT = Field(..., description="返回数据")


class ErrorResponse(BaseModel):
    """统一失败响应包装。"""

    code: int = Field(..., description="业务状态码", examples=[3001])
    message: str = Field(..., description="错误描述", examples=["style not found"])
    data: None = Field(None, description="失败时固定为 null")


# ---- /api/health ----


class HealthData(BaseModel):
    """健康检查返回数据。"""

    status: Literal["running"] = Field(..., description="服务运行状态")
    model_loaded: bool = Field(..., description="模型是否已加载")
    device: str = Field(..., description="运行设备", examples=["cuda", "cpu"])


# ---- /api/styles ----


class StyleItem(BaseModel):
    """单个可选风格。"""

    style_id: str = Field(..., description="风格唯一编号", examples=["vangogh"])
    name: str = Field(..., description="风格名称", examples=["梵高星空"])
    artist: str = Field(..., description="艺术家", examples=["Vincent van Gogh"])
    description: str = Field(..., description="风格描述")
    preview_url: str = Field(
        ..., description="风格预览图地址", examples=["/static/styles/vangogh.jpg"]
    )


class StylesData(BaseModel):
    """风格列表返回数据。"""

    styles: list[StyleItem] = Field(..., description="可选风格列表")


# ---- /api/style-transfer ----


class TransferParameters(BaseModel):
    """本次风格迁移实际使用的参数。"""

    style_strength: int = Field(..., ge=0, le=100, description="风格强度")
    content_weight: int = Field(..., ge=0, le=100, description="内容保留程度")
    smoothness: int = Field(..., ge=0, le=100, description="细节平滑程度")
    quality: Quality = Field(..., description="生成质量")


class TransferResult(BaseModel):
    """风格迁移返回数据。"""

    result_url: str = Field(
        ...,
        description="生成图片地址",
        examples=["/static/results/result001.png"],
    )
    time_ms: int = Field(..., description="生成耗时（毫秒）", examples=[2300])
    parameters: TransferParameters = Field(..., description="实际使用参数")


# 具体化的响应别名，供路由 response_model 使用。
HealthResponse = ApiResponse[HealthData]
StylesResponse = ApiResponse[StylesData]
TransferResponse = ApiResponse[TransferResult]
