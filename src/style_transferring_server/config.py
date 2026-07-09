"""项目运行配置。

配置来源优先级（高到低）：
1. 显式传入的构造参数（供 CLI 覆盖使用）
2. 环境变量（前缀 ``STYLE_SERVER_``）
3. JSON 配置文件（默认 ``config.json``，可用 ``STYLE_SERVER_CONFIG`` 指定路径）
4. 字段默认值
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_FILE = PROJECT_ROOT / "config.json"
DEFAULT_STYLES_FILE = PROJECT_ROOT / "config" / "styles.json"


def _config_file_path() -> Path:
    """解析 JSON 配置文件路径，允许通过环境变量覆盖。"""

    env_path = os.getenv("STYLE_SERVER_CONFIG")
    return Path(env_path) if env_path else DEFAULT_CONFIG_FILE


class Settings(BaseSettings):
    """服务端可调参数。"""

    model_config = SettingsConfigDict(
        env_prefix="STYLE_SERVER_",
        extra="ignore",
        frozen=True,
    )

    # 网络与上传
    host: str = "0.0.0.0"
    port: int = 8000
    max_upload_mb: int = 10

    # 推理
    timeout_s: float = 30.0
    preview_size: int = 512
    pretrained_vgg: bool = True
    warmup: bool = True

    # 目录与外部配置文件
    data_dir: Path = PROJECT_ROOT / "data"
    styles_config: Path = DEFAULT_STYLES_FILE

    # 日志
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_file: Path | None = None
    log_json: bool = False

    @property
    def output_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def static_dir(self) -> Path:
        return self.output_dir / "static"

    @property
    def results_dir(self) -> Path:
        return self.static_dir / "results"

    @property
    def style_static_dir(self) -> Path:
        return self.static_dir / "styles"

    @property
    def upload_dir(self) -> Path:
        return self.output_dir / "uploads"

    @property
    def wikiart_dir(self) -> Path:
        return self.data_dir / "dataset" / "wikiart"

    @property
    def custom_styles_dir(self) -> Path:
        """用户自定义风格图片目录，当前仅预留给后续上传接口。"""

        return self.output_dir / "custom_styles"

    def runtime_dirs(self) -> tuple[Path, ...]:
        return (
            self.output_dir,
            self.static_dir,
            self.results_dir,
            self.style_static_dir,
            self.upload_dir,
            self.custom_styles_dir,
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        json_source = JsonConfigSettingsSource(
            settings_cls, json_file=_config_file_path()
        )
        # 优先级：init > env > json 文件 > secret。
        return (init_settings, env_settings, json_source, file_secret_settings)


# 模块级单例，供各处直接引用。
settings = Settings()


def ensure_runtime_dirs(target: Settings = settings) -> None:
    """创建运行时输出目录。"""

    for path in target.runtime_dirs():
        path.mkdir(parents=True, exist_ok=True)
