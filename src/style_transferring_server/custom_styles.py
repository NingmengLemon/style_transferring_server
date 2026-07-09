"""用户自定义风格的预留服务。

当前前后端还没有确定自定义风格上传接口契约，因此这里只沉淀后续实装所需
的内部模型和存储目录约定，不暴露 HTTP 路由，避免破坏既有 API 合同。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .schemas import StyleInfo, StyleSource


class CustomStyleDraft(BaseModel):
    """未来上传自定义风格时可复用的草稿模型。"""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1, description="用户展示用风格名称")
    description: str = Field(default="", description="用户可选填写的风格描述")
    owner_id: str | None = Field(
        default=None, description="上传用户标识，待认证方案确定"
    )


class CustomStyleStore(Protocol):
    """自定义风格持久化抽象，便于以后接数据库或对象存储。"""

    def build_style_info(
        self,
        style_id: str,
        draft: CustomStyleDraft,
        image_path: Path,
    ) -> StyleInfo:
        """将已保存的自定义风格图片转换为统一 StyleInfo。"""

        ...


class LocalCustomStyleStore:
    """基于本地文件系统的自定义风格存储占位实现。"""

    @property
    def root_dir(self) -> Path:
        return settings.custom_styles_dir

    def build_style_info(
        self,
        style_id: str,
        draft: CustomStyleDraft,
        image_path: Path,
    ) -> StyleInfo:
        """构造统一风格对象，供未来并入 StyleRegistry。"""

        return StyleInfo(
            style_id=style_id,
            name=draft.name,
            artist="用户自定义",
            description=draft.description,
            preview_url="",
            image_path=image_path,
            source=StyleSource.CUSTOM,
            owner_id=draft.owner_id,
        )


custom_style_store = LocalCustomStyleStore()
